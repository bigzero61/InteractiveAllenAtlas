from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from PyQt5.QtCore import QRect, Qt
from PyQt5.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QCompleter,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backend.cache import AtlasStore
from backend.config import ANNOTATION_PALETTES, AXES, BASE_COLORMAPS, MERGES_JSON, UNDERLAY_JSON, UPLOAD_DIR
from backend.merges import load_merges, normalise_merge, save_merges
from backend.render import RenderOptions, export_pdf, render_mosaic_image, render_slice_image


AXIS_LABEL = {"x": "Sagittal", "y": "Coronal", "z": "Axial"}
OVERLAY_MODES = {
    "Fill": "fill",
    "Fill selected": "fill-selected",
    "Contour labels": "contour",
    "Contour selected": "contour-outer",
    "Fill + label contour": "fill-contour",
    "Fill + selected contour": "fill-contour-outer",
}


def clear_runtime_state() -> None:
    for path in (MERGES_JSON, UNDERLAY_JSON):
        if path.exists():
            path.unlink()
    if UPLOAD_DIR.exists():
        for child in UPLOAD_DIR.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink()


def pil_to_pixmap(image: Image.Image) -> QPixmap:
    rgb = image.convert("RGB")
    w, h = rgb.size
    qimage = QImage(rgb.tobytes(), w, h, w * 3, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(qimage)


def color_icon(color: str) -> QIcon:
    pixmap = QPixmap(14, 14)
    pixmap.fill(QColor(color))
    return QIcon(pixmap)


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


class ImageCanvas(QLabel):
    def __init__(self, app: "AtlasProgram", axis: str | None = None) -> None:
        super().__init__()
        self.app = app
        self.axis = axis
        self.pixmap_source: QPixmap | None = None
        self.draw_rect = QRect()
        self.zoom = 1.0
        self.badge = ""
        self._drag_y: int | None = None
        self._drag_zoom = 1.0
        self.setMinimumSize(180, 180)
        self.setMouseTracking(True)

    def set_image(self, image: Image.Image) -> None:
        self.pixmap_source = pil_to_pixmap(image)
        self.update()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(6, 8, 10))
        if self.pixmap_source is None:
            painter.end()
            return
        base = self.pixmap_source.size()
        fit = base.scaled(self.size(), Qt.KeepAspectRatio)
        w = max(1, int(fit.width() * self.zoom))
        h = max(1, int(fit.height() * self.zoom))
        x = (self.width() - w) // 2
        y = (self.height() - h) // 2
        self.draw_rect = QRect(x, y, w, h)
        painter.drawPixmap(self.draw_rect, self.pixmap_source)
        if self.badge:
            painter.setPen(QColor(255, 255, 255))
            painter.fillRect(10, 10, min(130, 18 + len(self.badge) * 8), 28, QColor(10, 13, 16, 190))
            painter.drawText(18, 29, self.badge)
        painter.end()

    def resizeEvent(self, event: Any) -> None:
        self.update()

    def wheelEvent(self, event: Any) -> None:
        if self.axis is None:
            return
        direction = 1 if event.angleDelta().y() < 0 else -1
        self.app.change_slice(self.axis, self.app.slice_steps[self.axis] * direction)

    def mousePressEvent(self, event: Any) -> None:
        if self.axis is None:
            return
        if event.button() == Qt.RightButton:
            self._drag_y = event.y()
            self._drag_zoom = self.zoom
            return
        if event.button() == Qt.LeftButton and self.app.show_crosshair.isChecked():
            voxel = self.voxel_from_pos(event.x(), event.y())
            if voxel is not None:
                self.app.set_crosshair(voxel)

    def mouseMoveEvent(self, event: Any) -> None:
        if self.axis is None:
            return
        if self._drag_y is not None:
            delta = (self._drag_y - event.y()) / 140.0
            self.zoom = float(np.clip(self._drag_zoom * np.exp(delta), 1.0, 8.0))
            self.update()
            return
        if self.app.show_hover.isChecked():
            self.app.update_hover_label(self.voxel_from_pos(event.x(), event.y()))

    def mouseReleaseEvent(self, event: Any) -> None:
        self._drag_y = None

    def leaveEvent(self, event: Any) -> None:
        self.app.update_hover_label(None)

    def voxel_from_pos(self, px: int, py: int) -> dict[str, int] | None:
        if self.axis is None or self.pixmap_source is None or not self.draw_rect.contains(px, py):
            return None
        col = round((px - self.draw_rect.left()) / max(1, self.draw_rect.width()) * (self.pixmap_source.width() - 1))
        row = round((py - self.draw_rect.top()) / max(1, self.draw_rect.height()) * (self.pixmap_source.height() - 1))
        shape = self.app.store.shape
        if self.axis == "x":
            return {"x": self.app.slices["x"], "y": clamp(col, 0, shape[1] - 1), "z": clamp(shape[2] - 1 - row, 0, shape[2] - 1)}
        if self.axis == "y":
            return {"x": clamp(col, 0, shape[0] - 1), "y": self.app.slices["y"], "z": clamp(shape[2] - 1 - row, 0, shape[2] - 1)}
        return {"x": clamp(col, 0, shape[0] - 1), "y": clamp(shape[1] - 1 - row, 0, shape[1] - 1), "z": self.app.slices["z"]}


