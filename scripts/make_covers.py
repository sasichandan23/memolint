"""Render Dev.to cover images, one per article.

    python scripts/make_covers.py

1000x420, which is what Dev.to renders. Drawn rather than generated, so the text is
spelled correctly, which image models still cannot be trusted with.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1000, 420
BG = (16, 20, 26)
PANEL = (22, 28, 36)
INK = (238, 241, 244)
DIM = (140, 152, 165)
FAINT = (74, 86, 98)
HOT = (255, 106, 61)
COOL = (90, 209, 196)

UI_BLK = "C:/Windows/Fonts/seguibl.ttf"
UI_B = "C:/Windows/Fonts/segoeuib.ttf"
UI = "C:/Windows/Fonts/segoeui.ttf"
MONO = "C:/Windows/Fonts/consola.ttf"


def F(p, s):
    return ImageFont.truetype(p, s)


def fit(d, text, path, size, max_w):
    while size > 14:
        f = F(path, size)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return F(path, size)


def base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def blurred_code(d, x, y, w, rows, colour=FAINT, seed=0):
    """Abstract code lines: bars, not letters, so nothing can read as a typo."""
    widths = [0.82, 0.55, 0.70, 0.38, 0.64, 0.47, 0.75, 0.33, 0.58]
    for i in range(rows):
        lw = int(w * widths[(i + seed) % len(widths)])
        indent = 16 if i % 3 == 1 else (32 if i % 4 == 3 else 0)
        d.rounded_rectangle([x + indent, y + i * 17, x + indent + lw, y + i * 17 + 7],
                            radius=3, fill=colour)


def cover_memory() -> Image.Image:
    """Rejections being filed into a memory bank."""
    img, d = base()

    # editor panel, left
    d.rounded_rectangle([44, 96, 430, 350], radius=12, fill=PANEL, outline=(40, 50, 62), width=2)
    d.rectangle([44, 96, 430, 124], fill=(28, 35, 44))
    for i, cx in enumerate((64, 82, 100)):
        d.ellipse([cx - 5, 105, cx + 5, 115], fill=(56, 68, 80))
    blurred_code(d, 68, 142, 330, 11)

    # memory slots, right
    sx, sy = 560, 118
    for r in range(4):
        for c in range(3):
            x = sx + c * 128
            y = sy + r * 56
            rejected = (r, c) in {(0, 0), (1, 2), (3, 1)}
            col = HOT if rejected else COOL
            d.rounded_rectangle([x, y, x + 108, y + 40], radius=7,
                                fill=(26, 33, 42), outline=col, width=2)
            blurred_code(d, x + 12, y + 12, 84, 1, colour=col, seed=r + c)
            if rejected:
                d.line([x + 88, y + 12, x + 98, y + 28], fill=HOT, width=3)
                d.line([x + 98, y + 12, x + 88, y + 28], fill=HOT, width=3)

    # cards drifting from editor to bank
    for i, (x, y, s) in enumerate([(452, 180, 26), (492, 208, 20), (524, 166, 16)]):
        d.rounded_rectangle([x, y, x + s + 18, y + s], radius=4,
                            fill=(30, 38, 48), outline=HOT if i == 0 else COOL, width=2)

    t = "What it remembers is what you turned down"
    tf = fit(d, t, UI_B, 30, W - 120)
    d.text((44, 40), t, font=tf, fill=INK)
    d.rectangle([44, 372, 118, 377], fill=HOT)
    d.text((44, 388), "code review with persistent memory", font=F(UI, 18), fill=DIM)
    return img


def cover_ab() -> Image.Image:
    """Two identical-looking runs that were not the same run."""
    img, d = base()

    for i, (x, colour, label) in enumerate([(52, COOL, "RUN A"), (516, HOT, "RUN B")]):
        d.rounded_rectangle([x, 110, x + 432, 344], radius=12, fill=PANEL,
                            outline=colour, width=2)
        d.rectangle([x, 110, x + 432, 138], fill=(28, 35, 44))
        d.text((x + 18, 116), label, font=F(MONO, 16), fill=colour)
        blurred_code(d, x + 24, 156, 380, 10, colour=FAINT, seed=0)
        # the tell: one bar in the right-hand run sits offset and in the accent colour
        if i == 1:
            d.rounded_rectangle([x + 24 + 46, 156 + 4 * 17, x + 24 + 46 + 250, 156 + 4 * 17 + 7],
                                radius=3, fill=HOT)

    # seam
    d.line([(W // 2, 96), (W // 2, 358)], fill=(48, 58, 70), width=2)

    t = "Identical, until you check what ran"
    tf = fit(d, t, UI_B, 30, W - 120)
    d.text((52, 44), t, font=tf, fill=INK)
    d.rectangle([52, 372, 126, 377], fill=HOT)
    d.text((52, 388), "a before/after test with a hidden variable", font=F(UI, 18), fill=DIM)
    return img


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "docs"
    cover_memory().save(out / "cover-team-lead.png")
    cover_ab().save(out / "cover-team-member.png")
    print(f"wrote {out/'cover-team-lead.png'} and {out/'cover-team-member.png'}  ({W}x{H})")
