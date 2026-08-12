from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
from skimage.segmentation import find_boundaries

from .cache import AtlasStore
from .config import ANNOTATION_PALETTES, AXES, BASE_COLORMAPS


@dataclass
class RenderOptions:
    axis: str = "z"
    index: int = 0
    structure_ids: list[int] | None = None
    merge_ids: list[str] | None = None
    hemi: str = "both"
    opacity: float = 0.55
    base_cmap: str = "greyscale"
    annotation_palette: str = "allen"
    overlay_mode: str = "fill"
    show_labels: bool = False
    show_hemisphere_labels: bool = False
    show_crosshair: bool = False
    crosshair: list[int] | None = None
    underlay_low: float = 0.0
    underlay_high: float = 100.0
    show_scale_bar: bool = False
    show_color_bar: bool = False
    show_coordinates: bool = False


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.strip().lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _palette_rgb(name: str, value: float) -> tuple[int, int, int]:
    value = float(np.clip(value, 0.0, 1.0))
    if name == "greyscale":
        v = int(round(value * 255))
        return v, v, v
    if name == "red-yellow":
        return 255, int(round(value * 255)), 0
    if name == "blue-lightblue":
        return int(round(value * 80)), int(round(120 + value * 135)), 255
    cmap = plt.get_cmap(name if name in {"hot", "cool", "viridis", "plasma", "inferno", "magma"} else "gray")
    r, g, b, _ = cmap(value)
    return int(r * 255), int(g * 255), int(b * 255)


def _contrast_limits(gray: np.ndarray, low_percent: float = 0.0, high_percent: float = 100.0) -> tuple[float, float]:
    data = gray.astype(np.float32)
    low = float(np.clip(low_percent, 0.0, 100.0))
    high = float(np.clip(high_percent, 0.0, 100.0))
    if high <= low:
        low, high = 0.0, 100.0
    lo = float(np.nanpercentile(data, low))
    hi = float(np.nanpercentile(data, high))
    if hi <= lo:
        lo = float(np.nanmin(data))
        hi = float(np.nanmax(data))
    return lo, hi


def _base_rgb(gray: np.ndarray, cmap_name: str, low_percent: float = 0.0, high_percent: float = 100.0) -> np.ndarray:
    name = cmap_name if cmap_name in BASE_COLORMAPS else "greyscale"
    data = gray.astype(np.float32)
    lo, hi = _contrast_limits(data, low_percent, high_percent)
    if hi <= lo:
        norm = np.zeros_like(data, dtype=np.float32)
    else:
        norm = (data - lo) / (hi - lo)
        norm = np.clip(norm, 0.0, 1.0)
    if name == "greyscale":
        rgb = np.stack([norm, norm, norm], axis=-1)
    elif name == "red-yellow":
        rgb = np.stack([np.ones_like(norm), norm, np.zeros_like(norm)], axis=-1)
    elif name == "blue-lightblue":
        rgb = np.stack([norm * 0.31, 0.47 + norm * 0.53, np.ones_like(norm)], axis=-1)
    else:
        rgb = plt.get_cmap(name)(norm)[..., :3]
    return np.clip(rgb * 255, 0, 255).astype(np.uint8)


def _annotation_rgb(store: AtlasStore, label_id: int, palette_name: str) -> tuple[int, int, int]:
    palette = palette_name if palette_name in ANNOTATION_PALETTES else "allen"
    if palette == "allen":
        return _hex_to_rgb(store.color_by_id.get(label_id, "#8A8A8A"))
    if palette == "graph-order":
        node = store.nodes.get(label_id)
        value = ((node or {}).get("graphOrder", label_id) % 997) / 996
    else:
        value = (label_id % 997) / 996
    return _palette_rgb("viridis" if palette == "graph-order" else palette, value)


def _extract_plane(volume: np.ndarray, axis: str, index: int) -> np.ndarray:
    if axis == "x":
        return volume[index, :, :].T[::-1, :]
    if axis == "y":
        return volume[:, index, :].T[::-1, :]
    return volume[:, :, index].T[::-1, :]


def _map_index(index: int, source_len: int, target_len: int) -> int:
    if source_len <= 1 or target_len <= 1:
        return 0
    scaled = index / (source_len - 1) * (target_len - 1)
    return int(np.clip(round(scaled), 0, target_len - 1))