class SlicePane(QWidget):
    def __init__(self, app: "AtlasProgram", axis: str) -> None:
        super().__init__()
        self.app = app
        self.axis = axis
        self.title = QLabel()
        self.canvas = ImageCanvas(app, axis)
        self.slider = QSlider(Qt.Horizontal)
        self.spin = QSpinBox()
        self.step = QSpinBox()
        self.step.setRange(1, 80)
        self.step.setValue(4)
        self.slider.setRange(0, app.store.shape[AXES[axis]["index"]] - 1)
        self.spin.setRange(0, app.store.shape[AXES[axis]["index"]] - 1)
        self.slider.valueChanged.connect(lambda value: app.set_slice(axis, value))
        self.spin.valueChanged.connect(lambda value: app.set_slice(axis, value))
        self.step.valueChanged.connect(lambda value: app.set_step(axis, value))

        controls = QHBoxLayout()
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.spin)
        controls.addWidget(QLabel("Step"))
        controls.addWidget(self.step)
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.canvas, 1)
        layout.addLayout(controls)

    def sync_controls(self) -> None:
        value = self.app.slices[self.axis]
        self.title.setText(f"{AXIS_LABEL[self.axis]}  slice {value}")
        self.slider.blockSignals(True)
        self.spin.blockSignals(True)
        self.slider.setValue(value)
        self.spin.setValue(value)
        self.slider.blockSignals(False)
        self.spin.blockSignals(False)


