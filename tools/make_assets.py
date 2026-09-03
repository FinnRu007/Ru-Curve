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
#  Klangwerkzeuge
#
#  Die erste Fassung der Sounds war schlicht zu laut und zu schrill. Gemessen:
#  Spitzen bis 0.50, und beim Anpfiff lagen 75 % der Energie ueber 2 kHz -
#  genau der Bereich, der im Ohr weh tut. Dazu Einsaetze von unter 2 ms, die
#  als Knacken hoerbar sind, und Rechteckwellen mit ihren harten Obertoenen.
#
#  Die Werkzeuge hier drehen genau daran:
#    * `_lowpass`  nimmt die Schaerfe raus
#    * `_soft_env` gibt jedem Ton einen weichen Einsatz statt eines Knacks
#    * `_partials` baut Klaenge additiv mit schnell abfallenden Obertoenen
#    * `_space`    haengt ein paar leise Wiederholungen an - klingt weiter weg
#    * `_finish`   setzt am Ende einen festen, niedrigen Spitzenpegel
# --------------------------------------------------------------------------- #
def _lowpass(x: np.ndarray, cutoff: float, order: int = 2) -> np.ndarray:
    """Einfacher Tiefpass (mehrfach angewandtes Ein-Pol-Filter)."""
    dt = 1.0 / SR
    rc = 1.0 / (2 * np.pi * max(20.0, cutoff))
    a = dt / (rc + dt)
    out = x
    for _ in range(max(1, order)):
        y = np.empty_like(out)
        acc = 0.0
        for i in range(len(out)):          # bewusst schlicht: laeuft einmalig
            acc += a * (out[i] - acc)
            y[i] = acc
        out = y
    return out


def _soft_env(n: int, attack=0.012, hold=0.0, curve=3.0) -> np.ndarray:
    """Weicher Einsatz, danach exponentiell abfallend.

    Der Einsatz laeuft ueber eine Kosinusflanke - linear reicht nicht, man
    hoert die Ecke am Ende der Rampe noch als leises Knacken.
    """
    e = np.ones(n)
    a = min(n, int(SR * attack))
    if a > 1:
        e[:a] = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, a))
    h = min(n - a, int(SR * hold))
    rest = n - a - h
    if rest > 0:
        e[a + h:] = np.exp(-curve * np.linspace(0, 1, rest))
    return e


