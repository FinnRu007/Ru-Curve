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
#  Turnier-Sounds
# --------------------------------------------------------------------------- #
def _brass(freq, dur, detune=0.004):
    """Trompeten-artiger Ton: Saegezahn-Obertoene + leichtes Vibrato."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    vib = 1.0 + 0.006 * np.sin(2 * np.pi * 5.5 * t)
    out = np.zeros_like(t)
    for k, amp in enumerate((1.0, 0.62, 0.42, 0.26, 0.16, 0.09), start=1):
        out += amp * np.sin(2 * np.pi * freq * k * vib * t)
        out += amp * 0.5 * np.sin(2 * np.pi * freq * k * (1 + detune) * t)
    out /= np.max(np.abs(out)) + 1e-9
    # weicher Anblas-Einsatz
    att = int(SR * min(0.05, dur * 0.25))
    env = np.ones_like(t)
    env[:att] = np.linspace(0, 1, att) ** 0.6
    rel = int(SR * min(0.18, dur * 0.5))
    env[-rel:] *= np.linspace(1, 0, rel) ** 1.4
    return out * env


def sfx_fanfare():
    """Kurze Trompeten-Fanfare fuer Ergebnisse und den Turniersieg."""
    g, c, e = 392.00, 523.25, 659.25
    parts = [
        _brass(g, 0.15), _brass(g, 0.13), _brass(g, 0.13),
        _brass(c, 0.30), _brass(e, 0.22), _brass(c * 1.5, 0.60),
    ]
    m = np.concatenate(parts) * 0.40
    _write_wav(os.path.join(SND, "fanfare.wav"), _stereo(m))


def sfx_whistle():
    """Anpfiff - kurzer Triller."""
    dur = 0.55
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    trill = 2100 + 120 * np.sin(2 * np.pi * 22 * t)
    m = np.sin(2 * np.pi * trill * t) + 0.35 * np.sin(2 * np.pi * 2 * trill * t)
    rng = np.random.default_rng(3)
    m += 0.10 * rng.uniform(-1, 1, len(t))
    m *= _env(len(t), 0.02, 0.16) * 0.30
    _write_wav(os.path.join(SND, "whistle.wav"), _stereo(m))


def sfx_tick():
    m = _tone(1750, 0.035, "square") * _env(int(SR * 0.035), 0.001, 0.03) * 0.16
    _write_wav(os.path.join(SND, "tick.wav"), _stereo(m))


def sfx_correct():
    parts = [_tone(880, 0.09), _tone(1318.5, 0.16)]
    m = np.concatenate([p * _env(len(p), 0.004, len(p) / SR * 0.7) for p in parts]) * 0.32
    _write_wav(os.path.join(SND, "correct.wav"), _stereo(m))


def sfx_wrong():
    m = _tone(196, 0.24, "square") * _env(int(SR * 0.24), 0.004, 0.2) * 0.26
    _write_wav(os.path.join(SND, "wrong.wav"), _stereo(m))


def sfx_applause():
    """Applaus: gefilterte Rauschstoesse."""
    dur = 1.8
    n = int(SR * dur)
    rng = np.random.default_rng(11)
    noise = rng.uniform(-1, 1, n)
    for _ in range(2):
        noise = np.convolve(noise, np.ones(4) / 4, mode="same")
    claps = np.zeros(n)
    pos = 0
    while pos < n:
        w = rng.integers(200, 900)
        end = min(n, pos + w)
        claps[pos:end] += noise[pos:end] * rng.uniform(0.4, 1.0)
        pos += int(rng.integers(300, 1400))
    swell = np.minimum(1.0, np.linspace(0, 3, n)) * np.linspace(1, 0.2, n)
    m = claps * swell * 0.30
    _write_wav(os.path.join(SND, "applause.wav"), _stereo(m))


# --------------------------------------------------------------------------- #
def _unused_music_menu():
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


def _unused_music_game():
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
def _draw_icon(pygame, size):
    import math

    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(surf, (18, 20, 28), (0, 0, size, size),
                     border_radius=max(2, size // 5))
    pts = []
    n = 120
    for i in range(n):
        a = i / n * math.pi * 2.4
        r = size * (0.12 + i / n * 0.30)
        pts.append((size / 2 + math.cos(a) * r, size / 2 + math.sin(a) * r * 0.72))
    if len(pts) > 1:
        pygame.draw.lines(surf, (54, 122, 246), False, pts, max(2, size // 18))
    pygame.draw.circle(surf, (232, 76, 61), (int(pts[-1][0]), int(pts[-1][1])),
                       max(2, size // 20))
    return surf


def _png_bytes(pygame, surf):
    import io

    buf = io.BytesIO()
    pygame.image.save(surf, buf, "icon.png")
    return buf.getvalue()


def make_icon():
    try:
        import pygame
    except ImportError:
        print("  (pygame fehlt - Icon uebersprungen)")
        return
    pygame.init()

    big = _draw_icon(pygame, 256)
    png = os.path.join(ROOT, "assets", "icon.png")
    pygame.image.save(big, png)
    print("  ", os.path.relpath(png, ROOT))

    # gueltige .ico-Datei: ICONDIR + ICONDIRENTRYs + PNG-Bloecke (Windows Vista+)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    blobs = [_png_bytes(pygame, _draw_icon(pygame, s)) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for s, blob in zip(sizes, blobs):
        dim = 0 if s >= 256 else s
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    ico = os.path.join(ROOT, "icon.ico")
    with open(ico, "wb") as fh:
        fh.write(header + entries + b"".join(blobs))
    print("  ", os.path.relpath(ico, ROOT))


def main():
    print("Sounds:")
    for fn in (sfx_click, sfx_countdown, sfx_go, sfx_powerup, sfx_crash, sfx_win,
               sfx_fanfare, sfx_whistle, sfx_tick, sfx_correct, sfx_wrong,
               sfx_applause):
        fn()
    print("Icon:")
    make_icon()


if __name__ == "__main__":
    main()
