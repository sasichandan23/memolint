"""Cut the demo into a beat-synced edit.

Every shot's length is measured in beats, so the cuts land on the music instead of
near it. Hits get a flash and a zoom punch that decays before the next beat.

    python scripts/make_beat.py --bpm 150 --bars 84 --out docs/track.wav
    python scripts/beat_edit.py --bpm 150 --audio docs/track.wav --out docs/memolint-edit.mp4

Swap in a licensed track of your own with --audio and set --bpm to its tempo.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H, FPS = 1920, 1080, 30

BG = (10, 13, 18)
INK = (238, 241, 244)
DIM = (151, 163, 176)
FAINT = (93, 106, 119)
HOT = (255, 106, 61)
COOL = (90, 209, 196)
WARN = (255, 200, 87)

MONO, MONO_B = "C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/consolab.ttf"
UI_B, UI_BLK, UI = "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/seguibl.ttf", "C:/Windows/Fonts/segoeui.ttf"

LINES = json.loads((ROOT / "preview_data.json").read_text(encoding="utf-8"))["lines"]


def F(p, s):
    return ImageFont.truetype(p, s)


def hexcol(c):
    if c is None:
        return INK
    if c.startswith("rgb("):
        return tuple(int(v) for v in c[4:-1].split(","))
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def fit(draw, text, path, size, max_w):
    """Shrink until the line fits the frame."""
    while size > 20:
        f = F(path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return F(path, size)


# ---------- shots ----------

class Shot:
    beats = 1

    def frame(self, p: float) -> Image.Image:  # p goes 0 -> 1 across the shot
        raise NotImplementedError


class Stinger(Shot):
    """One huge line. The workhorse of a fast edit."""

    def __init__(self, text, beats=2, sub=None, colour=INK, rule=True, size=150):
        self.text, self.beats, self.sub, self.colour, self.rule, self.size = text, beats, sub, colour, rule, size

    def frame(self, p):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        f = fit(d, self.text, UI_BLK, self.size, W - 200)
        # fit() may have shrunk the face, so measure what will actually be drawn
        # rather than trusting the requested size; otherwise the rule sits on the text.
        box = d.textbbox((0, 0), self.text, font=f)
        tw, th = box[2] - box[0], box[3] - box[1]
        x = (W - tw) / 2 - box[0]
        y = H // 2 - th / 2 - box[1] - (40 if self.sub else 0)
        d.text((x, y), self.text, font=f, fill=self.colour)
        below = y + box[3] + 40
        if self.rule:
            d.rectangle([(W - 130) / 2, below, (W + 130) / 2, below + 8], fill=HOT)
        if self.sub:
            sf = F(UI, 40)
            sw = d.textlength(self.sub, font=sf)
            d.text(((W - sw) / 2, below + 34), self.sub, font=sf, fill=DIM)
        return img


class Split(Shot):
    """Two columns: the comparison the whole video exists for."""

    def __init__(self, left, right, lsub, rsub, beats=8):
        self.left, self.right, self.lsub, self.rsub, self.beats = left, right, lsub, rsub, beats

    def frame(self, p):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.line([(W // 2, 120), (W // 2, H - 120)], fill=(38, 47, 58), width=2)
        for x0, title, sub, col in ((0, self.left, self.lsub, HOT), (W // 2, self.right, self.rsub, COOL)):
            lf = F(UI_BLK, 64)
            tw = d.textlength(title, font=lf)
            d.text((x0 + (W // 2 - tw) / 2, 300), title, font=lf, fill=col)
            sf = F(UI, 34)
            for i, ln in enumerate(sub):
                w = d.textlength(ln, font=sf)
                d.text((x0 + (W // 2 - w) / 2, 430 + i * 52), ln, font=sf, fill=DIM if i else INK)
        return img


class Terminal(Shot):
    """Transcript lines streaming in, as they did in the real run."""

    def __init__(self, start, end, beats, rows=22, size=25):
        self.start, self.end, self.beats, self.rows, self.size = start, end, beats, rows, size
        self.mono, self.mono_b = F(MONO, size), F(MONO_B, size)
        self.lh = int(size * 1.52)
        self.cw = self.mono.getlength("M")

    def frame(self, p):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 58], fill=(18, 23, 30))
        for i, x in enumerate((40, 70, 100)):
            d.ellipse([x - 8, 21, x + 8, 37], fill=(48, 59, 71))
        d.text((138, 18), "memolint demo", font=F(MONO, 20), fill=FAINT)

        upto = self.start + max(1, int((self.end - self.start) * min(1.0, p * 1.06)))
        visible = LINES[max(self.start, upto - self.rows):upto]
        y = 96
        for ln in visible:
            x = 70
            for sp in ln["s"]:
                d.text((x, y), sp["t"], font=self.mono_b if sp["b"] else self.mono, fill=hexcol(sp["c"]))
                x += self.cw * len(sp["t"])
            y += self.lh
        return img


class Quote(Shot):
    """A single line of real output, blown up. Used for the outage moment."""

    def __init__(self, text, beats=6, label=None, colour=WARN):
        self.text, self.beats, self.label, self.colour = text, beats, label, colour

    def frame(self, p):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        words, lines, cur = self.text.split(), [], ""
        f = F(MONO_B, 52)
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) > W - 260:
                lines.append(cur)
                cur = w
            else:
                cur = t
        lines.append(cur)
        y = H // 2 - len(lines) * 40
        if self.label:
            lf = F(UI_B, 30)
            d.text((130, y - 90), self.label.upper(), font=lf, fill=HOT)
        for ln in lines:
            d.text((130, y), ln, font=f, fill=self.colour)
            y += 78
        return img


class Card(Shot):
    def __init__(self, title, sub, foot=None, beats=8):
        self.title, self.sub, self.foot, self.beats = title, sub, foot, beats

    def frame(self, p):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        tf = fit(d, self.title, UI_BLK, 104, W - 300)
        d.text((140, H // 2 - 150), self.title, font=tf, fill=INK)
        d.rectangle([144, H // 2 - 14, 264, H // 2 - 6], fill=HOT)
        d.text((140, H // 2 + 30), self.sub, font=F(UI, 44), fill=DIM)
        if self.foot:
            d.text((140, H - 160), self.foot, font=F(UI, 32), fill=FAINT)
        return img


# ---------- the edit ----------

def build_edit() -> list[Shot]:
    return [
        # cold open: state the problem in single words, one per beat
        Stinger("YOUR CODE REVIEWER", 2, size=120),
        Stinger("HAS AMNESIA", 2, colour=HOT, size=140),
        Stinger("EVERY", 1, rule=False, size=170),
        Stinger("SINGLE", 1, rule=False, size=170),
        Stinger("PULL REQUEST", 2, colour=HOT, size=150),
        Card("Memolint", "A code reviewer that remembers your team's precedents.",
             "Built on Hindsight agent memory", beats=8),

        # the problem, hit by hit
        Stinger("it repeats the nitpick you rejected", 2, size=84),
        Stinger("it forgets your conventions", 2, size=84),
        Stinger("it never heard of your outages", 2, size=84),
        Stinger("it starts from zero", 2, colour=HOT, size=96),
        Stinger("EVERY TIME", 2, colour=HOT, size=160),
        Stinger("SO I GAVE IT A MEMORY", 4, colour=COOL, size=118),

        # how it works, in four beats of plain language
        Stinger("HOW IT WORKS", 2, size=130),
        Stinger("1. recall what the team said", 2, size=92),
        Stinger("2. review with that in the prompt", 2, size=88),
        Stinger("3. retain what happened next", 2, size=92),
        Stinger("the model is the same. the prompt is not.", 4, colour=COOL, size=78),

        # PR 1 - cold
        Stinger("PULL REQUEST 1", 2, sub="0 memories", size=110),
        Terminal(0, 58, 40),
        Stinger("THE TEAM ANSWERS", 2, colour=COOL, size=110),
        Terminal(59, 66, 8),
        Stinger("accepted", 1, rule=False, colour=COOL, size=130),
        Stinger("rejected", 1, rule=False, colour=HOT, size=130),
        Stinger("2 RULES STORED", 2, size=120),

        # PR 2 - it changed
        Stinger("PULL REQUEST 2", 2, sub="15 memories recalled", size=110),
        Terminal(66, 128, 48),
        Quote("precedent: The team prohibits print() for logging, requiring get_logger(__name__).",
              6, label="every finding cites a rule"),
        Stinger("IT STOPPED REPEATING ITSELF", 4, colour=COOL, size=100),
        Terminal(129, 134, 6),
        Stinger("LINKED TO A REAL OUTAGE", 4, colour=WARN, size=104),

        # PR 3 - the payoff
        Stinger("SAME MODEL", 2, size=150),
        Stinger("SAME DIFF", 2, size=150),
        Stinger("REVIEWED TWICE", 3, colour=HOT, size=140),
        Split("MEMORY OFF", "MEMORY ON", ["generic warning", "", "correct", "forgettable"],
              ["names the outage", "", "cites the precedent", "skips what you rejected"], beats=8),
        Terminal(138, 154, 22),
        Stinger("NOW WITH MEMORY", 3, colour=COOL, size=130),
        Terminal(155, 183, 38),
        Quote("This is the exact shape of the bug that caused the 41-minute checkout outage "
              "on September 3, 2026.", 10, label="it remembered the outage"),
        Stinger("NOBODY TOLD IT", 2, size=140),
        Stinger("THOSE WERE THE SAME BUG", 4, colour=COOL, size=110),
        Stinger("a database query per item", 2, size=96),
        Stinger("an API call per item", 2, size=96),
        Stinger("SAME SHAPE", 3, colour=WARN, size=160),

        # what it ended up knowing, and what it costs
        Stinger("WHAT IT LEARNED", 2, size=126),
        Stinger("guard clauses over nested ifs", 2, size=88),
        Stinger("never print(), always the logger", 2, size=88),
        Stinger("no type hints on private helpers", 2, size=88),
        Stinger("one 41-minute outage", 2, colour=WARN, size=104),
        Card("2,206 tokens", "per review, memory included",
             "runs on free tiers: Groq and Hindsight", beats=8),

        # close
        Terminal(184, 193, 14),
        Stinger("THE MODEL IS STATELESS", 3, size=118),
        Stinger("THE MEMORY IS NOT", 4, colour=COOL, size=128),
        Card("Memolint", "github.com/sasichandan23/trial-1",
             "Hindsight: github.com/vectorize-io/hindsight", beats=14),
    ]


def punch(img: Image.Image, t: float, strength: float) -> Image.Image:
    """Zoom-in that decays across the beat, plus a flash on the first frames."""
    z = 1.0 + strength * max(0.0, 1.0 - t * 3.2)
    if z > 1.001:
        w, h = int(W / z), int(H / z)
        img = img.crop(((W - w) // 2, (H - h) // 2, (W + w) // 2, (H + h) // 2)).resize((W, H), Image.LANCZOS)
    if t < 0.06:
        img = ImageEnhance.Brightness(img).enhance(1.0 + (0.06 - t) * 5.0)
    return img


def render(bpm: float, audio: Path | None, out: Path) -> None:
    beat = 60.0 / bpm
    shots = build_edit()
    total_beats = sum(s.beats for s in shots)

    ff = __import__("imageio_ffmpeg").get_ffmpeg_exe()
    cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio)]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += [str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert proc.stdin

    for s in shots:
        dur = s.beats * beat
        n = max(1, round(dur * FPS))
        # A short shot is a hit and gets a hard punch; a long one breathes.
        strength = 0.05 if s.beats <= 2 else (0.028 if s.beats <= 4 else 0.012)
        for i in range(n):
            p = i / max(1, n - 1)
            img = s.frame(p)
            proc.stdin.write(punch(img, i / FPS / max(beat, 0.01), strength).tobytes())

    proc.stdin.close()
    proc.wait()
    secs = total_beats * beat
    print(f"wrote {out}  {secs:.1f}s  ({total_beats} beats at {bpm:g} BPM, {len(shots)} shots)")
    print(f"track needs at least {secs/ (60/bpm) / 4:.0f} bars")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bpm", type=float, default=150.0)
    ap.add_argument("--audio", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "memolint-edit.mp4")
    ap.add_argument("--beats-only", action="store_true", help="Print the shot timings and exit.")
    a = ap.parse_args()
    if a.beats_only:
        t = 0.0
        for s in build_edit():
            print(f"{t:7.2f}s  {s.beats:>2} beats  {type(s).__name__}")
            t += s.beats * 60.0 / a.bpm
        print(f"total {t:.1f}s")
    else:
        render(a.bpm, a.audio, a.out)
