"""Render article screenshots from the real demo transcript.

    python scripts/make_article_images.py

Draws terminal output as PNGs so the articles can show what the reviewer actually
printed. Every line comes from docs/demo-transcript.ansi, so nothing is mocked up.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from transcript_data import load  # noqa: E402

LINES = load()["lines"]
OUT = ROOT / "docs" / "images"

BG = (13, 17, 23)
CHROME = (22, 27, 34)
BORDER = (48, 54, 61)
INK = (230, 237, 243)
FAINT = (125, 133, 144)
HOT = (255, 106, 61)
COOL = (90, 209, 196)

MONO = "C:/Windows/Fonts/consola.ttf"
MONO_B = "C:/Windows/Fonts/consolab.ttf"
UI_B = "C:/Windows/Fonts/segoeuib.ttf"

SIZE = 19
LH = int(SIZE * 1.55)
PAD = 26


def hexcol(c):
    if c is None:
        return INK
    if c.startswith("rgb("):
        return tuple(int(v) for v in c[4:-1].split(","))
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def terminal(lines, caption=None, width=1000):
    mono, mono_b = ImageFont.truetype(MONO, SIZE), ImageFont.truetype(MONO_B, SIZE)
    cw = mono.getlength("M")
    head = 40
    cap_h = 44 if caption else 0
    height = head + PAD * 2 + len(lines) * LH + cap_h
    img = Image.new("RGB", (width, height), BG)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, width, head], fill=CHROME)
    d.line([(0, head), (width, head)], fill=BORDER)
    for x in (22, 44, 66):
        d.ellipse([x - 6, 14, x + 6, 26], fill=(64, 72, 82))
    d.text((92, 11), "memolint", font=ImageFont.truetype(MONO, 16), fill=FAINT)

    y = head + PAD
    for ln in lines:
        x = PAD
        for sp in ln["s"]:
            d.text((x, y), sp["t"], font=mono_b if sp["b"] else mono, fill=hexcol(sp["c"]))
            x += cw * len(sp["t"])
        y += LH

    if caption:
        d.line([(0, height - cap_h), (width, height - cap_h)], fill=BORDER)
        d.text((PAD, height - cap_h + 13), caption,
               font=ImageFont.truetype(UI_B, 17), fill=FAINT)
    d.rectangle([0, 0, width - 1, height - 1], outline=BORDER)
    return img


def slice_lines(a, b):
    return [ln for ln in LINES[a:b] if any(s["t"].strip() for s in ln["s"])]


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # Each range ends on a finished sentence, so no image is cut off mid-thought.
    terminal(slice_lines(139, 154), "Memory off: correct, and indistinguishable from any other tool") \
        .save(OUT / "01-memory-off.png")

    terminal(slice_lines(156, 174), "Memory on: same model, same diff, and it names the incident") \
        .save(OUT / "02-memory-on.png")

    terminal(slice_lines(175, 184), "Suppression made visible: what it chose not to raise, and why") \
        .save(OUT / "03-deliberately-not-raised.png")

    terminal(slice_lines(184, 190), "What the reviewer had learned by the third pull request") \
        .save(OUT / "04-rules-learned.png")

    for p in sorted(OUT.glob("*.png")):
        print(f"{p.name}  {Image.open(p).size[0]}x{Image.open(p).size[1]}")


if __name__ == "__main__":
    main()
