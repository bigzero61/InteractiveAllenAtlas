from __future__ import annotations

import os
import sys
from pathlib import Path


def _default_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _default_atlas_root(project_root: Path) -> Path:
    candidates = [project_root / "data" / "atlas"]
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / "data" / "atlas")
    for candidate in candidates:
        if (candidate / "P56_Atlas.nii.gz").exists():
            return candidate
    return candidates[0]


PROJECT_ROOT = Path(os.environ.get("INTERACTIVE_ATLAS_PROJECT_ROOT", _default_project_root()))
ATLAS_ROOT = Path(os.environ.get("ALLEN_ATLAS_ROOT", _default_atlas_root(PROJECT_ROOT)))

BASE_NII = Path(os.environ.get("ATLAS_BASE_NII", ATLAS_ROOT / "P56_Atlas.nii.gz"))
ANNOTATION_NII = Path(
    os.environ.get("ATLAS_ANNOTATION_NII", ATLAS_ROOT / "ABA_v3_P56_Annotation_downloaded.nii.gz")
)
STRUCTURE_GRAPH_JSON = Path(
    os.environ.get("ATLAS_STRUCTURE_GRAPH_JSON", ATLAS_ROOT / "ABA_v3_structure_graph.json")
)

CACHE_DIR = PROJECT_ROOT / "data" / "cache"
CACHE_JSON = CACHE_DIR / "atlas_cache.json"
MERGES_JSON = PROJECT_ROOT / "data" / "merges.json"
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
UNDERLAY_JSON = PROJECT_ROOT / "data" / "underlay.json"
DIST_DIR = PROJECT_ROOT / "dist"

AXES = {
    "x": {"name": "Sagittal", "index": 0},
    "y": {"name": "Coronal", "index": 1},
    "z": {"name": "Axial", "index": 2},
}

BASE_COLORMAPS = [
    "greyscale",
    "hot",
    "cool",
    "viridis",
    "plasma",
    "inferno",
    "magma",
    "red-yellow",
    "blue-lightblue",
]

ANNOTATION_PALETTES = [
    "allen",
    "graph-order",
    "viridis",
    "plasma",
    "inferno",
    "magma",
    "red-yellow",
    "blue-lightblue",
]
