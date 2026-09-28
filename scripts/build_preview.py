"""Generate the video preview page: terminal playback with the edit's captions over it.

    python scripts/build_preview.py

Writes docs/video-preview.html with the transcript data embedded, so the page is a
single self-contained file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from transcript_data import load  # noqa: E402

DATA = load()

# Each beat covers a range of transcript lines and carries the caption burned over the
# footage plus the voiceover line read against it. Line numbers come from `--marks`.
BEATS = [
    {"from": 0,   "caption": "0 memories",                "label": "PR 1 — cold",
     "voice": "First pull request. The memory bank is empty, so this is a normal review. Nothing here you couldn't get from any other tool."},
    {"from": 59,  "caption": "the team answers back",     "label": "Feedback",
     "voice": "Then a human answers. One suggestion was right. One was wrong for this team. Two conventions get written down."},
    {"from": 66,  "caption": "15 memories recalled",      "label": "PR 2 — it changed",
     "voice": "Second pull request, different file. Now every finding cites the rule behind it. And it's quietly not raising the one we rejected."},
    {"from": 129, "caption": "linked to a real outage",   "label": "Incident",
     "voice": "The N plus one finding gets accepted, and tied to an outage that took checkout down for forty-one minutes."},
    {"from": 134, "caption": "same diff, reviewed twice", "label": "PR 3",
     "voice": "Third pull request. We review it twice."},
    {"from": 138, "caption": "memory OFF",                "label": "Memory off",
     "voice": "Memory off. A generic performance warning. Correct, and forgettable."},
    {"from": 155, "caption": "it remembered the outage",  "label": "Memory on",
     "voice": "Memory on. Same model, same diff. It connects a per-item API call to an outage caused by a per-item database query. Nobody told it those were the same bug."},
    {"from": 184, "caption": "3 rules learned",           "label": "Close",
     "voice": "The model is stateless. The memory isn't. That's the whole trick, and it runs entirely on free tiers."},
]

TEMPLATE = (ROOT / "scripts" / "preview_template.html").read_text(encoding="utf-8")

payload = json.dumps({"lines": DATA["lines"], "beats": BEATS}, separators=(",", ":"))
out = TEMPLATE.replace("/*__DATA__*/null", payload)
dest = ROOT / "docs" / "video-preview.html"
dest.write_text(out, encoding="utf-8")
print(f"wrote {dest} ({len(out):,} bytes)")
