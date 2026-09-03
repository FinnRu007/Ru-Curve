"""Die Sounds muessen ruhig bleiben.

Die erste Fassung war zu laut und zu schrill: Spitzen bis 0.50, und beim
Anpfiff lagen 75 % der Energie ueber 2 kHz - genau dort, wo es im Ohr weh
tut. Dazu Einsaetze unter 2 ms, die als Knacken hoerbar sind.

Hier stehen die Grenzen, damit das nicht unbemerkt zurueckkommt.
"""

from __future__ import annotations

import glob
import os
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SND = os.path.join(ROOT, "assets", "sounds")

MAX_PEAK = 0.24            # Spitzenpegel
MAX_RMS = 0.085            # mittlere Lautstaerke
MAX_HIGH = 0.30            # Anteil Energie ueber 2 kHz
MIN_ATTACK_MS = 2.5        # kuerzer klingt wie ein Knacken

# Klaenge, die im Spiel besonders oft kommen - die duerfen noch weniger
OFTEN = {"crash": 0.20, "whistle": 0.18, "tick": 0.12, "click": 0.16,
         "correct": 0.18, "wrong": 0.18}


def load(path):
    with wave.open(path) as w:
        n, sr, ch = w.getnframes(), w.getframerate(), w.getnchannels()
        raw = np.frombuffer(w.readframes(n), dtype="<i2").astype(float) / 32768
    mono = raw.reshape(-1, ch).mean(axis=1) if ch > 1 else raw
    return mono, sr


def measure(path):
    m, sr = load(path)
    peak = float(np.max(np.abs(m))) if len(m) else 0.0
    rms = float(np.sqrt(np.mean(m ** 2))) if len(m) else 0.0
    spec = np.abs(np.fft.rfft(m))
    freq = np.fft.rfftfreq(len(m), 1 / sr)
    high = float(spec[freq > 2000].sum() / (spec.sum() + 1e-9))
    idx = int(np.argmax(np.abs(m) >= 0.9 * peak)) if peak > 0 else 0
    return {"peak": peak, "rms": rms, "high": high,
            "attack_ms": 1000.0 * idx / sr, "dur": len(m) / sr}


def all_sounds():
    files = sorted(glob.glob(os.path.join(SND, "*.wav")))
    assert files, "keine Sounds gefunden - erst tools/make_assets.py laufen lassen"
    return files


# =========================================================================== #
def test_nothing_is_loud():
    for path in all_sounds():
        v = measure(path)
        name = os.path.basename(path)
        assert v["peak"] <= MAX_PEAK, "%s: Spitze %.2f" % (name, v["peak"])
        assert v["rms"] <= MAX_RMS, "%s: RMS %.3f" % (name, v["rms"])


def test_nothing_is_shrill():
    """Der Anteil oberhalb 2 kHz ist das, was als schrill empfunden wird."""
    for path in all_sounds():
        v = measure(path)
        name = os.path.basename(path)
        assert v["high"] <= MAX_HIGH, (
            "%s: %.0f%% der Energie ueber 2 kHz" % (name, 100 * v["high"]))


def test_no_clicky_attacks():
    """Ein Ton, der in unter 2.5 ms auf voller Lautstaerke ist, knackt."""
    for path in all_sounds():
        v = measure(path)
        name = os.path.basename(path)
        assert v["attack_ms"] >= MIN_ATTACK_MS, (
            "%s: Einsatz in %.1f ms - das knackt" % (name, v["attack_ms"]))


def test_frequent_sounds_are_extra_quiet():
    """Was staendig kommt, muss leiser sein als der Rest - sonst nervt es
    nach der dritten Runde."""
    for name, limit in OFTEN.items():
        path = os.path.join(SND, name + ".wav")
        if not os.path.exists(path):
            continue
        v = measure(path)
        assert v["peak"] <= limit, (
            "%s kommt oft, ist aber mit Spitze %.2f zu laut (max %.2f)"
            % (name, v["peak"], limit))


def test_bump_sound_is_short():
    """Bei Sumo und Ernte rempelt es dauernd - ein langer Knall wuerde sich
    ueberlagern und zu Laerm summieren."""
    path = os.path.join(SND, "crash.wav")
    if os.path.exists(path):
        v = measure(path)
        assert v["dur"] <= 0.30, "Rempelgeraeusch dauert %.2f s" % v["dur"]


def test_every_sound_the_game_asks_for_exists():
    """Ein fehlender Sound faellt sonst erst im Spiel auf - und dort still."""
    import re

    wanted = set()
    for base, _dirs, files in os.walk(os.path.join(ROOT, "rucurve")):
        for f in files:
            if not f.endswith(".py"):
                continue
            text = open(os.path.join(base, f), encoding="utf-8").read()
            wanted.update(re.findall(r"""\.play\(["']([a-z_]+)["']\)""", text))
            wanted.update(re.findall(r"""ctx\.play\(["']([a-z_]+)["']\)""", text))
    have = {os.path.splitext(os.path.basename(p))[0] for p in all_sounds()}
    missing = sorted(wanted - have)
    assert not missing, "Das Spiel spielt Sounds, die es nicht gibt: %s" % missing


def test_sounds_are_not_silent():
    for path in all_sounds():
        v = measure(path)
        assert v["rms"] > 0.004, "%s ist praktisch stumm" % os.path.basename(path)


if __name__ == "__main__":
    import traceback

    print("%-12s %6s %7s %7s %8s %9s" %
          ("Datei", "Dauer", "Spitze", "RMS", "Hoehen", "Anstieg"))
    for p in all_sounds():
        v = measure(p)
        print("%-12s %5.2fs  %5.2f  %6.3f  %6.0f%%  %6.1f ms" %
              (os.path.basename(p), v["dur"], v["peak"], v["rms"],
               100 * v["high"], v["attack_ms"]))
    print()

    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok   %s" % name)
            except Exception:
                fails += 1
                print("FAIL %s" % name)
                traceback.print_exc()
    sys.exit(1 if fails else 0)