def _extract_underlay_plane(store: AtlasStore, axis: str, index: int, target_shape: tuple[int, int]) -> np.ndarray:
    axis_index = AXES[axis]["index"]
    underlay_index = _map_index(index, store.shape[axis_index], store.underlay_shape[axis_index])
    plane = _extract_plane(store.underlay, axis, underlay_index)
    if plane.shape == target_shape:
        return plane
    image = Image.fromarray(np.asarray(plane, dtype=np.float32))
    resized = image.resize((target_shape[1], target_shape[0]), Image.Resampling.BILINEAR)
    return np.asarray(resized)


def _plane_shape(store: AtlasStore, axis: str) -> tuple[int, int]:
    if axis == "x":
        return store.shape[2], store.shape[1]
    if axis == "y":
        return store.shape[2], store.shape[0]
    return store.shape[1], store.shape[0]


def _clip_index(store: AtlasStore, axis: str, index: int) -> int:
    axis_index = AXES[axis]["index"]
    return int(np.clip(index, 0, store.shape[axis_index] - 1))


def _hemi_mask(store: AtlasStore, axis: str, index: int, hemi: str, image_shape: tuple[int, int]) -> np.ndarray:
    if hemi not in {"left", "right"}:
        return np.ones(image_shape, dtype=bool)
    if axis == "x":
        world_x = store.world_x[index]
        ok = world_x < 0 if hemi == "left" else world_x > 0
        return np.full(image_shape, ok, dtype=bool)
    x_ok = store.world_x < 0 if hemi == "left" else store.world_x > 0
    return np.broadcast_to(x_ok.reshape(1, -1), image_shape)


def _label_table(store: AtlasStore, label_ids: set[int], palette: str) -> tuple[np.ndarray, np.ndarray]:
    colors = np.zeros((store.max_label + 1, 3), dtype=np.uint8)
    active = np.zeros((store.max_label + 1,), dtype=bool)
    for label_id in label_ids:
        if 0 <= label_id <= store.max_label:
            colors[label_id] = _annotation_rgb(store, label_id, palette)
            active[label_id] = True
    return colors, active


def _apply_layer(
    rgb: np.ndarray,
    labels_2d: np.ndarray,
    label_ids: set[int],
    color: tuple[int, int, int] | None,
    hemi_mask: np.ndarray,
    opacity: float,
    mode: str,
    store: AtlasStore,
    palette: str,
) -> None:
    if not label_ids:
        return
    if color is None:
        colors, active = _label_table(store, label_ids, palette)
        valid = labels_2d <= store.max_label
        mask = valid & active[np.minimum(labels_2d, store.max_label)] & hemi_mask
        color_pixels = colors[np.minimum(labels_2d, store.max_label)]
        boundary_source = np.where(mask, labels_2d, 0)
        boundary_colors = color_pixels
    else:
        colors = np.asarray(color, dtype=np.uint8)
        active = np.zeros((store.max_label + 1,), dtype=bool)
        for label_id in label_ids:
            if 0 <= label_id <= store.max_label:
                active[label_id] = True
        valid = labels_2d <= store.max_label
        mask = valid & active[np.minimum(labels_2d, store.max_label)] & hemi_mask
        boundary_source = mask.astype(np.uint8)
        boundary_colors = np.broadcast_to(colors.reshape(1, 1, 3), rgb.shape)

    draw_fill = mode in {"fill", "fill-contour", "fill-contour-outer"}
    draw_contour = mode in {"contour", "fill-contour", "contour-outer", "fill-contour-outer"}
    if draw_fill and np.any(mask):
        alpha = float(np.clip(opacity, 0.0, 1.0))
        rgb[mask] = (rgb[mask].astype(np.float32) * (1.0 - alpha) + boundary_colors[mask].astype(np.float32) * alpha).astype(
            np.uint8
        )
    if draw_contour and np.any(mask):
        if mode in {"contour-outer", "fill-contour-outer"}:
            boundary_source = mask.astype(np.uint8)
        boundary = find_boundaries(boundary_source, mode="inner")
        rgb[boundary] = boundary_colors[boundary]


def _font(size: int = 14) -> ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, color: tuple[int, int, int], font: ImageFont.ImageFont) -> None:
    x, y = xy
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        draw.text((x + dx, y + dy), text, fill=(0, 0, 0), font=font, anchor="mm")
    draw.text((x, y), text, fill=color, font=font, anchor="mm")


