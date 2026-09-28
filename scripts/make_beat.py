"""Synthesise a phonk-style backing track. Everything here is generated from maths,
so there is nothing to licence and nothing for Content ID to claim.

    python scripts/make_beat.py --bpm 150 --bars 40 --out docs/track.wav

Drift phonk ingredients: a long 808 sub that slides, a cowbell melody, tight hats
with occasional rolls, and a hard kick on the downbeat.
"""

from __future__ import annotations

import argparse
import math
import struct
import wave
from pathlib import Path

import numpy as np

SR = 44100


def _env(n: int, attack: float, decay: float, power: float = 2.0) -> np.ndarray:
    a = max(1, int(attack * SR))
    e = np.ones(n)
    e[:a] = np.linspace(0, 1, a)
    d = np.linspace(1, 0, max(1, n - a)) ** power
    e[a:] = d[: n - a]
    return e


def kick(dur=0.42, f0=125.0, f1=44.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 26)
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR)
    click = np.random.default_rng(1).normal(0, 1, n) * np.exp(-t * 420) * 0.25
    return np.tanh((sig * _env(n, 0.001, dur, 1.6) + click) * 1.7) * 0.92


def sub808(note_hz: float, dur: float, glide_from: float | None = None) -> np.ndarray:
    """The 808: a sine an octave down with soft saturation, optionally sliding in."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    if glide_from:
        f = note_hz + (glide_from - note_hz) * np.exp(-t * 16)
    else:
        f = np.full(n, note_hz)
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return np.tanh(sig * 1.9) * _env(n, 0.004, dur, 1.1) * 0.55


def cowbell(freq: float, dur=0.19) -> np.ndarray:
    """Two detuned squares through a short envelope: the phonk cowbell."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    a = np.sign(np.sin(2 * np.pi * freq * t))
    b = np.sign(np.sin(2 * np.pi * freq * 1.503 * t))
    return (a * 0.6 + b * 0.4) * _env(n, 0.001, dur, 3.4) * 0.17


def hat(dur=0.05, bright=1.0) -> np.ndarray:
    n = int(dur * SR)
    noise = np.random.default_rng().normal(0, 1, n)
    # crude high-pass: difference of the signal emphasises the top end
    hp = np.diff(np.concatenate([[0], noise]))
    return hp * _env(n, 0.0005, dur, 4.0) * 0.12 * bright


def snare(dur=0.2) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = np.random.default_rng(7).normal(0, 1, n)
    tone = np.sin(2 * np.pi * 185 * t) * 0.35
    return (noise * 0.7 + tone) * _env(n, 0.001, dur, 3.0) * 0.30


def place(buf: np.ndarray, sig: np.ndarray, at: float) -> None:
    i = int(at * SR)
    end = min(len(buf), i + len(sig))
    if i < len(buf):
        buf[i:end] += sig[: end - i]


# A minor-ish set of cowbell pitches, in Hz.
MELODY = [440.0, 523.25, 392.0, 440.0, 349.23, 392.0, 329.63, 392.0]
BASS = [55.0, 55.0, 43.65, 49.0]


def build(bpm: float, bars: int) -> np.ndarray:
    beat = 60.0 / bpm
    bar = beat * 4
    total = bar * bars + 2.0
    buf = np.zeros(int(total * SR))

    for b in range(bars):
        t0 = b * bar
        section = b // 8            # 8-bar sections
        busy = section >= 1         # the intro bar keeps it sparse

        # kick: downbeat plus a syncopated pickup once the track opens up
        place(buf, kick(), t0)
        if busy:
            place(buf, kick(), t0 + beat * 2.5)
        if b % 4 == 3:
            place(buf, kick(), t0 + beat * 3.5)

        # snare on 2 and 4
        if busy:
            place(buf, snare(), t0 + beat)
            place(buf, snare(), t0 + beat * 3)

        # 808 following the bass line, sliding into the bar
        root = BASS[b % len(BASS)]
        place(buf, sub808(root, bar * 0.62, glide_from=root * 1.5), t0)
        if busy:
            place(buf, sub808(root * 1.335, bar * 0.28), t0 + beat * 2.5)

        # hats: eighths, with sixteenth rolls at the end of every fourth bar
        if busy:
            for i in range(8):
                place(buf, hat(bright=1.0 if i % 2 == 0 else 0.65), t0 + i * beat / 2)
            if b % 4 == 3:
                for i in range(8):
                    place(buf, hat(0.035, 0.8), t0 + beat * 3 + i * beat / 8)

        # cowbell melody, one note per beat from the second section
        if section >= 1:
            for i in range(4):
                idx = (b * 4 + i) % len(MELODY)
                if (b * 4 + i) % 8 in (0, 2, 3, 5, 6):
                    place(buf, cowbell(MELODY[idx]), t0 + i * beat)

    # gentle master bus: soft clip then normalise
    buf = np.tanh(buf * 1.15)
    buf /= max(1e-9, np.max(np.abs(buf))) / 0.89
    return buf


def write_wav(path: Path, mono: np.ndarray) -> None:
    stereo = np.stack([mono, mono], axis=1)
    pcm = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bpm", type=float, default=150.0)
    ap.add_argument("--bars", type=int, default=40)
    ap.add_argument("--out", type=Path, default=Path("docs/track.wav"))
    a = ap.parse_args()
    audio = build(a.bpm, a.bars)
    write_wav(a.out, audio)
    print(f"wrote {a.out}  {len(audio)/SR:.1f}s at {a.bpm:g} BPM ({a.bars} bars)")