def _partials(freq, dur, amps=(1.0, 0.28, 0.10), detune=0.0):
    """Additiver Ton. Die Obertoene fallen bewusst schnell ab."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    out = np.zeros_like(t)
    for k, amp in enumerate(amps, start=1):
        out += amp * np.sin(2 * np.pi * freq * k * t)
        if detune:
            out += amp * 0.5 * np.sin(2 * np.pi * freq * k * (1 + detune) * t)
    return out / (np.max(np.abs(out)) + 1e-9)


def _glide(f0, f1, dur, curve=1.0):
    """Gleitender Ton von f0 nach f1 - ohne Phasenspruenge."""
    n = int(SR * dur)
    t = np.linspace(0, dur, n, endpoint=False)
    f = f0 + (f1 - f0) * (t / dur) ** curve
    phase = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(phase)


def _space(x: np.ndarray, amount=0.25, taps=((0.055, 0.6), (0.11, 0.35),
                                             (0.19, 0.18))):
    """Ein paar leise Wiederholungen - laesst den Klang weicher wirken."""
    out = np.copy(x)
    extra = int(SR * 0.35)
    out = np.concatenate([out, np.zeros(extra)])
    for delay, gain in taps:
        d = int(SR * delay)
        if d < len(out):
            out[d:d + len(x)] += x * gain * amount
    return out


def _finish(m: np.ndarray, peak: float) -> np.ndarray:
    """Auf einen festen Spitzenpegel bringen und die Enden sauber ausblenden."""
    m = np.asarray(m, dtype=float)
    top = np.max(np.abs(m))
    if top > 1e-9:
        m = m * (peak / top)
    edge = min(len(m) // 8, int(SR * 0.008))
    if edge > 1:
        m[:edge] *= np.linspace(0, 1, edge)
        m[-edge:] *= np.linspace(1, 0, edge)
    return m


def _seq(notes, gap=0.0):
    """Toene hintereinander, mit optionaler Ueberlappung (gap < 0)."""
    if gap >= 0:
        parts = []
        for i, nte in enumerate(notes):
            parts.append(nte)
            if gap and i < len(notes) - 1:
                parts.append(np.zeros(int(SR * gap)))
        return np.concatenate(parts)
    step = int(SR * -gap)
    total = sum(len(n) for n in notes) - step * (len(notes) - 1)
    out = np.zeros(max(total, 1))
    pos = 0
    for nte in notes:
        out[pos:pos + len(nte)] += nte
        pos += max(1, len(nte) - step)
    return out


# --------------------------------------------------------------------------- #
#  Die einzelnen Klaenge - alle bewusst leise und ohne scharfe Hoehen
# --------------------------------------------------------------------------- #
def sfx_click():
    """Klick im Menue. Soll man kaum bemerken."""
    d = 0.045
    m = _partials(520, d, (1.0, 0.22)) * _soft_env(int(SR * d), 0.006, curve=6)
    _write_wav(os.path.join(SND, "click.wav"),
               _stereo(_finish(_lowpass(m, 2400), 0.11)))


def sfx_countdown():
    """Drei, zwei, eins - ein warmer Ton, kein Piepen."""
    d = 0.16
    m = _partials(392, d, (1.0, 0.25, 0.08)) * _soft_env(int(SR * d), 0.012, 0.03)
    _write_wav(os.path.join(SND, "countdown.wav"),
               _stereo(_finish(_lowpass(m, 2000), 0.14)))


def sfx_go():
    """Los! Zwei Toene aufwaerts, ineinander uebergehend."""
    a = _partials(523.25, 0.16, (1.0, 0.3, 0.1)) * _soft_env(int(SR * 0.16), 0.01, 0.02)
    b = _partials(783.99, 0.34, (1.0, 0.26, 0.08)) * _soft_env(int(SR * 0.34), 0.014, 0.04)
    m = _space(_seq([a, b], gap=-0.05), 0.22)
    _write_wav(os.path.join(SND, "go.wav"),
               _stereo(_finish(_lowpass(m, 2600), 0.17)))


def sfx_powerup():
    """Powerup: sanft aufwaerts gleitend, mit leichtem Schweben."""
    d = 0.34
    t = np.linspace(0, d, int(SR * d), endpoint=False)
    m = _glide(330, 660, d, curve=1.4) * (1.0 + 0.12 * np.sin(2 * np.pi * 6 * t))
    m += 0.25 * _glide(660, 1320, d, curve=1.4)
    m *= _soft_env(len(t), 0.018, 0.05, curve=3.5)
    _write_wav(os.path.join(SND, "powerup.wav"),
               _stereo(_finish(_lowpass(m, 2600), 0.14)))


def sfx_crash():
    """Zusammenstoss. Faellt bei Sumo und Ernte staendig an - deshalb kurz,
    dumpf und leise. Ein heller Knall waere hier eine Zumutung."""
    d = 0.20
    n = int(SR * d)
    rng = np.random.default_rng(7)
    noise = _lowpass(rng.uniform(-1, 1, n), 600, order=3)
    t = np.linspace(0, d, n, endpoint=False)
    thump = np.sin(2 * np.pi * np.cumsum(np.linspace(120, 55, n)) / SR)
    m = (0.55 * noise / (np.max(np.abs(noise)) + 1e-9) + 0.9 * thump)
    m *= _soft_env(n, 0.004, 0.01, curve=5.0)
    _write_wav(os.path.join(SND, "crash.wav"),
               _stereo(_finish(_lowpass(m, 900), 0.16)))


def sfx_win():
    """Rundensieg: ein ruhiger Dreiklang mit Nachhall."""
    notes = []
    for f, d in ((523.25, 0.18), (659.25, 0.18), (783.99, 0.18), (1046.5, 0.5)):
        notes.append(_partials(f, d, (1.0, 0.3, 0.09))
                     * _soft_env(int(SR * d), 0.014, 0.04, curve=3.0))
    m = _space(_seq(notes, gap=-0.04), 0.3)
    _write_wav(os.path.join(SND, "win.wav"),
               _stereo(_finish(_lowpass(m, 2600), 0.18)))


# --------------------------------------------------------------------------- #
def _horn(freq, dur, detune=0.005):
    """Weiches Blasinstrument. Die alte Fassung hatte sechs Obertoene in
    voller Staerke - das klang nach Blechtrompete direkt am Ohr. Drei
    reichen, und sie fallen deutlich schneller ab."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    vib = 1.0 + 0.004 * np.sin(2 * np.pi * 5.0 * t)
    out = np.zeros_like(t)
    for k, amp in enumerate((1.0, 0.34, 0.13, 0.05), start=1):
        out += amp * np.sin(2 * np.pi * freq * k * vib * t)
        out += amp * 0.4 * np.sin(2 * np.pi * freq * k * (1 + detune) * t)
    out /= np.max(np.abs(out)) + 1e-9
    env = _soft_env(len(t), min(0.045, dur * 0.3), hold=dur * 0.35, curve=2.4)
    return out * env


