"""Render the YouTube thumbnail.

    python scripts/make_thumbnail.py --out docs/thumbnail.png

1280x720, high contrast, readable at the size YouTube actually shows it (about 360px
wide in a feed). The design is the video's own argument: two reviews of one diff, one
generic and one that names a past outage.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BG = (10, 13, 18)
PANEL = (16, 21, 28)
INK = (238, 241, 244)
DIM = (151, 163, 176)
HOT = (255, 106, 61)
COOL = (90, 209, 196)
RED = (224, 108, 117)

UI_BLK = "C:/Windows/Fonts/seguibl.ttf"
UI_B = "C:/Windows/Fonts/segoeuib.ttf"
UI = "C:/Windows/Fonts/segoeui.ttf"
MONO = "C:/Windows/Fonts/consola.ttf"
MONO_B = "C:/Windows/Fonts/consolab.ttf"


def F(p, s):
    return ImageFont.truetype(p, s)


def wrap(d, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def build() -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # Two panels: the same diff, reviewed twice.
    pad, gap, top, bot = 40, 26, 190, 108
    pw = (W - pad * 2 - gap) // 2
    for i, (x, label, colour, mark) in enumerate([
        (pad, "WITHOUT MEMORY", RED, "x"),
        (pad + pw + gap, "WITH MEMORY", COOL, "check"),
    ]):
        d.rounded_rectangle([x, top, x + pw, H - bot], radius=14, fill=PANEL,
                            outline=colour, width=4)
        lf = F(UI_B, 30)
        d.text((x + 26, top + 20), label, font=lf, fill=colour)

        body = ("Consider batching\nthese requests."
                if i == 0 else
                "This is the exact\nshape of the bug that\ncaused the 41-minute\ncheckout outage.")
        bf = F(MONO_B if i else MONO, 30 if i else 31)
        y = top + 78
        for ln in body.split("\n"):
            d.text((x + 26, y), ln, font=bf, fill=DIM if i == 0 else INK)
            y += 42

        # verdict mark, bottom right of the panel
        mx, my = x + pw - 74, H - bot - 78
        if mark == "x":
            d.line([mx, my, mx + 44, my + 44], fill=RED, width=9)
            d.line([mx + 44, my, mx, my + 44], fill=RED, width=9)
        else:
            d.line([mx, my + 24, mx + 17, my + 44], fill=COOL, width=10)
            d.line([mx + 17, my + 44, mx + 48, my - 2], fill=COOL, width=10)

    # Headline
    hf = F(UI_BLK, 96)
    title = "SAME MODEL."
    tw = d.textlength(title, font=hf)
    d.text(((W - tw) / 2, 34), title, font=hf, fill=INK)
    sf = F(UI_BLK, 52)
    sub = "ONE OF THEM REMEMBERS."
    sw = d.textlength(sub, font=sf)
    d.text(((W - sw) / 2, 128), sub, font=sf, fill=HOT)

    # Footer strip
    d.rectangle([0, H - 56, W, H], fill=HOT)
    ff = F(UI_B, 30)
    foot = "AI code review with persistent memory"
    fw = d.textlength(foot, font=ff)
    d.text(((W - fw) / 2, H - 46), foot, font=ff, fill=(14, 18, 22))
    return img


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("docs/thumbnail.png"))
    a = ap.parse_args()
    build().save(a.out)
    print(f"wrote {a.out}  {W}x{H}")
