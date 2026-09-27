"""Local state: the last few reviews with their finding IDs, so `feedback` can reference them."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import STATE_DIR


def _safe(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", name)[:80]


def save_review(key: str, data: dict[str, Any]) -> Path:
    d = STATE_DIR / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{_safe(key)}.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    (STATE_DIR / "last").write_text(p.name, encoding="utf-8")
    return p


def load_review(key: str | None = None) -> dict[str, Any] | None:
    d = STATE_DIR / "reviews"
    if key is None:
        last = STATE_DIR / "last"
        if not last.exists():
            return None
        p = d / last.read_text(encoding="utf-8").strip()
    else:
        p = d / f"{_safe(key)}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def find_finding(fid: str, key: str | None = None) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return (review, finding) for a finding id like F3, searching the given or last review."""
    review = load_review(key)
    if not review:
        return None
    for f in review.get("findings", []):
        if f.get("id", "").upper() == fid.upper():
            return review, f
    return None