def sfx_fanfare():
    """Fanfare fuer Ergebnisse und den Turniersieg - warm statt schmetternd."""
    g, c, e = 392.00, 523.25, 659.25
    parts = [_horn(g, 0.18), _horn(g, 0.16), _horn(g, 0.16),
             _horn(c, 0.34), _horn(e, 0.26), _horn(c * 1.5, 0.72)]
    m = _space(_seq(parts, gap=-0.03), 0.35)
    _write_wav(os.path.join(SND, "fanfare.wav"),
               _stereo(_finish(_lowpass(m, 2200), 0.19)))


def sfx_whistle():
    """Anpfiff. Faellt bei der Jagd bei JEDEM Fangen an - die alte Fassung
    lag mit 2100 Hz plus Oberton genau im schmerzhaften Bereich (75 % der
    Energie ueber 2 kHz). Jetzt tiefer, kurz und ohne Rauschanteil."""
    d = 0.26
    t = np.linspace(0, d, int(SR * d), endpoint=False)
    f = 880 + 40 * np.sin(2 * np.pi * 11 * t)
    m = np.sin(2 * np.pi * np.cumsum(f) / SR)
    m += 0.18 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    m *= _soft_env(len(t), 0.02, 0.06, curve=4.0)
    _write_wav(os.path.join(SND, "whistle.wav"),
               _stereo(_finish(_lowpass(m, 1800), 0.13)))


def sfx_tick():
    """Sekundenticken - so leise wie moeglich, es laeuft im Hintergrund mit."""
    d = 0.03
    m = _partials(660, d, (1.0, 0.15)) * _soft_env(int(SR * d), 0.004, curve=7)
    _write_wav(os.path.join(SND, "tick.wav"),
               _stereo(_finish(_lowpass(m, 1800), 0.07)))


def sfx_correct():
    """Richtig geantwortet: zwei freundliche Toene aufwaerts."""
    a = _partials(659.25, 0.10, (1.0, 0.22)) * _soft_env(int(SR * 0.10), 0.008, 0.02)
    b = _partials(987.77, 0.20, (1.0, 0.18)) * _soft_env(int(SR * 0.20), 0.010, 0.03)
    m = _seq([a, b], gap=-0.03)
    _write_wav(os.path.join(SND, "correct.wav"),
               _stereo(_finish(_lowpass(m, 2400), 0.13)))


def sfx_wrong():
    """Falsch: zwei tiefe Toene abwaerts. Bewusst KEIN Rechteck mehr - dessen
    harte Obertoene waren fast die Haelfte der Energie."""
    a = _partials(261.63, 0.13, (1.0, 0.2)) * _soft_env(int(SR * 0.13), 0.010, 0.02)
    b = _partials(196.00, 0.26, (1.0, 0.16)) * _soft_env(int(SR * 0.26), 0.012, 0.04)
    m = _seq([a, b], gap=-0.02)
    _write_wav(os.path.join(SND, "wrong.wav"),
               _stereo(_finish(_lowpass(m, 1300), 0.12)))


def sfx_applause():
    """Applaus: bandbegrenztes Rauschen. Ungefiltert klingt es wie Zischen -
    echtes Klatschen hat kaum Energie ueber 2 kHz."""
    d = 1.5
    n = int(SR * d)
    rng = np.random.default_rng(11)
    noise = _lowpass(rng.uniform(-1, 1, n), 1600, order=2)
    noise = noise - _lowpass(noise, 220, order=1)      # Tiefen weg
    claps = np.zeros(n)
    pos = 0
    while pos < n:
        w = int(rng.integers(300, 1100))
        end = min(n, pos + w)
        seg = noise[pos:end] * rng.uniform(0.35, 1.0)
        fade = np.linspace(1.0, 0.0, len(seg)) ** 1.5
        claps[pos:end] += seg * fade
        pos += int(rng.integers(400, 1500))
    swell = np.minimum(1.0, np.linspace(0, 4, n)) * np.linspace(1, 0.15, n)
    m = _lowpass(claps * swell, 1800)
    _write_wav(os.path.join(SND, "applause.wav"),
               _stereo(_finish(m, 0.15)))


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
