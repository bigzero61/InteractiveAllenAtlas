from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
from scipy import ndimage

from .config import ANNOTATION_NII, BASE_NII, CACHE_DIR, CACHE_JSON, STRUCTURE_GRAPH_JSON, UNDERLAY_JSON


CACHE_VERSION = 1


@dataclass(frozen=True)
class CombinedStats:
    count: int
    center: list[float] | None
    bbox: list[list[int]] | None


def _file_signature(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _input_signature() -> dict[str, Any]:
    return {
        "base": _file_signature(BASE_NII),
        "annotation": _file_signature(ANNOTATION_NII),
        "structure_graph": _file_signature(STRUCTURE_GRAPH_JSON),
    }


def _read_graph_root() -> dict[str, Any]:
    with STRUCTURE_GRAPH_JSON.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict) and isinstance(raw.get("msg"), list) and raw["msg"]:
        return raw["msg"][0]
    if isinstance(raw, list) and raw:
        return raw[0]
    if isinstance(raw, dict) and "children" in raw:
        return raw
    raise ValueError(f"Could not find structure graph root in {STRUCTURE_GRAPH_JSON}")


def _hex_color(value: Any) -> str:
    text = str(value or "888888").strip().lstrip("#")
    if len(text) != 6:
        text = "888888"
    return f"#{text.upper()}"


def _flatten_graph(root: dict[str, Any]) -> tuple[int, list[dict[str, Any]]]:
    nodes: list[dict[str, Any]] = []

    def visit(raw: dict[str, Any], depth: int, parent_id: int | None, path_ids: list[int], path_names: list[str]) -> None:
        node_id = int(raw["id"])
        name = str(raw.get("name") or f"Region {node_id}")
        acronym = str(raw.get("acronym") or name)
        next_path_ids = [*path_ids, node_id]
        next_path_names = [*path_names, name]
        children = raw.get("children") or []
        nodes.append(
            {
                "id": node_id,
                "acronym": acronym,
                "name": name,
                "color": _hex_color(raw.get("color_hex_triplet")),
                "parentId": parent_id,
                "childIds": [int(child["id"]) for child in children],
                "ancestorIds": path_ids,
                "depth": depth,
                "graphOrder": int(raw.get("graph_order") or 0),
                "stLevel": int(raw.get("st_level") or 0),
                "pathIds": next_path_ids,
                "pathText": " / ".join(next_path_names),
            }
        )
        for child in children:
            visit(child, depth + 1, node_id, next_path_ids, next_path_names)

    visit(root, 0, None, [], [])
    return int(root["id"]), nodes


def _label_stats_for_array(labels: np.ndarray, x_offset: int = 0) -> dict[int, dict[str, Any]]:
    values, counts = np.unique(labels, return_counts=True)
    present = [int(value) for value in values.tolist() if int(value) != 0]
    count_map = {int(value): int(count) for value, count in zip(values.tolist(), counts.tolist()) if int(value) != 0}
    if not present:
        return {}

    max_label = int(max(present))
    objects = ndimage.find_objects(labels, max_label=max_label)
    weights = np.ones(labels.shape, dtype=np.uint8)
    centers = ndimage.center_of_mass(weights, labels=labels, index=present)

    stats: dict[int, dict[str, Any]] = {}
    for label, center in zip(present, centers):
        obj = objects[label - 1] if label > 0 and label - 1 < len(objects) else None
        if obj is None or any(part is None for part in obj):
            continue
        bbox_min = [int(obj[0].start + x_offset), int(obj[1].start), int(obj[2].start)]
        bbox_max = [int(obj[0].stop - 1 + x_offset), int(obj[1].stop - 1), int(obj[2].stop - 1)]
        stats[label] = {
            "count": count_map[label],
            "center": [float(center[0] + x_offset), float(center[1]), float(center[2])],
            "bbox": [bbox_min, bbox_max],
        }
    return stats


