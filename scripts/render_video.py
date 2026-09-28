"""Render the demo transcript straight to an MP4. No screen recording involved.

Draws each frame with Pillow and pipes raw frames to the ffmpeg binary that ships with
imageio-ffmpeg, so nothing has to be installed system-wide.

    python scripts/render_video.py --speed 1.4 --out docs/memolint-demo.mp4

The output is silent on purpose: add music and voice in an editor, or use
scripts/make_voiceover.py first and pass --audio.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

W, H, FPS = 1920, 1080, 30
BG = (10, 13, 18)
CHROME_BG = (18, 23, 30)
LINE_COL = (38, 47, 58)
DIM = (151, 163, 176)
FAINT = (93, 106, 119)
INK = (238, 241, 244)
HOT = (255, 106, 61)
COOL = (90, 209, 196)

PAD_X, TOP = 74, 132
MONO = "C:/Windows/Fonts/consola.ttf"
MONO_B = "C:/Windows/Fonts/consolab.ttf"
UI_B = "C:/Windows/Fonts/segoeuib.ttf"
UI = "C:/Windows/Fonts/segoeui.ttf"

BEATS = json.loads((ROOT / "scripts" / "beats.json").read_text(encoding="utf-8"))


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def beat_for(n: int) -> dict:
    cur = BEATS[0]
    for b in BEATS:
        if n >= b["from"]:
            cur = b
    return cur


class Renderer:
    def __init__(self, font_size: int = 25):
        self.mono = font(MONO, font_size)
        self.mono_b = font(MONO_B, font_size)
        self.cap = font(UI_B, 58)
        self.chrome = font(MONO, 22)
        self.badge = font(MONO_B, 22)
        self.title = font(UI_B, 96)
        self.sub = font(UI, 40)
        self.small = font(UI, 30)
        self.lh = int(font_size * 1.52)
        self.char_w = self.mono.getlength("M")
        self.rows = (H - TOP - 210) // self.lh

    def base(self) -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 64], fill=CHROME_BG)
        d.line([(0, 64), (W, 64)], fill=LINE_COL)
        for i, x in enumerate((44, 76, 108)):
            d.ellipse([x - 9, 23, x + 9, 41], fill=(48, 59, 71))
        d.text((150, 22), "memolint demo", font=self.chrome, fill=FAINT)
        return img

    def draw_screen(self, img: Image.Image, visible: list) -> None:
        d = ImageDraw.Draw(img)
        y = TOP
        for ln in visible:
            x = PAD_X
            for sp in ln["s"]:
                f = self.mono_b if sp["b"] else self.mono
                col = _hex(sp["c"]) if sp["c"] else INK
                d.text((x, y), sp["t"], font=f, fill=col)
                x += self.char_w * len(sp["t"])
            y += self.lh

    def draw_caption(self, img: Image.Image, text: str, fade: float = 1.0) -> None:
        d = ImageDraw.Draw(img)
        grad = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for i in range(300):
            gd.line([(0, i), (W, i)], fill=(6, 9, 13, int(240 * (i / 300) ** 1.4)))
        img.paste(Image.alpha_composite(img.crop((0, H - 300, W, H)).convert("RGBA"), grad).convert("RGB"),
                  (0, H - 300))
        d = ImageDraw.Draw(img)
        off = int((1 - fade) * 22)
        col = tuple(int(c * fade + BG[k] * (1 - fade)) for k, c in enumerate(INK))
        d.text((PAD_X, H - 172 + off), text, font=self.cap, fill=col)
        d.rectangle([PAD_X, H - 92 + off, PAD_X + 84, H - 87 + off], fill=HOT)

    def draw_badge(self, img: Image.Image, text: str, on: bool) -> None:
        d = ImageDraw.Draw(img)
        w = int(d.textlength(text, font=self.badge)) + 34
        x0, y0 = W - PAD_X - w, 92
        col = COOL if on else HOT
        d.rounded_rectangle([x0, y0, x0 + w, y0 + 46], radius=6, fill=(12, 16, 22), outline=col, width=2)
        d.text((x0 + 17, y0 + 10), text, font=self.badge, fill=col)

    def card(self, title: str, sub: str, foot: str = "") -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.text((PAD_X + 40, H // 2 - 130), title, font=self.title, fill=INK)
        d.rectangle([PAD_X + 44, H // 2 - 8, PAD_X + 44 + 120, H // 2 - 1], fill=HOT)
        d.text((PAD_X + 40, H // 2 + 36), sub, font=self.sub, fill=DIM)
        if foot:
            d.text((PAD_X + 40, H - 150), foot, font=self.small, fill=FAINT)
        return img


def _hex(c: str) -> tuple[int, int, int]:
    if c.startswith("rgb("):
        return tuple(int(v) for v in c[4:-1].split(","))  # type: ignore[return-value]
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def render(speed: float, out: Path, audio: Path | None, font_size: int) -> None:
    data = json.loads((ROOT / "preview_data.json").read_text(encoding="utf-8"))
    lines = data["lines"]
    r = Renderer(font_size)

    ff = __import__("imageio_ffmpeg").get_ffmpeg_exe()
    cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert proc.stdin

    def push(img: Image.Image, seconds: float) -> None:
        buf = img.tobytes()
        for _ in range(max(1, round(seconds * FPS))):
            proc.stdin.write(buf)

    # Title card
    push(r.card("Memolint", "A code reviewer that remembers your team's precedents.",
                "Built on Hindsight agent memory"), 2.6)

    visible: list = []
    last_caption, frames_since_cut = None, 99
    total = 0.0
    for idx, ln in enumerate(lines):
        visible.append(ln)
        if len(visible) > r.rows:
            visible = visible[-r.rows:]
        b = beat_for(idx)
        dur = ln["d"] * 1.4 / speed
        total += dur

        img = r.base()
        r.draw_screen(img, visible)
        if b["caption"] != last_caption:
            last_caption, frames_since_cut = b["caption"], 0
        if b.get("badge"):
            r.draw_badge(img, b["badge"], b["badge"] == "memory on")

        n_frames = max(1, round(dur * FPS))
        for f in range(n_frames):
            frame = img
            if frames_since_cut < 9:  # caption animates in over ~0.3s
                frame = img.copy()
                r.draw_caption(frame, b["caption"], fade=min(1.0, 0.25 + frames_since_cut * 0.1))
            else:
                frame = img.copy()
                r.draw_caption(frame, b["caption"], fade=1.0)
            proc.stdin.write(frame.tobytes())
            frames_since_cut += 1

    push(r.card("The model is stateless.", "The memory is not.",
                "github.com/sasichandan23/trial-1"), 3.4)

    proc.stdin.close()
    proc.wait()
    print(f"wrote {out}  ({total + 6:.0f}s of video)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=float, default=1.4)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "memolint-demo.mp4")
    ap.add_argument("--audio", type=Path, default=None)
    ap.add_argument("--font-size", type=int, default=25)
    a = ap.parse_args()
    render(a.speed, a.out, a.audio, a.font_size)