def _project_voxel(store: AtlasStore, voxel: list[int], axis: str) -> tuple[float, float]:
    x, y, z = [float(value) for value in voxel]
    if axis == "x":
        return y, store.shape[2] - 1 - z
    if axis == "y":
        return x, store.shape[2] - 1 - z
    return x, store.shape[1] - 1 - y


def _draw_crosshair(image: Image.Image, store: AtlasStore, axis: str, voxel: list[int]) -> None:
    x, y = _project_voxel(store, voxel, axis)
    if x < 0 or y < 0 or x >= image.width or y >= image.height:
        return
    draw = ImageDraw.Draw(image)
    color = (255, 219, 88)
    shadow = (0, 0, 0)
    for offset in (-1, 1):
        draw.line((x + offset, 0, x + offset, image.height), fill=shadow, width=1)
        draw.line((0, y + offset, image.width, y + offset), fill=shadow, width=1)
    draw.line((x, 0, x, image.height), fill=color, width=1)
    draw.line((0, y, image.width, y), fill=color, width=1)


def _draw_scale_bar(image: Image.Image, store: AtlasStore, axis: str, length_mm: float = 1.0) -> None:
    if axis == "x":
        spacing = float(np.linalg.norm(store.affine[:3, 1]))
    else:
        spacing = float(np.linalg.norm(store.affine[:3, 0]))
    if spacing <= 0:
        return
    bar_px = int(round(length_mm / spacing))
    bar_px = int(np.clip(bar_px, 12, max(12, image.width - 48)))
    x0 = 22
    y0 = image.height - 24
    x1 = x0 + bar_px
    draw = ImageDraw.Draw(image)
    font = _font(13)
    for dy in (-1, 1):
        draw.line((x0, y0 + dy, x1, y0 + dy), fill=(0, 0, 0), width=3)
    draw.line((x0, y0, x1, y0), fill=(255, 255, 255), width=3)
    draw.line((x0, y0 - 5, x0, y0 + 5), fill=(255, 255, 255), width=2)
    draw.line((x1, y0 - 5, x1, y0 + 5), fill=(255, 255, 255), width=2)
    draw.text((x0, y0 - 18), f"{length_mm:g} mm", fill=(255, 255, 255), font=font)


def _axis_mm(store: AtlasStore, axis: str, index: int) -> float:
    axis_index = AXES[axis]["index"]
    return float(store.affine[axis_index, axis_index] * index + store.affine[axis_index, 3])


def _draw_coordinate_label(image: Image.Image, store: AtlasStore, axis: str, index: int) -> None:
    text = f"{axis}={_axis_mm(store, axis, index):.3f} mm"
    draw = ImageDraw.Draw(image)
    font = _font(13)
    x = image.width - 10
    y = image.height - 10
    draw.text((x + 1, y + 1), text, fill=(0, 0, 0), font=font, anchor="rb")
    draw.text((x, y), text, fill=(255, 255, 255), font=font, anchor="rb")


def _format_value(value: float) -> str:
    if abs(value) >= 1000 or (abs(value) < 0.01 and value != 0):
        return f"{value:.2e}"
    return f"{value:.3g}"


