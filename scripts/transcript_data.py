"""Turn the captured ANSI transcript into the render-ready JSON the video scripts use.

The transcript in docs/ is the source of truth; this derived file is generated on demand,
so a fresh clone can render the video without first running the demo against live APIs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

TRANSCRIPT = ROOT / "docs" / "demo-transcript.ansi"
DERIVED = ROOT / "preview_data.json"

SGR = re.compile(r"\x1b\[([0-9;]*)m")
BASE = {
    30: "#5c6370", 31: "#e06c75", 32: "#98c379", 33: "#e5c07b", 34: "#61afef",
    35: "#c678dd", 36: "#56b6c2", 37: "#dcdfe4", 90: "#7f848e", 91: "#ff7b86",
    92: "#b5e890", 93: "#ffd68a", 94: "#82c7ff", 95: "#e0a3f0", 96: "#78d9e0", 97: "#ffffff",
}


def parse_line(line: str) -> list[dict]:
    """Split one ANSI line into coloured spans."""
    out: list[dict] = []
    pos = 0
    cur = {"c": None, "b": False}
    for m in SGR.finditer(line):
        if m.start() > pos:
            out.append({"t": line[pos:m.start()], **cur})
        codes = [int(c) for c in (m.group(1) or "0").split(";") if c != ""] or [0]
        i = 0
        while i < len(codes):
            c = codes[i]
            if c == 0:
                cur = {"c": None, "b": False}
            elif c == 1:
                cur = {**cur, "b": True}
            elif c == 22:
                cur = {**cur, "b": False}
            elif c in BASE:
                cur = {**cur, "c": BASE[c]}
            elif c == 38 and i + 4 < len(codes) and codes[i + 1] == 2:
                cur = {**cur, "c": "rgb(%d,%d,%d)" % tuple(codes[i + 2:i + 5])}
                i += 4
            elif c == 38 and i + 2 < len(codes) and codes[i + 1] == 5:
                cur = {**cur, "c": None}
                i += 2
            i += 1
        pos = m.end()
    if pos < len(line):
        out.append({"t": line[pos:], **cur})
    return [s for s in out if s["t"]]


def build(speed: float = 1.4) -> dict:
    from memolint.replay import Pacing, find_marks, is_panel_line

    lines = TRANSCRIPT.read_text(encoding="utf-8", errors="replace").splitlines()
    pacing, prev, data = Pacing(speed=speed), False, []
    for ln in lines:
        d = pacing.delay_for(ln, prev_was_panel=prev and not is_panel_line(ln))
        data.append({"s": parse_line(ln), "d": round(d, 3)})
        prev = is_panel_line(ln)
    return {"lines": data, "marks": find_marks(TRANSCRIPT)}


def ensure() -> Path:
    """Generate the derived file if it is missing or older than the transcript."""
    if not TRANSCRIPT.exists():
        raise SystemExit(
            f"{TRANSCRIPT} is missing. Capture one with:\n"
            "  MEMOLINT_FORCE_COLOR=1 memolint demo --auto > docs/demo-transcript.ansi"
        )
    if not DERIVED.exists() or DERIVED.stat().st_mtime < TRANSCRIPT.stat().st_mtime:
        DERIVED.write_text(json.dumps(build()), encoding="utf-8")
        print(f"generated {DERIVED.name} from {TRANSCRIPT.name}")
    return DERIVED


def load() -> dict:
    return json.loads(ensure().read_text(encoding="utf-8"))


if __name__ == "__main__":
    ensure()