class AtlasProgram(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        clear_runtime_state()
        self.store = AtlasStore.get()
        self.merges = load_merges()
        self.slices = {"x": self.store.shape[0] // 2, "y": self.store.shape[1] // 2, "z": self.store.shape[2] // 2}
        self.slice_steps = {"x": 4, "y": 4, "z": 4}
        self.selected_ids: set[int] = set()
        self.hover_label = ""
        self.crosshair_label = ""
        self.merge_color = "#FFCC33"
        self.node_items: dict[int, QTreeWidgetItem] = {}
        self.search_map: dict[str, int] = {}
        self.setWindowTitle("Interactive Allen CCFv3 Atlas")
        self.resize(1500, 920)
        self.build_ui()
        self.populate_tree()
        self.refresh_all()

    def closeEvent(self, event: Any) -> None:
        clear_runtime_state()
        super().closeEvent(event)

    def build_ui(self) -> None:
        splitter = QSplitter()
        splitter.addWidget(self.build_left_panel())
        splitter.addWidget(self.build_viewer())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

    def build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search id, acronym, name")
        self.search.returnPressed.connect(self.focus_search_result)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.focus_search_result)
        search_row = QHBoxLayout()
        search_row.addWidget(self.search, 1)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        self.all_box = QCheckBox("All structures")
        self.all_box.stateChanged.connect(self.toggle_all)
        layout.addWidget(self.all_box)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Region", "Voxels"])
        self.tree.itemChanged.connect(self.tree_item_changed)
        layout.addWidget(self.tree, 1)

        merge_box = QGroupBox("Merges")
        merge_layout = QVBoxLayout(merge_box)
        self.merge_name = QLineEdit("Merged region")
        color_btn = QPushButton("Color")
        color_btn.clicked.connect(self.pick_merge_color)
        create_btn = QPushButton("Create from checked")
        create_btn.clicked.connect(self.create_merge)
        row = QHBoxLayout()
        row.addWidget(self.merge_name, 1)
        row.addWidget(color_btn)
        row.addWidget(create_btn)
        merge_layout.addLayout(row)
        self.merge_list = QListWidget()
        self.merge_list.itemChanged.connect(self.merge_item_changed)
        self.merge_list.itemDoubleClicked.connect(lambda item: self.locate_merge(item.data(Qt.UserRole)))
        merge_layout.addWidget(self.merge_list)
        delete_btn = QPushButton("Delete selected merge")
        delete_btn.clicked.connect(self.delete_selected_merge)
        merge_layout.addWidget(delete_btn)
        layout.addWidget(merge_box)
        self.refresh_merge_list()
        return panel

    def build_viewer(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        controls = QGridLayout()
        self.hemi = QComboBox()
        self.hemi.addItems(["both", "left", "right"])
        self.overlay = QComboBox()
        for label, value in OVERLAY_MODES.items():
            self.overlay.addItem(label, value)
        self.base_cmap = QComboBox()
        self.base_cmap.addItems(BASE_COLORMAPS)
        self.annotation_palette = QComboBox()
        self.annotation_palette.addItems(ANNOTATION_PALETTES)
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(55)
        self.low = QSlider(Qt.Horizontal)
        self.low.setRange(0, 99)
        self.low.setValue(0)
        self.high = QSlider(Qt.Horizontal)
        self.high.setRange(1, 100)
        self.high.setValue(100)
        for widget in (self.hemi, self.overlay, self.base_cmap, self.annotation_palette):
            widget.currentIndexChanged.connect(self.refresh_all)
        for widget in (self.opacity, self.low, self.high):
            widget.valueChanged.connect(self.refresh_all)
        controls.addWidget(QLabel("Hemisphere"), 0, 0)
        controls.addWidget(self.hemi, 0, 1)
        controls.addWidget(QLabel("Overlay"), 0, 2)
        controls.addWidget(self.overlay, 0, 3)
        controls.addWidget(QLabel("Base cmap"), 0, 4)
        controls.addWidget(self.base_cmap, 0, 5)
        controls.addWidget(QLabel("Low"), 0, 6)
        controls.addWidget(self.low, 0, 7)
        controls.addWidget(QLabel("High"), 0, 8)
        controls.addWidget(self.high, 0, 9)
        controls.addWidget(QLabel("Annotation"), 1, 0)
        controls.addWidget(self.annotation_palette, 1, 1)
        controls.addWidget(QLabel("Opacity"), 1, 2)
        controls.addWidget(self.opacity, 1, 3)

        self.show_labels = QCheckBox("Acronyms")
        self.show_axes = QCheckBox("Axes")
        self.show_axes.setChecked(True)
        self.show_crosshair = QCheckBox("Crosshair")
        self.show_hover = QCheckBox("Hover")
        self.show_xyz = QCheckBox("XYZ")
        self.show_scale = QCheckBox("Scale")
        self.show_colorbar = QCheckBox("Colorbar")
        for i, cb in enumerate((self.show_labels, self.show_axes, self.show_crosshair, self.show_hover, self.show_xyz, self.show_scale, self.show_colorbar)):
            cb.stateChanged.connect(self.refresh_all)
            controls.addWidget(cb, 1, 4 + i)
        pdf_btn = QPushButton("Export PDF")
        pdf_btn.clicked.connect(self.export_pdf)
        upload_btn = QPushButton("Upload underlay")
        upload_btn.clicked.connect(self.upload_underlay)
        self.perm = QLineEdit("021")
        self.perm.setToolTip("perm must contain 0, 1, and 2 exactly once. Identity is 012; 000 is invalid. Example: 021 means old axes 0,2,1.")
        self.flip = QLineEdit("000")
        self.flip.setToolTip("flip is 0/1 after perm; 1 flips that output axis.")
        controls.addWidget(upload_btn, 2, 0)
        controls.addWidget(QLabel("perm"), 2, 1)
        controls.addWidget(self.perm, 2, 2)
        controls.addWidget(QLabel("flip"), 2, 3)
        controls.addWidget(self.flip, 2, 4)
        controls.addWidget(pdf_btn, 2, 5)
        layout.addLayout(controls)

        self.tabs = QTabWidget()
        three = QWidget()
        grid = QGridLayout(three)
        self.panes = {axis: SlicePane(self, axis) for axis in ("x", "y", "z")}
        for col, axis in enumerate(("x", "y", "z")):
            grid.addWidget(self.panes[axis], 0, col)
        self.tabs.addTab(three, "Three view")

        mosaic = QWidget()
        mosaic_layout = QVBoxLayout(mosaic)
        mosaic_controls = QHBoxLayout()
        self.mosaic_axis = QComboBox()
        for axis in ("x", "y", "z"):
            self.mosaic_axis.addItem(AXIS_LABEL[axis], axis)
        self.mosaic_anchor = QComboBox()
        self.mosaic_anchor.addItems(["start", "end"])
        self.mosaic_rows = QSpinBox()
        self.mosaic_rows.setRange(1, 8)
        self.mosaic_rows.setValue(3)
        self.mosaic_cols = QSpinBox()
        self.mosaic_cols.setRange(1, 8)
        self.mosaic_cols.setValue(4)
        self.mosaic_start = QSpinBox()
        self.mosaic_start.setRange(0, self.store.shape[2] - 1)
        self.mosaic_start.setValue(self.slices["z"])
        self.mosaic_step = QSpinBox()
        self.mosaic_step.setRange(1, 80)
        self.mosaic_step.setValue(8)
        for label, widget in (("Axis", self.mosaic_axis), ("Anchor", self.mosaic_anchor), ("Layer", self.mosaic_start), ("Rows", self.mosaic_rows), ("Cols", self.mosaic_cols), ("Step", self.mosaic_step)):
            mosaic_controls.addWidget(QLabel(label))
            mosaic_controls.addWidget(widget)
        for widget in (self.mosaic_axis, self.mosaic_anchor, self.mosaic_rows, self.mosaic_cols, self.mosaic_start, self.mosaic_step):
            if hasattr(widget, "valueChanged"):
                widget.valueChanged.connect(self.refresh_mosaic)
            else:
                widget.currentIndexChanged.connect(self.refresh_mosaic)
        self.mosaic_canvas = ImageCanvas(self)
        mosaic_layout.addLayout(mosaic_controls)
        mosaic_layout.addWidget(self.mosaic_canvas, 1)
        self.tabs.addTab(mosaic, "Mosaic")
        layout.addWidget(self.tabs, 1)
        return panel

    def populate_tree(self) -> None:
        self.tree.blockSignals(True)
        self.tree.clear()
        self.node_items.clear()
        self.search_map.clear()
        root = self.store.nodes[self.store.root_id]
        for child_id in root["childIds"]:
            self.add_tree_item(child_id, self.tree)
        completions = []
        for node in self.store.node_list:
            if node["id"] == self.store.root_id:
                continue
            text = f"{node['acronym']} - {node['name']} [{node['id']}]"
            completions.append(text)
            self.search_map[text] = node["id"]
        completer = QCompleter(completions, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.activated[str].connect(self.focus_completion)
        self.search.setCompleter(completer)
        self.tree.blockSignals(False)

    def add_tree_item(self, node_id: int, parent: QTreeWidget | QTreeWidgetItem) -> None:
        node = self.store.nodes[node_id]
        item = QTreeWidgetItem(parent)
        item.setText(0, f"{node['acronym']}  {node['name']}")
        item.setText(1, str(node["counts"]["both"]))
        item.setIcon(0, color_icon(node["color"]))
        item.setData(0, Qt.UserRole, node_id)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(0, Qt.Unchecked)
        self.node_items[node_id] = item
        for child_id in node["childIds"]:
            self.add_tree_item(child_id, item)

    def tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        node_id = item.data(0, Qt.UserRole)
        if node_id is None:
            return
        if item.checkState(0) == Qt.Checked:
            self.selected_ids.add(int(node_id))
            self.locate_structures([int(node_id)])
        else:
            self.selected_ids.discard(int(node_id))
        self.refresh_all()

    def toggle_all(self) -> None:
        checked = self.all_box.isChecked()
        self.tree.blockSignals(True)
        self.selected_ids = set(self.node_items.keys()) if checked else set()
        for item in self.node_items.values():
            item.setCheckState(0, Qt.Checked if checked else Qt.Unchecked)
        self.tree.blockSignals(False)
        self.refresh_all()

    def focus_search_result(self) -> None:
        query = self.search.text().strip().lower()
        if not query:
            return
        if self.search.text() in self.search_map:
            self.focus_node_id(self.search_map[self.search.text()])
            return
        for node in self.store.node_list:
            haystack = f"{node['id']} {node['acronym']} {node['name']} {node['pathText']}".lower()
            if node["id"] != self.store.root_id and query in haystack:
                self.focus_node_id(node["id"])
                return

    def focus_completion(self, text: str) -> None:
        node_id = self.search_map.get(text)
        if node_id is not None:
            self.focus_node_id(node_id)

    def focus_node_id(self, node_id: int) -> None:
        item = self.node_items.get(node_id)
        if not item:
            return
        self.tree.setCurrentItem(item)
        item.setExpanded(True)
        parent = item.parent()
        while parent:
            parent.setExpanded(True)
            parent = parent.parent()
        self.locate_structures([node_id])
        self.refresh_all()

    def build_options(self, axis: str, index: int) -> RenderOptions:
        return RenderOptions(
            axis=axis,
            index=index,
            structure_ids=sorted(self.selected_ids),
            merge_ids=[merge["id"] for merge in self.merges if merge.get("visible")],
            hemi=self.hemi.currentText(),
            opacity=self.opacity.value() / 100.0,
            base_cmap=self.base_cmap.currentText(),
            annotation_palette=self.annotation_palette.currentText(),
            overlay_mode=self.overlay.currentData(),
            show_labels=self.show_labels.isChecked(),
            show_hemisphere_labels=self.show_axes.isChecked(),
            show_crosshair=self.show_crosshair.isChecked(),
            crosshair=[self.slices["x"], self.slices["y"], self.slices["z"]],
            underlay_low=self.low.value(),
            underlay_high=self.high.value(),
            show_scale_bar=self.show_scale.isChecked(),
            show_color_bar=self.show_colorbar.isChecked(),
            show_coordinates=self.show_xyz.isChecked(),
        )

    def visible_merges(self) -> list[dict[str, Any]]:
        return [merge for merge in self.merges if merge.get("visible")]

    def refresh_all(self) -> None:
        for axis in ("x", "y", "z"):
            self.refresh_axis(axis)
        self.refresh_badges()
        self.refresh_mosaic()

    def refresh_axis(self, axis: str) -> None:
        pane = self.panes[axis]
        pane.sync_controls()
        image = render_slice_image(self.store, self.build_options(axis, self.slices[axis]), self.visible_merges())
        pane.canvas.set_image(image)

    def refresh_mosaic(self) -> None:
        if not hasattr(self, "mosaic_canvas"):
            return
        axis = self.mosaic_axis.currentData()
        self.mosaic_start.setMaximum(self.store.shape[AXES[axis]["index"]] - 1)
        image = render_mosaic_image(
            self.store,
            axis,
            self.mosaic_rows.value(),
            self.mosaic_cols.value(),
            self.mosaic_start.value(),
            self.mosaic_step.value(),
            self.mosaic_anchor.currentText(),
            self.build_options(axis, self.mosaic_start.value()),
            self.visible_merges(),
        )
        self.mosaic_canvas.set_image(image)

    def set_slice(self, axis: str, value: int) -> None:
        self.slices[axis] = clamp(value, 0, self.store.shape[AXES[axis]["index"]] - 1)
        self.refresh_axis(axis)
        self.refresh_badges()

    def change_slice(self, axis: str, delta: int) -> None:
        self.set_slice(axis, self.slices[axis] + delta)

    def set_step(self, axis: str, value: int) -> None:
        self.slice_steps[axis] = value

    def set_crosshair(self, voxel: dict[str, int]) -> None:
        for axis in ("x", "y", "z"):
            self.slices[axis] = clamp(voxel[axis], 0, self.store.shape[AXES[axis]["index"]] - 1)
        self.refresh_all()

    def update_hover_label(self, voxel: dict[str, int] | None) -> None:
        if voxel is None:
            self.hover_label = ""
        else:
            label = self.store.label_at(voxel["x"], voxel["y"], voxel["z"])
            self.hover_label = label["acronym"] if label["id"] and label["acronym"] else ""
        self.refresh_badges()

    def refresh_badges(self) -> None:
        if self.show_hover.isChecked() and self.hover_label:
            text = self.hover_label
        elif self.show_crosshair.isChecked():
            label = self.store.label_at(self.slices["x"], self.slices["y"], self.slices["z"])
            text = label["acronym"] if label["id"] and label["acronym"] else ""
        else:
            text = ""
        for pane in self.panes.values():
            pane.canvas.badge = text
            pane.canvas.update()

    def locate_structures(self, ids: list[int]) -> None:
        stats = self.store.center_for(ids, [], self.hemi.currentText())
        if not stats.center:
            return
        for axis, value in zip(("x", "y", "z"), stats.center):
            self.slices[axis] = clamp(round(value), 0, self.store.shape[AXES[axis]["index"]] - 1)
        axis = self.mosaic_axis.currentData() if hasattr(self, "mosaic_axis") else "z"
        axis_index = AXES[axis]["index"]
        center = round(stats.center[axis_index])
        span = (self.mosaic_rows.value() * self.mosaic_cols.value() * self.mosaic_step.value()) // 2 if hasattr(self, "mosaic_rows") else 0
        self.mosaic_start.setValue(clamp(center + span if self.mosaic_anchor.currentText() == "end" else center - span, 0, self.store.shape[axis_index] - 1))

    def locate_merge(self, merge_id: str) -> None:
        merge = next((item for item in self.merges if item["id"] == merge_id), None)
        if merge:
            stats = self.store.center_for([], [merge], self.hemi.currentText())
            if stats.center:
                for axis, value in zip(("x", "y", "z"), stats.center):
                    self.slices[axis] = clamp(round(value), 0, self.store.shape[AXES[axis]["index"]] - 1)
                self.refresh_all()

    def refresh_merge_list(self) -> None:
        self.merge_list.blockSignals(True)
        self.merge_list.clear()
        for merge in self.merges:
            item = QListWidgetItem(f"{merge['name']} ({len(merge['memberStructureIds'])})")
            item.setIcon(color_icon(merge["color"]))
            item.setData(Qt.UserRole, merge["id"])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if merge.get("visible") else Qt.Unchecked)
            self.merge_list.addItem(item)
        self.merge_list.blockSignals(False)

    def merge_item_changed(self, item: QListWidgetItem) -> None:
        merge_id = item.data(Qt.UserRole)
        for merge in self.merges:
            if merge["id"] == merge_id:
                merge["visible"] = item.checkState() == Qt.Checked
        save_merges(self.merges)
        self.refresh_all()

    def pick_merge_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.merge_color), self)
        if color.isValid():
            self.merge_color = color.name().upper()

    def create_merge(self) -> None:
        if not self.selected_ids:
            QMessageBox.information(self, "Merge", "Check one or more structures first.")
            return
        merge = normalise_merge(
            {"name": self.merge_name.text(), "color": self.merge_color, "memberStructureIds": sorted(self.selected_ids), "visible": True}
        )
        self.merges.append(merge)
        save_merges(self.merges)
        self.refresh_merge_list()
        self.refresh_all()

    def delete_selected_merge(self) -> None:
        item = self.merge_list.currentItem()
        if not item:
            return
        merge_id = item.data(Qt.UserRole)
        self.merges = [merge for merge in self.merges if merge["id"] != merge_id]
        save_merges(self.merges)
        self.refresh_merge_list()
        self.refresh_all()

    def upload_underlay(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open registered underlay", "", "NIfTI (*.nii *.nii.gz);;All files (*)")
        if not path:
            return
        perm = self.perm.text().strip()
        flip = self.flip.text().strip()
        if len(perm) != 3 or sorted(perm) != ["0", "1", "2"]:
            QMessageBox.warning(self, "Invalid perm", "perm must be one of 012, 021, 102, 120, 201, or 210. 000 is not valid; identity is 012.")
            return
        if len(flip) != 3 or any(char not in "01" for char in flip):
            QMessageBox.warning(self, "Invalid flip", "flip must be a three-digit 0/1 code, e.g. 000, 010, or 111.")
            return
        ok = QMessageBox.question(
            self,
            "Registered underlay",
            "Please confirm this underlay is already registered to Allen brain atlas space. It will not be saved as a resampled volume.",
        )
        if ok != QMessageBox.Yes:
            return
        try:
            self.store.set_underlay(Path(path), perm, flip, Path(path).name)
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "Underlay error", str(exc))

    def pdf_name(self) -> str:
        names = []
        for node_id in sorted(self.selected_ids):
            node = self.store.nodes.get(node_id)
            if node:
                names.append(node["acronym"])
        names.extend(merge["name"] for merge in self.merges if merge.get("visible"))
        if not names:
            names = ["all_annotations"]
        prefix = "L_" if self.hemi.currentText() == "left" else "R_" if self.hemi.currentText() == "right" else ""
        safe = "_".join("".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in name) for name in names)
        return prefix + safe + ".pdf"

    def export_pdf(self) -> None:
        out, _ = QFileDialog.getSaveFileName(self, "Save PDF", self.pdf_name(), "PDF (*.pdf)")
        if not out:
            return
        if not out.lower().endswith(".pdf"):
            out += ".pdf"
        payload = {
            "mode": "mosaic" if self.tabs.currentIndex() == 1 else "tri",
            "slices": self.slices,
            "axis": self.mosaic_axis.currentData(),
            "rows": self.mosaic_rows.value(),
            "cols": self.mosaic_cols.value(),
            "start": self.mosaic_start.value(),
            "step": self.mosaic_step.value(),
            "anchor": self.mosaic_anchor.currentText(),
            "structures": sorted(self.selected_ids),
            "merges": [merge["id"] for merge in self.visible_merges()],
            "hemi": self.hemi.currentText(),
            "opacity": self.opacity.value() / 100.0,
            "baseCmap": self.base_cmap.currentText(),
            "annotationPalette": self.annotation_palette.currentText(),
            "overlayMode": self.overlay.currentData(),
            "showLabels": self.show_labels.isChecked(),
            "showHemisphereLabels": self.show_axes.isChecked(),
            "showCrosshair": self.show_crosshair.isChecked(),
            "crosshair": [self.slices["x"], self.slices["y"], self.slices["z"]],
            "underlayLow": self.low.value(),
            "underlayHigh": self.high.value(),
            "showScaleBar": self.show_scale.isChecked(),
            "showColorBar": self.show_colorbar.isChecked(),
            "showCoordinates": self.show_xyz.isChecked(),
        }
        pdf = export_pdf(self.store, payload, self.visible_merges())
        Path(out).write_bytes(pdf.getvalue())


def main() -> int:
    app = QApplication(sys.argv)
    window = AtlasProgram()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
