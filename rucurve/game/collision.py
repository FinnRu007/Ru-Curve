"""Belegungsraster fuer die Kollision - ein numpy-uint8-Array in Arena-Aufloesung.

`stamp_circle` malt eine gefuellte Kreisscheibe (Trail), `hits` prueft, ob unter
einer Scheibe schon etwas gemalt ist oder ob sie den Rand verlaesst.
"""

from __future__ import annotations

import numpy as np


class CollisionGrid:
    def __init__(self, width: int, height: int) -> None:
        self.w = int(width)
        self.h = int(height)
        self.grid = np.zeros((self.h, self.w), dtype=np.uint8)

    def clear(self) -> None:
        self.grid.fill(0)

    # ------------------------------------------------------------------ #
    def stamp_circle(self, x: float, y: float, r: float, value: int = 1) -> None:
        r = max(0.5, float(r))
        x0 = max(0, int(np.floor(x - r)))
        x1 = min(self.w, int(np.ceil(x + r)) + 1)
        y0 = max(0, int(np.floor(y - r)))
        y1 = min(self.h, int(np.ceil(y + r)) + 1)
        if x0 >= x1 or y0 >= y1:
            return
        ys = np.arange(y0, y1)[:, None].astype(np.float32)
        xs = np.arange(x0, x1)[None, :].astype(np.float32)
        mask = (xs - x) ** 2 + (ys - y) ** 2 <= r * r
        block = self.grid[y0:y1, x0:x1]
        block[mask] = value

    def stamp_segment(self, x0: float, y0: float, x1: float, y1: float, r: float, value: int = 1) -> None:
        """Kreisscheiben entlang einer Strecke (dichte Linie ohne Luecken)."""
        dx, dy = x1 - x0, y1 - y0
        length = (dx * dx + dy * dy) ** 0.5
        n = max(1, int(length / max(0.75, r * 0.6)))
        for i in range(n + 1):
            t = i / n
            self.stamp_circle(x0 + dx * t, y0 + dy * t, r, value)

    # ------------------------------------------------------------------ #
    def hits(self, x: float, y: float, r: float) -> bool:
        r = max(0.5, float(r))
        # Rand = toedlich
        if x - r < 0 or y - r < 0 or x + r >= self.w or y + r >= self.h:
            return True
        x0 = max(0, int(np.floor(x - r)))
        x1 = min(self.w, int(np.ceil(x + r)) + 1)
        y0 = max(0, int(np.floor(y - r)))
        y1 = min(self.h, int(np.ceil(y + r)) + 1)
        if x0 >= x1 or y0 >= y1:
            return False
        sub = self.grid[y0:y1, x0:x1]
        if not sub.any():
            return False
        ys = np.arange(y0, y1)[:, None].astype(np.float32)
        xs = np.arange(x0, x1)[None, :].astype(np.float32)
        mask = (xs - x) ** 2 + (ys - y) ** 2 <= r * r
        return bool(np.any(sub[mask] != 0))

    def ray_distance(self, x: float, y: float, angle: float, max_dist: float, r: float, step: float | None = None) -> float:
        """Entfernung bis zum ersten Hindernis entlang eines Strahls (fuer die Bot-KI).

        Punkt-Abtastung (kein Scheiben-Test) und vektorisiert - schnell genug fuer
        viele Bots pro Tick."""
        import math

        step = step or 7.0
        n = max(2, int(max_dist / step) + 1)
        ds = np.arange(n, dtype=np.float32) * step
        xs = x + math.cos(angle) * ds
        ys = y + math.sin(angle) * ds
        margin = max(1.0, r)
        oob = (xs < margin) | (ys < margin) | (xs >= self.w - margin) | (ys >= self.h - margin)
        ix = np.clip(xs.astype(np.int32), 0, self.w - 1)
        iy = np.clip(ys.astype(np.int32), 0, self.h - 1)
        hit = (self.grid[iy, ix] != 0) | oob
        idx = int(np.argmax(hit))
        if hit[idx]:
            return float(ds[idx])
        return float(max_dist)