def _draw_color_bar(image: Image.Image, cmap_name: str, lo: float, hi: float) -> None:
    bar_h = min(130, max(60, image.height // 3))
    bar_w = 12
    x0 = image.width - 24
    y0 = max(34, (image.height - bar_h) // 2)
    gradient = np.linspace(1.0, 0.0, bar_h, dtype=np.float32).reshape(bar_h, 1)
    colors = np.zeros((bar_h, bar_w, 3), dtype=np.uint8)
    for row, value in enumerate(gradient[:, 0]):
        colors[row, :, :] = _palette_rgb(cmap_name, float(value))
    bar = Image.fromarray(colors)
    image.paste(bar, (x0, y0))
    draw = ImageDraw.Draw(image)
    font = _font(11)
    draw.rectangle((x0, y0, x0 + bar_w, y0 + bar_h), outline=(255, 255, 255), width=1)
    draw.text((x0 - 3, y0), _format_value(hi), fill=(255, 255, 255), font=font, anchor="rt")
    draw.text((x0 - 3, y0 + bar_h), _format_value(lo), fill=(255, 255, 255), font=font, anchor="rb")


def _component_label_points(mask: np.ndarray, min_area: int = 20) -> list[tuple[float, float, int]]:
    labeled, count = ndi.label(mask)
    if count == 0:
        return []
    points: list[tuple[float, float, int]] = []
    objects = ndi.find_objects(labeled)
    for component_id, obj in enumerate(objects, start=1):
        if obj is None:
            continue
        local = labeled[obj] == component_id
        area = int(local.sum())
        if area < min_area:
            continue
        rows, cols = np.nonzero(local)
        rows = rows + obj[0].start
        cols = cols + obj[1].start
        row_mean = float(rows.mean())
        col_mean = float(cols.mean())
        nearest = int(np.argmin((rows - row_mean) ** 2 + (cols - col_mean) ** 2))
        points.append((float(cols[nearest]), float(rows[nearest]), area))
    return sorted(points, key=lambda item: item[2], reverse=True)


def _label_annotation_items(
    store: AtlasStore,
    options: RenderOptions,
    selected_merges: list[dict[str, Any]],
    labels_2d: np.ndarray,
    hemi_mask: np.ndarray,
) -> list[dict[str, Any]]:
    axis_index = AXES[options.axis]["index"]
    candidates: list[tuple[str, tuple[int, int, int], set[int], list[list[int]] | None]] = []
    for structure_id in options.structure_ids or []:
        node = store.nodes.get(int(structure_id))
        if not node or int(structure_id) == store.root_id:
            continue
        candidates.append((node["acronym"], _hex_to_rgb(node["color"]), set(node["labelIds"]), node["bboxes"].get(options.hemi)))
    for merge in selected_merges:
        stats = store.center_for([], [merge], options.hemi)
        candidates.append((merge["name"], _hex_to_rgb(merge["color"]), store.label_ids_for_merges([merge]), stats.bbox))

    items: list[dict[str, Any]] = []
    occupied: list[tuple[float, float]] = []
    for text, color, label_ids, bbox in candidates:
        if not label_ids:
            continue
        if bbox is not None and not (bbox[0][axis_index] <= options.index <= bbox[1][axis_index]):
            continue
        mask = np.isin(labels_2d, list(label_ids)) & hemi_mask
        if not np.any(mask):
            continue
        points = _component_label_points(mask)
        if not points:
            continue
        x, y, _area = points[0]
        if x < 8 or y < 8 or x > labels_2d.shape[1] - 8 or y > labels_2d.shape[0] - 8:
            continue
        if any((x - ox) ** 2 + (y - oy) ** 2 < 22**2 for ox, oy in occupied):
            continue
        occupied.append((x, y))
        items.append({"text": text, "xy": (x, y), "color": color, "ha": "center", "va": "center", "size": 14, "weight": "bold"})
    return items


def _draw_labels(
    image: Image.Image,
    store: AtlasStore,
    options: RenderOptions,
    selected_merges: list[dict[str, Any]],
    labels_2d: np.ndarray,
    hemi_mask: np.ndarray,
) -> None:
    draw = ImageDraw.Draw(image)
    font = _font(14)
    for item in _label_annotation_items(store, options, selected_merges, labels_2d, hemi_mask):
        _draw_text(draw, item["xy"], item["text"], item["color"], font)


def _draw_orientation_labels(image: Image.Image, store: AtlasStore, axis: str, index: int) -> None:
    draw = ImageDraw.Draw(image)
    font = _font(18)
    fill = (235, 245, 255)
    w, h = image.size
    if axis == "x":
        draw.text((w / 2, 10), "S", fill=fill, font=font, anchor="mt")
        draw.text((w / 2, h - 10), "I", fill=fill, font=font, anchor="mb")
        draw.text((12, h / 2), "P", fill=fill, font=font, anchor="lm")
        draw.text((w - 12, h / 2), "A", fill=fill, font=font, anchor="rm")
        return
    if axis == "y":
        draw.text((12, 10), "L", fill=fill, font=font)
        draw.text((w - 26, 10), "R", fill=fill, font=font)
        draw.text((w / 2, 10), "S", fill=fill, font=font, anchor="mt")
        draw.text((w / 2, h - 10), "I", fill=fill, font=font, anchor="mb")
        return
    draw.text((12, 10), "L", fill=fill, font=font)
    draw.text((w - 26, 10), "R", fill=fill, font=font)
    draw.text((w / 2, 10), "A", fill=fill, font=font, anchor="mt")
    draw.text((w / 2, h - 10), "P", fill=fill, font=font, anchor="mb")


def _orientation_items(width: int, height: int, axis: str) -> list[dict[str, Any]]:
    white = (235, 245, 255)
    if axis == "x":
        return [
            {"text": "S", "xy": (width / 2, 10), "color": white, "ha": "center", "va": "top", "size": 18, "weight": "bold"},
            {"text": "I", "xy": (width / 2, height - 10), "color": white, "ha": "center", "va": "bottom", "size": 18, "weight": "bold"},
            {"text": "P", "xy": (12, height / 2), "color": white, "ha": "left", "va": "center", "size": 18, "weight": "bold"},
            {"text": "A", "xy": (width - 12, height / 2), "color": white, "ha": "right", "va": "center", "size": 18, "weight": "bold"},
        ]
    if axis == "y":
        return [
            {"text": "L", "xy": (12, 10), "color": white, "ha": "left", "va": "top", "size": 18, "weight": "bold"},
            {"text": "R", "xy": (width - 12, 10), "color": white, "ha": "right", "va": "top", "size": 18, "weight": "bold"},
            {"text": "S", "xy": (width / 2, 10), "color": white, "ha": "center", "va": "top", "size": 18, "weight": "bold"},
            {"text": "I", "xy": (width / 2, height - 10), "color": white, "ha": "center", "va": "bottom", "size": 18, "weight": "bold"},
        ]
    return [
        {"text": "L", "xy": (12, 10), "color": white, "ha": "left", "va": "top", "size": 18, "weight": "bold"},
        {"text": "R", "xy": (width - 12, 10), "color": white, "ha": "right", "va": "top", "size": 18, "weight": "bold"},
        {"text": "A", "xy": (width / 2, 10), "color": white, "ha": "center", "va": "top", "size": 18, "weight": "bold"},
        {"text": "P", "xy": (width / 2, height - 10), "color": white, "ha": "center", "va": "bottom", "size": 18, "weight": "bold"},
    ]


def _as_mpl_color(color: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(float(v) / 255.0 for v in color)


def _text_item(ax: Any, item: dict[str, Any], offset: tuple[int, int] = (0, 0)) -> None:
    x, y = item["xy"]
    ax.text(
        x + offset[0],
        y + offset[1],
        item["text"],
        color=_as_mpl_color(item["color"]),
        fontsize=item.get("size", 13),
        fontweight=item.get("weight", "normal"),
        ha=item.get("ha", "center"),
        va=item.get("va", "center"),
    )


def _draw_mpl_scale_bar(ax: Any, image: Image.Image, store: AtlasStore, axis: str, offset: tuple[int, int] = (0, 0), length_mm: float = 1.0) -> None:
    spacing = float(np.linalg.norm(store.affine[:3, 1])) if axis == "x" else float(np.linalg.norm(store.affine[:3, 0]))
    if spacing <= 0:
        return
    bar_px = int(np.clip(round(length_mm / spacing), 12, max(12, image.width - 48)))
    x0 = offset[0] + 22
    y0 = offset[1] + image.height - 24
    x1 = x0 + bar_px
    ax.plot([x0, x1], [y0, y0], color="white", linewidth=2)
    ax.plot([x0, x0], [y0 - 5, y0 + 5], color="white", linewidth=1.5)
    ax.plot([x1, x1], [y0 - 5, y0 + 5], color="white", linewidth=1.5)
    ax.text(x0, y0 - 18, f"{length_mm:g} mm", color="white", fontsize=10, ha="left", va="bottom")


def _draw_mpl_color_bar(ax: Any, image: Image.Image, cmap_name: str, lo: float, hi: float, offset: tuple[int, int] = (0, 0)) -> None:
    bar_h = min(130, max(60, image.height // 3))
    bar_w = 12
    x0 = offset[0] + image.width - 24
    y0 = offset[1] + max(34, (image.height - bar_h) // 2)
    gradient = np.zeros((bar_h, bar_w, 3), dtype=np.uint8)
    for row, value in enumerate(np.linspace(1.0, 0.0, bar_h)):
        gradient[row, :, :] = _palette_rgb(cmap_name, float(value))
    ax.imshow(gradient, extent=(x0, x0 + bar_w, y0 + bar_h, y0), zorder=3)
    ax.plot([x0, x0 + bar_w, x0 + bar_w, x0, x0], [y0, y0, y0 + bar_h, y0 + bar_h, y0], color="white", linewidth=0.8)
    ax.text(x0 - 3, y0, _format_value(hi), color="white", fontsize=8, ha="right", va="top")
    ax.text(x0 - 3, y0 + bar_h, _format_value(lo), color="white", fontsize=8, ha="right", va="bottom")


def _draw_mpl_overlays(ax: Any, store: AtlasStore, image: Image.Image, options: RenderOptions, merges: list[dict[str, Any]], offset: tuple[int, int] = (0, 0)) -> None:
    labels_2d = _extract_plane(store.annotation, options.axis, options.index)
    mask = _hemi_mask(store, options.axis, options.index, options.hemi, labels_2d.shape[:2])
    if options.show_labels:
        for item in _label_annotation_items(store, options, merges, labels_2d, mask):
            _text_item(ax, item, offset)
    if options.show_hemisphere_labels:
        for item in _orientation_items(image.width, image.height, options.axis):
            _text_item(ax, item, offset)
    if options.show_coordinates:
        _text_item(
            ax,
            {
                "text": f"{options.axis}={_axis_mm(store, options.axis, options.index):.3f} mm",
                "xy": (image.width - 10, image.height - 10),
                "color": (255, 255, 255),
                "ha": "right",
                "va": "bottom",
                "size": 10,
            },
            offset,
        )
    if options.show_scale_bar:
        _draw_mpl_scale_bar(ax, image, store, options.axis, offset)
    if options.show_color_bar:
        base_2d = _extract_underlay_plane(store, options.axis, options.index, _plane_shape(store, options.axis))
        lo, hi = _contrast_limits(base_2d, options.underlay_low, options.underlay_high)
        _draw_mpl_color_bar(ax, image, options.base_cmap, lo, hi, offset)


def render_slice_image(store: AtlasStore, options: RenderOptions, merges: list[dict[str, Any]]) -> Image.Image:
    axis = options.axis if options.axis in AXES else "z"
    options.axis = axis
    options.index = _clip_index(store, axis, int(options.index))
    options.hemi = options.hemi if options.hemi in {"both", "left", "right"} else "both"
    options.overlay_mode = (
        options.overlay_mode
        if options.overlay_mode in {"fill", "fill-selected", "contour", "fill-contour", "contour-outer", "fill-contour-outer"}
        else "fill"
    )

    target_shape = _plane_shape(store, axis)
    base_2d = _extract_underlay_plane(store, axis, options.index, target_shape)
    labels_2d = _extract_plane(store.annotation, axis, options.index)
    underlay_lo, underlay_hi = _contrast_limits(base_2d, options.underlay_low, options.underlay_high)
    rgb = _base_rgb(base_2d, options.base_cmap, options.underlay_low, options.underlay_high)
    mask = _hemi_mask(store, axis, options.index, options.hemi, rgb.shape[:2])

    selected_merges = [merge for merge in merges if merge["id"] in set(options.merge_ids or [])]
    structure_ids = [int(value) for value in (options.structure_ids or []) if int(value) != store.root_id]

    if structure_ids:
        normal_labels = store.label_ids_for_structures(structure_ids)
    elif not selected_merges:
        normal_labels = set(store.present_labels)
    else:
        normal_labels = set()

    if options.overlay_mode == "fill-selected":
        for structure_id in structure_ids:
            node = store.nodes.get(structure_id)
            if node:
                _apply_layer(
                    rgb,
                    labels_2d,
                    set(node["labelIds"]),
                    _hex_to_rgb(node["color"]),
                    mask,
                    options.opacity,
                    "fill",
                    store,
                    options.annotation_palette,
                )
    elif options.overlay_mode in {"contour-outer", "fill-contour-outer"} and structure_ids:
        if options.overlay_mode == "fill-contour-outer":
            _apply_layer(rgb, labels_2d, normal_labels, None, mask, options.opacity, "fill", store, options.annotation_palette)
        for structure_id in structure_ids:
            node = store.nodes.get(structure_id)
            if node:
                _apply_layer(
                    rgb,
                    labels_2d,
                    set(node["labelIds"]),
                    _hex_to_rgb(node["color"]),
                    mask,
                    options.opacity,
                    "contour-outer",
                    store,
                    options.annotation_palette,
                )
    else:
        _apply_layer(
            rgb,
            labels_2d,
            normal_labels,
            None,
            mask,
            options.opacity,
            options.overlay_mode,
            store,
            options.annotation_palette,
        )
    for merge in selected_merges:
        merge_labels = store.label_ids_for_merges([merge])
        merge_mode = "fill" if options.overlay_mode == "fill-selected" else options.overlay_mode
        _apply_layer(
            rgb,
            labels_2d,
            merge_labels,
            _hex_to_rgb(merge["color"]),
            mask,
            options.opacity,
            merge_mode,
            store,
            options.annotation_palette,
        )

    image = Image.fromarray(rgb)
    if options.show_crosshair and options.crosshair is not None:
        _draw_crosshair(image, store, axis, options.crosshair)
    if options.show_labels:
        _draw_labels(image, store, options, selected_merges, labels_2d, mask)
    if options.show_hemisphere_labels:
        _draw_orientation_labels(image, store, axis, options.index)
    if options.show_scale_bar:
        _draw_scale_bar(image, store, axis)
    if options.show_color_bar:
        _draw_color_bar(image, options.base_cmap, underlay_lo, underlay_hi)
    if options.show_coordinates:
        _draw_coordinate_label(image, store, axis, options.index)
    return image


def image_to_png_response(image: Image.Image) -> io.BytesIO:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output


def render_mosaic_image(
    store: AtlasStore,
    axis: str,
    rows: int,
    cols: int,
    start: int,
    step: int,
    anchor: str,
    options: RenderOptions,
    merges: list[dict[str, Any]],
    draw_title: bool = True,
) -> Image.Image:
    axis = axis if axis in AXES else "z"
    rows = int(np.clip(rows, 1, 8))
    cols = int(np.clip(cols, 1, 8))
    step = max(1, int(step))
    axis_len = store.shape[AXES[axis]["index"]]
    tile_h, tile_w = _plane_shape(store, axis)
    title_h = 24 if draw_title else 0
    gap = 6
    canvas = Image.new("RGB", (cols * tile_w + (cols - 1) * gap, title_h + rows * tile_h + (rows - 1) * gap), (16, 20, 24))
    draw = ImageDraw.Draw(canvas)
    font = _font(13)
    total = rows * cols
    anchor = anchor if anchor in {"start", "end"} else "start"
    if anchor == "end":
        indices = [start - (total - 1 - tile) * step for tile in range(total)]
        title = f"{AXES[axis]['name']} End {axis}={start}"
    else:
        indices = [start + tile * step for tile in range(total)]
        title = f"{AXES[axis]['name']} Start {axis}={start}"
    if draw_title:
        draw.text((6, 4), title, fill=(215, 225, 235), font=font)

    for tile in range(rows * cols):
        row = tile // cols
        col = tile % cols
        index = indices[tile]
        x0 = col * (tile_w + gap)
        y0 = title_h + row * (tile_h + gap)
        if 0 <= index < axis_len:
            tile_options = RenderOptions(**{**options.__dict__, "axis": axis, "index": index})
            image = render_slice_image(store, tile_options, merges)
        else:
            image = Image.new("RGB", (tile_w, tile_h), (6, 9, 12))
        canvas.paste(image, (x0, y0))
    return canvas


def export_pdf(store: AtlasStore, payload: dict[str, Any], merges: list[dict[str, Any]]) -> io.BytesIO:
    mode = payload.get("mode", "tri")
    base_options = RenderOptions(
        structure_ids=[int(value) for value in payload.get("structures", [])],
        merge_ids=[str(value) for value in payload.get("merges", [])],
        hemi=str(payload.get("hemi", "both")),
        opacity=float(payload.get("opacity", 0.55)),
        base_cmap=str(payload.get("baseCmap", "greyscale")),
        annotation_palette=str(payload.get("annotationPalette", "allen")),
        overlay_mode=str(payload.get("overlayMode", "fill")),
        show_labels=bool(payload.get("showLabels", False)),
        show_hemisphere_labels=bool(payload.get("showHemisphereLabels", False)),
        show_crosshair=bool(payload.get("showCrosshair", False)),
        crosshair=[int(value) for value in payload.get("crosshair", [])] if payload.get("crosshair") else None,
        underlay_low=float(payload.get("underlayLow", 0.0)),
        underlay_high=float(payload.get("underlayHigh", 100.0)),
        show_scale_bar=bool(payload.get("showScaleBar", False)),
        show_color_bar=bool(payload.get("showColorBar", False)),
        show_coordinates=bool(payload.get("showCoordinates", False)),
    )
    output = io.BytesIO()
    if mode == "mosaic":
        image_options = RenderOptions(
            **{
                **base_options.__dict__,
                "show_labels": False,
                "show_hemisphere_labels": False,
                "show_scale_bar": False,
                "show_color_bar": False,
                "show_coordinates": False,
            }
        )
        image = render_mosaic_image(
            store,
            str(payload.get("axis", "z")),
            int(payload.get("rows", 3)),
            int(payload.get("cols", 4)),
            int(payload.get("start", 0)),
            int(payload.get("step", 5)),
            str(payload.get("anchor", "start")),
            image_options,
            merges,
            draw_title=False,
        )
        fig_w = min(16, max(8, image.width / 180))
        fig_h = min(16, max(6, image.height / 180))
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        ax.imshow(image)
        axis = str(payload.get("axis", "z")) if str(payload.get("axis", "z")) in AXES else "z"
        rows = int(np.clip(int(payload.get("rows", 3)), 1, 8))
        cols = int(np.clip(int(payload.get("cols", 4)), 1, 8))
        start = int(payload.get("start", 0))
        step = max(1, int(payload.get("step", 5)))
        anchor = str(payload.get("anchor", "start"))
        total = rows * cols
        indices = [start - (total - 1 - tile) * step for tile in range(total)] if anchor == "end" else [start + tile * step for tile in range(total)]
        tile_h, tile_w = _plane_shape(store, axis)
        gap = 6
        ax.set_title(f"{AXES[axis]['name']} {'End' if anchor == 'end' else 'Start'} {axis}={start}")
        for tile, index in enumerate(indices):
            if not (0 <= index < store.shape[AXES[axis]["index"]]):
                continue
            row = tile // cols
            col = tile % cols
            tile_options = RenderOptions(**{**base_options.__dict__, "axis": axis, "index": index})
            tile_image = Image.new("RGB", (tile_w, tile_h))
            _draw_mpl_overlays(ax, store, tile_image, tile_options, merges, (col * (tile_w + gap), row * (tile_h + gap)))
        ax.axis("off")
        fig.tight_layout(pad=0.1)
        fig.savefig(output, format="pdf", dpi=180)
        plt.close(fig)
    else:
        slices = payload.get("slices", {}) or {}
        axes = ["x", "y", "z"]
        images = []
        for axis in axes:
            image_options = RenderOptions(
                **{
                    **base_options.__dict__,
                    "show_labels": False,
                    "show_hemisphere_labels": False,
                    "show_scale_bar": False,
                    "show_color_bar": False,
                    "show_coordinates": False,
                    "axis": axis,
                    "index": int(slices.get(axis, store.shape[AXES[axis]["index"]] // 2)),
                }
            )
            image = render_slice_image(
                store,
                image_options,
                merges,
            )
            images.append((axis, image, int(slices.get(axis, store.shape[AXES[axis]["index"]] // 2))))
        fig, axs = plt.subplots(1, 3, figsize=(13.5, 4.8))
        for ax, (axis, image, index) in zip(axs, images):
            ax.imshow(image)
            ax.set_title(f"{AXES[axis]['name']}  {axis}={_axis_mm(store, axis, int(slices.get(axis, store.shape[AXES[axis]['index']] // 2))):.3f} mm")
            overlay_options = RenderOptions(**{**base_options.__dict__, "axis": axis, "index": index})
            _draw_mpl_overlays(ax, store, image, overlay_options, merges)
            ax.axis("off")
        fig.tight_layout(pad=0.3)
        fig.savefig(output, format="pdf", dpi=180)
        plt.close(fig)
    output.seek(0)
    return output
