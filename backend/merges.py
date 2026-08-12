from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from .config import MERGES_JSON


HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _normalise_color(color: str) -> str:
    value = color.strip()
    if not value.startswith("#"):
        value = f"#{value}"
    if not HEX_RE.match(value):
        raise ValueError("Color must be a #RRGGBB value")
    return value.upper()


def load_merges(path: Path = MERGES_JSON) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return [normalise_merge(item, keep_id=True) for item in data if isinstance(item, dict)]


def save_merges(merges: list[dict[str, Any]], path: Path = MERGES_JSON) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(merges, f, ensure_ascii=False, indent=2)
    temp.replace(path)


def normalise_merge(payload: dict[str, Any], keep_id: bool = False) -> dict[str, Any]:
    merge_id = str(payload.get("id") or uuid.uuid4().hex[:10]) if keep_id else uuid.uuid4().hex[:10]
    members = sorted({int(value) for value in payload.get("memberStructureIds", [])})
    name = str(payload.get("name") or "Merged region").strip()[:80] or "Merged region"
    return {
        "id": merge_id,
        "name": name,
        "color": _normalise_color(str(payload.get("color") or "#FFCC33")),
        "memberStructureIds": members,
        "visible": bool(payload.get("visible", True)),
    }
