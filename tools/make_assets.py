"""Erzeugt die Sound-/Musik-Dateien und das Icon fuer Ru-Curve.

    python tools/make_assets.py

Alles wird prozedural mit numpy erzeugt - keine externen Rohdateien noetig.
"""

from __future__ import annotations

import os
import struct
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SND = os.path.join(ROOT, "assets", "sounds")
MUS = os.path.join(ROOT, "assets", "music")
SR = 44100


def _write_wav(path: str, stereo: np.ndarray) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = np.clip(stereo, -1.0, 1.0)
    pcm = (data * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("  ", os.path.relpath(path, ROOT))


def _stereo(mono: np.ndarray) -> np.ndarray:
    return np.column_stack([mono, mono])


def _env(n: int, attack=0.01, release=0.2) -> np.ndarray:
    e = np.ones(n)
    a = int(SR * attack)
    r = int(SR * release)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] = np.linspace(1, 0, r)
    return e


def _tone(freq, dur, kind="sine"):
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    if kind == "square":
        return np.sign(np.sin(2 * np.pi * freq * t))
    if kind == "saw":
        return 2 * (t * freq - np.floor(0.5 + t * freq))
    return np.sin(2 * np.pi * freq * t)


# --------------------------------------------------------------------------- #
def sfx_click():
    m = _tone(1250, 0.05) * _env(int(SR * 0.05), 0.002, 0.045) * 0.35
    _write_wav(os.path.join(SND, "click.wav"), _stereo(m))


def sfx_countdown():
    m = _tone(680, 0.13) * _env(int(SR * 0.13), 0.005, 0.1) * 0.4
    _write_wav(os.path.join(SND, "countdown.wav"), _stereo(m))


def sfx_go():
    n = int(SR * 0.35)
    e = _env(n, 0.005, 0.28)
    m = (_tone(880, 0.35) + 0.6 * _tone(1320, 0.35)) * e * 0.33
    _write_wav(os.path.join(SND, "go.wav"), _stereo(m))


def sfx_powerup():
    dur = 0.28
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    sweep = np.sin(2 * np.pi * (240 + (900 - 240) * (t / dur) ** 1.5) * t)
    m = sweep * _env(len(t), 0.005, 0.2) * 0.35
    _write_wav(os.path.join(SND, "powerup.wav"), _stereo(m))


def sfx_crash():
    dur = 0.35
    n = int(SR * dur)
    rng = np.random.default_rng(7)
    noise = rng.uniform(-1, 1, n)
    # simpler Tiefpass
    for _ in range(4):
        noise = np.convolve(noise, np.ones(6) / 6, mode="same")
    t = np.linspace(0, dur, n, endpoint=False)
    thud = np.sin(2 * np.pi * np.linspace(180, 60, n) * t)
    m = (0.7 * noise + 0.6 * thud) * _env(n, 0.001, 0.32) * 0.5
    _write_wav(os.path.join(SND, "crash.wav"), _stereo(m))


def sfx_win():
    notes = [523.25, 659.25, 783.99, 1046.5]
    parts = []
    for i, f in enumerate(notes):
        d = 0.16 if i < 3 else 0.4
        parts.append(_tone(f, d) * _env(int(SR * d), 0.005, d * 0.8) * 0.33)
    _write_wav(os.path.join(SND, "win.wav"), _stereo(np.concatenate(parts)))


# --------------------------------------------------------------------------- #
def music_menu():
    dur = 8.0
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    chord = [110.0, 164.81, 220.0, 277.18]  # A-moll-ish Pad
    m = np.zeros_like(t)
    for f in chord:
        m += np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)
    trem = 0.8 + 0.2 * np.sin(2 * np.pi * 0.15 * t)
    m = m / len(chord) * trem
    # sanfter Loop-Crossfade
    fade = int(SR * 0.4)
    m[:fade] *= np.linspace(0, 1, fade)
    m[-fade:] *= np.linspace(1, 0, fade)
    _write_wav(os.path.join(MUS, "menu.wav"), _stereo(m * 0.22))


def music_game():
    bpm = 124
    beat = 60.0 / bpm
    seq = [220.0, 261.63, 329.63, 261.63, 246.94, 329.63, 392.0, 329.63]
    step = beat / 2
    parts = []
    for i in range(32):
        f = seq[i % len(seq)]
        d = step
        n = int(SR * d)
        tt = np.linspace(0, d, n, endpoint=False)
        note = (np.sign(np.sin(2 * np.pi * f * tt)) * 0.3 + np.sin(2 * np.pi * f * tt))
        bass = 0.5 * np.sin(2 * np.pi * (f / 2) * tt)
        parts.append((note + bass) * _env(n, 0.004, d * 0.6))
    m = np.concatenate(parts)
    fade = int(SR * 0.2)
    m[:fade] *= np.linspace(0, 1, fade)
    m[-fade:] *= np.linspace(1, 0, fade)
    _write_wav(os.path.join(MUS, "game.wav"), _stereo(m * 0.16))


# --------------------------------------------------------------------------- #
def make_icon():
    try:
        import pygame
    except ImportError:
        print("  (pygame fehlt - Icon uebersprungen)")
        return
    pygame.init()
    size = 256
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(surf, (18, 20, 28), (0, 0, size, size), border_radius=48)
    pts = []
    import math

    for i in range(120):
        a = i / 120 * math.pi * 2.4
        r = 30 + i * 0.7
        pts.append((size / 2 + math.cos(a) * r, size / 2 + math.sin(a) * r * 0.7))
    if len(pts) > 1:
        pygame.draw.lines(surf, (54, 122, 246), False, pts, 14)
    pygame.draw.circle(surf, (232, 76, 61), (int(pts[-1][0]), int(pts[-1][1])), 12)
    png = os.path.join(ROOT, "assets", "icon.png")
    pygame.image.save(surf, png)
    print("  ", os.path.relpath(png, ROOT))
    try:
        ico = os.path.join(ROOT, "icon.ico")
        small = pygame.transform.smoothscale(surf, (64, 64))
        pygame.image.save(small, ico)
        print("  ", os.path.relpath(ico, ROOT))
    except Exception as exc:  # pragma: no cover
        print("  ico:", exc)


def main():
    print("Sounds:")
    for fn in (sfx_click, sfx_countdown, sfx_go, sfx_powerup, sfx_crash, sfx_win):
        fn()
    print("Musik:")
    music_menu()
    music_game()
    print("Icon:")
    make_icon()


if __name__ == "__main__":
    main()