def _json_safe_stats(stats: dict[str, dict[int, dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    return {
        hemi: [{"label": int(label), **payload} for label, payload in sorted(label_stats.items())]
        for hemi, label_stats in stats.items()
    }


def _load_json_safe_stats(raw: dict[str, list[dict[str, Any]]]) -> dict[str, dict[int, dict[str, Any]]]:
    return {
        hemi: {int(item["label"]): {key: value for key, value in item.items() if key != "label"} for item in items}
        for hemi, items in raw.items()
    }


def parse_perm(code: str) -> tuple[int, int, int]:
    text = str(code).strip()
    if len(text) != 3 or sorted(text) != ["0", "1", "2"]:
        raise ValueError("perm must be a permutation of 0, 1, and 2, e.g. 012, 021, 102, 120, 201, or 210. 000 is not valid; identity is 012.")
    return tuple(int(char) for char in text)  # type: ignore[return-value]


def parse_flip(code: str) -> tuple[int, int, int]:
    text = str(code).strip()
    if len(text) != 3 or any(char not in {"0", "1"} for char in text):
        raise ValueError("flip must be a three-digit 0/1 code")
    return tuple(int(char) for char in text)  # type: ignore[return-value]


def apply_perm_flip(volume: np.ndarray, perm: tuple[int, int, int], flip: tuple[int, int, int]) -> np.ndarray:
    out = np.transpose(volume, perm)
    for axis, flag in enumerate(flip):
        if flag:
            out = np.flip(out, axis=axis)
    return np.ascontiguousarray(out)


class AtlasStore:
    _instance: "AtlasStore | None" = None
    _lock = threading.Lock()

    def __init__(self, force_rebuild: bool = False) -> None:
        self.base_img = nib.load(str(BASE_NII))
        self.annotation_img = nib.load(str(ANNOTATION_NII))
        self.base = np.asarray(self.base_img.dataobj)
        self.annotation = np.asarray(self.annotation_img.dataobj)
        self.underlay = self.base
        self.underlay_shape = self.shape if hasattr(self, "shape") else tuple(int(v) for v in self.base.shape[:3])
        self.underlay_info = {
            "kind": "default",
            "name": BASE_NII.name,
            "path": str(BASE_NII),
            "perm": "012",
            "flip": "000",
            "shape": [int(v) for v in self.base.shape[:3]],
        }
        self.shape = tuple(int(v) for v in self.annotation.shape)
        self.affine = np.asarray(self.base_img.affine, dtype=float)

        if self.base.shape != self.annotation.shape:
            raise ValueError(f"Base shape {self.base.shape} does not match annotation shape {self.annotation.shape}")
        if not np.allclose(self.base_img.affine, self.annotation_img.affine):
            raise ValueError("Base and annotation affines do not match")

        x_index = np.arange(self.shape[0], dtype=float)
        self.world_x = self.affine[0, 0] * x_index + self.affine[0, 3]
        self.left_x = np.where(self.world_x < 0)[0]
        self.right_x = np.where(self.world_x > 0)[0]

        cache = None if force_rebuild else self._read_cache()
        if cache is None:
            cache = self._build_cache()
            self._write_cache(cache)

        self.root_id = int(cache["rootId"])
        self.nodes = {int(node["id"]): node for node in cache["nodes"]}
        self.node_list = sorted(self.nodes.values(), key=lambda item: item["graphOrder"])
        self.label_stats = _load_json_safe_stats(cache["labelStats"])
        self.present_labels = sorted(self.label_stats["both"].keys())
        self.max_label = int(max(self.present_labels)) if self.present_labels else 0
        self.color_by_id = {node["id"]: node["color"] for node in self.node_list}
        self._load_persisted_underlay()

    @classmethod
    def get(cls, force_rebuild: bool = False) -> "AtlasStore":
        with cls._lock:
            if cls._instance is None or force_rebuild:
                cls._instance = AtlasStore(force_rebuild=force_rebuild)
            return cls._instance

    def _read_cache(self) -> dict[str, Any] | None:
        if not CACHE_JSON.exists():
            return None
        try:
            with CACHE_JSON.open("r", encoding="utf-8") as f:
                cache = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
        if cache.get("version") != CACHE_VERSION:
            return None
        if cache.get("inputs") != _input_signature():
            return None
        if tuple(cache.get("shape", [])) != self.shape:
            return None
        return cache

    def _write_cache(self, cache: dict[str, Any]) -> None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        temp = CACHE_JSON.with_suffix(".json.tmp")
        with temp.open("w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
        temp.replace(CACHE_JSON)

    def _build_cache(self) -> dict[str, Any]:
        root = _read_graph_root()
        root_id, nodes = _flatten_graph(root)
        node_by_id = {node["id"]: node for node in nodes}

        label_stats = {
            "both": _label_stats_for_array(self.annotation),
            "left": _label_stats_for_array(self.annotation[self.left_x, :, :], int(self.left_x[0])) if len(self.left_x) else {},
            "right": _label_stats_for_array(self.annotation[self.right_x, :, :], int(self.right_x[0])) if len(self.right_x) else {},
        }
        present_labels = set(label_stats["both"].keys())

        def descendants(node_id: int) -> list[int]:
            node = node_by_id[node_id]
            output = [node_id]
            for child_id in node["childIds"]:
                output.extend(descendants(child_id))
            return output

        for node in nodes:
            descendant_ids = descendants(int(node["id"]))
            label_ids = sorted(label_id for label_id in descendant_ids if label_id in present_labels)
            node["descendantIds"] = descendant_ids
            node["labelIds"] = label_ids
            node["counts"] = {}
            node["centers"] = {}
            node["bboxes"] = {}
            for hemi in ("both", "left", "right"):
                combined = self.combine_label_stats(label_ids, hemi, label_stats=label_stats)
                node["counts"][hemi] = combined.count
                node["centers"][hemi] = combined.center
                node["bboxes"][hemi] = combined.bbox

        return {
            "version": CACHE_VERSION,
            "inputs": _input_signature(),
            "shape": list(self.shape),
            "zooms": [float(v) for v in self.base_img.header.get_zooms()[:3]],
            "affine": self.affine.tolist(),
            "rootId": root_id,
            "nodes": sorted(nodes, key=lambda item: item["graphOrder"]),
            "labelStats": _json_safe_stats(label_stats),
        }

    def public_payload(self) -> dict[str, Any]:
        public_nodes = []
        for node in self.node_list:
            public_nodes.append(
                {
                    "id": node["id"],
                    "acronym": node["acronym"],
                    "name": node["name"],
                    "color": node["color"],
                    "parentId": node["parentId"],
                    "childIds": node["childIds"],
                    "ancestorIds": node["ancestorIds"],
                    "depth": node["depth"],
                    "graphOrder": node["graphOrder"],
                    "stLevel": node["stLevel"],
                    "pathText": node["pathText"],
                    "counts": node["counts"],
                    "centers": node["centers"],
                }
            )
        return {"rootId": self.root_id, "nodes": public_nodes}

    def _load_persisted_underlay(self) -> None:
        if not UNDERLAY_JSON.exists():
            return
        try:
            with UNDERLAY_JSON.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            path = Path(payload["path"])
            if path.exists():
                self.set_underlay(path, str(payload.get("perm", "021")), str(payload.get("flip", "000")), str(payload.get("name") or path.name), persist=False)
        except Exception:
            self.reset_underlay(persist=False)

    def reset_underlay(self, persist: bool = True) -> dict[str, Any]:
        self.underlay = self.base
        self.underlay_shape = tuple(int(v) for v in self.base.shape[:3])
        self.underlay_info = {
            "kind": "default",
            "name": BASE_NII.name,
            "path": str(BASE_NII),
            "perm": "012",
            "flip": "000",
            "shape": [int(v) for v in self.underlay_shape],
        }
        if persist and UNDERLAY_JSON.exists():
            UNDERLAY_JSON.unlink()
        return self.underlay_info

    def set_underlay(self, path: Path, perm_code: str, flip_code: str, name: str | None = None, persist: bool = True) -> dict[str, Any]:
        perm = parse_perm(perm_code)
        flip = parse_flip(flip_code)
        img = nib.load(str(path))
        data = np.asarray(img.dataobj)
        if data.ndim > 3:
            data = data[..., 0]
        if data.ndim != 3:
            raise ValueError("Uploaded underlay must be a 3D NIfTI image, or a 4D image with a usable first volume")
        oriented = apply_perm_flip(data, perm, flip)
        self.underlay = oriented
        self.underlay_shape = tuple(int(v) for v in oriented.shape[:3])
        self.underlay_info = {
            "kind": "uploaded",
            "name": name or path.name,
            "path": str(path),
            "perm": "".join(str(v) for v in perm),
            "flip": "".join(str(v) for v in flip),
            "shape": [int(v) for v in self.underlay_shape],
        }
        if persist:
            UNDERLAY_JSON.parent.mkdir(parents=True, exist_ok=True)
            with UNDERLAY_JSON.open("w", encoding="utf-8") as f:
                json.dump(self.underlay_info, f, ensure_ascii=False, indent=2)
        return self.underlay_info

    def label_ids_for_structures(self, structure_ids: list[int]) -> set[int]:
        labels: set[int] = set()
        for structure_id in structure_ids:
            node = self.nodes.get(int(structure_id))
            if node is None or int(structure_id) == self.root_id:
                continue
            labels.update(int(label) for label in node["labelIds"])
        return labels

    def label_ids_for_merges(self, merges: list[dict[str, Any]]) -> set[int]:
        labels: set[int] = set()
        for merge in merges:
            members = [int(value) for value in merge.get("memberStructureIds", [])]
            labels.update(self.label_ids_for_structures(members))
        return labels

    def combine_label_stats(
        self,
        label_ids: list[int] | set[int],
        hemi: str,
        label_stats: dict[str, dict[int, dict[str, Any]]] | None = None,
    ) -> CombinedStats:
        stats_by_hemi = label_stats or self.label_stats
        stats = stats_by_hemi.get(hemi, stats_by_hemi["both"])
        total = 0
        weighted = np.zeros(3, dtype=float)
        bbox_min = np.array([np.inf, np.inf, np.inf], dtype=float)
        bbox_max = np.array([-np.inf, -np.inf, -np.inf], dtype=float)

        for label_id in label_ids:
            item = stats.get(int(label_id))
            if not item:
                continue
            count = int(item["count"])
            total += count
            weighted += np.asarray(item["center"], dtype=float) * count
            bbox = item.get("bbox")
            if bbox:
                bbox_min = np.minimum(bbox_min, np.asarray(bbox[0], dtype=float))
                bbox_max = np.maximum(bbox_max, np.asarray(bbox[1], dtype=float))

        if total == 0:
            return CombinedStats(count=0, center=None, bbox=None)
        return CombinedStats(
            count=int(total),
            center=[float(value) for value in (weighted / total).tolist()],
            bbox=[[int(value) for value in bbox_min.tolist()], [int(value) for value in bbox_max.tolist()]],
        )

    def center_for(self, structure_ids: list[int], merges: list[dict[str, Any]], hemi: str) -> CombinedStats:
        label_ids = self.label_ids_for_structures(structure_ids)
        label_ids.update(self.label_ids_for_merges(merges))
        return self.combine_label_stats(label_ids, hemi)

    def label_at(self, x: int, y: int, z: int) -> dict[str, Any]:
        xi = int(np.clip(x, 0, self.shape[0] - 1))
        yi = int(np.clip(y, 0, self.shape[1] - 1))
        zi = int(np.clip(z, 0, self.shape[2] - 1))
        label_id = int(self.annotation[xi, yi, zi])
        node = self.nodes.get(label_id)
        return {
            "id": label_id,
            "acronym": node["acronym"] if node else "",
            "name": node["name"] if node else "",
            "color": node["color"] if node else "#888888",
            "voxel": [xi, yi, zi],
        }
