"""Sehr einfache Bot-KI: Strahlen nach vorne, weiche in die freieste Richtung aus."""

from __future__ import annotations

import math

from .curve import Curve
from .world import World

_OFFSETS = (-0.70, -0.32, 0.0, 0.32, 0.70)


def control_bot(world: World, c: Curve, difficulty: float) -> tuple[bool, bool, bool]:
    """Gibt (links, rechts, powerup) fuer diesen Bot in diesem Tick zurueck."""
    s = world.s
    r = max(1.5, s.line_width * 0.9)
    look = 45.0 + 190.0 * difficulty + s.speed * 0.18

    # andere lebende Koepfe als zusaetzliche Hindernisse behandeln
    others = [(o.x, o.y) for o in world.curves if o.alive and o.id != c.id]

    def _dir_clear(angle: float) -> float:
        dist = world.grid.ray_distance(c.x, c.y, angle, look, r)
        cx, sy = math.cos(angle), math.sin(angle)
        for ox, oy in others:
            # Projektion des Gegners auf den Strahl
            proj = (ox - c.x) * cx + (oy - c.y) * sy
            if 0 < proj < dist:
                perp = abs(-(ox - c.x) * sy + (oy - c.y) * cx)
                if perp < r * 6:
                    dist = min(dist, proj)
        return dist

    best_off = 0.0
    best_clear = -1.0
    straight_clear = 0.0
    for off in _OFFSETS:
        dist = _dir_clear(c.heading + off)
        clear = dist + (0.18 * look if off == 0.0 else 0.0)  # leichte Vorliebe fuer geradeaus
        if off == 0.0:
            straight_clear = dist
        if clear > best_clear:
            best_clear = clear
            best_off = off

    # schwache Bots reagieren traeger und zappeliger
    react = 0.25 + 0.7 * difficulty
    if world.rng.random() > react:
        return (False, False, False)
    if world.rng.random() < (0.06 * (1.0 - difficulty)):
        pick = world.rng.choice((-1, 0, 1))
        return (pick < 0, pick > 0, False)

    left = best_off < -0.05
    right = best_off > 0.05

    # in der Klemme -> Powerup (Speed/Geist helfen beim Rauskommen)
    powerup = straight_clear < look * 0.33 and c.pu.can_use()

    return (left, right, powerup)
