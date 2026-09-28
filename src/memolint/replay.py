"""Play a captured demo transcript back at a controlled pace.

Recording a live demo means recording its dead air: API latency, rate-limit waits,
a command typed wrong. This replays a transcript that already happened, with the
rhythm of a live run and none of the waiting, so a screen recording of it cuts
cleanly into a video.

Capture a transcript with colour:

    MEMOLINT_FORCE_COLOR=1 memolint demo --auto > docs/demo-transcript.ansi

Then:

    memolint replay docs/demo-transcript.ansi --speed 1.4
"""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")

# Lines that deserve a pause, because they are the beats a viewer needs to land.
RULE_CHARS = ("─", "-" * 10)          # section rules
PANEL_CHARS = ("┌", "└", "│", "├", "┬", "┴", "┼",
               "┐", "┘", "+--", "|")


@dataclass
class Pacing:
    speed: float = 1.0
    beat: float = 1.1        # pause at a section rule
    hold: float = 0.9        # pause after a review panel closes
    per_char: float = 0.010
    min_line: float = 0.05
    max_line: float = 0.55

    def delay_for(self, line: str, *, prev_was_panel: bool) -> float:
        plain = ANSI.sub("", line).rstrip()
        if not plain:
            return 0.10 / self.speed
        if any(plain.startswith(c) or plain.count(c) > 8 for c in RULE_CHARS):
            return self.beat / self.speed
        if any(c in plain[:3] for c in PANEL_CHARS):
            return 0.03 / self.speed
        if prev_was_panel:
            return self.hold / self.speed
        d = min(self.max_line, max(self.min_line, len(plain) * self.per_char))
        return d / self.speed


def is_panel_line(line: str) -> bool:
    plain = ANSI.sub("", line)
    return bool(plain) and any(c in plain[:3] for c in PANEL_CHARS)


def play(
    path: str | Path,
    *,
    speed: float = 1.0,
    start: int = 0,
    stop: int | None = None,
    countdown: int = 0,
    out=None,
) -> int:
    """Print the transcript with pacing. Returns the number of lines played."""
    out = out or sys.stdout
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    lines = lines[start : stop if stop is not None else len(lines)]
    pacing = Pacing(speed=speed)

    for n in range(countdown, 0, -1):
        out.write(f"\rrecording starts in {n} ")
        out.flush()
        time.sleep(1.0)
    if countdown:
        out.write("\r" + " " * 30 + "\r")
        out.flush()

    prev_panel = False
    for line in lines:
        out.write(line + "\n")
        out.flush()
        time.sleep(pacing.delay_for(line, prev_was_panel=prev_panel and not is_panel_line(line)))
        prev_panel = is_panel_line(line)
    return len(lines)


def find_marks(path: str | Path) -> list[tuple[int, str]]:
    """Line numbers of each section rule, so a script can cite exact cue points."""
    marks: list[tuple[int, str]] = []
    for i, line in enumerate(Path(path).read_text(encoding="utf-8", errors="replace").splitlines()):
        plain = ANSI.sub("", line).strip()
        # A section rule is a run of horizontal lines around a title. Panel borders use
        # other box-drawing characters, and which ones depends on the theme (square or
        # rounded corners), so reject any box-drawing character that is not the plain rule.
        if plain.count("─") <= 8:
            continue
        if any(0x2500 <= ord(c) <= 0x257F and c != "─" for c in plain):
            continue
        title = plain.strip("─ ")
        if title:
            marks.append((i, title))
    return marks
