"""Einfache Bot-KI: Strahlen nach vorne, frueh in die freieste Richtung ausweichen."""

from __future__ import annotations

import math

from .curve import Curve
from .world import World

_OFFSETS = (-0.8, -0.36, 0.0, 0.36, 0.8)


def control_bot(world: World, c: Curve, difficulty: float) -> tuple[bool, bool, bool]:
    """Gibt (links, rechts, powerup) fuer diesen Bot in diesem Tick zurueck."""
    s = world.s
    r = max(1.5, s.line_width * 0.9)
    # deutlich weiter vorausschauen als frueher -> Bots reagieren rechtzeitig
    look = 95.0 + 170.0 * difficulty + s.speed * 0.40

    others = [(o.x, o.y) for o in world.curves if o.alive and o.id != c.id]

    def clear_at(angle: float) -> float:
        dist = world.grid.ray_distance(c.x, c.y, angle, look, r)
        cx, sy = math.cos(angle), math.sin(angle)
        for ox, oy in others:
            proj = (ox - c.x) * cx + (oy - c.y) * sy
            if 0 < proj < dist:
                perp = abs(-(ox - c.x) * sy + (oy - c.y) * cx)
                if perp < r * 7:
                    dist = min(dist, proj)
        return dist

    straight = clear_at(c.heading)
    best_off, best_clear = 0.0, -1.0
    for off in _OFFSETS:
        d = clear_at(c.heading + off)
        score = d + (0.22 * look if off == 0.0 else -abs(off) * 8.0)
        if score > best_clear:
            best_clear, best_off = score, off

    # sehr schwache Bots reagieren manchmal gar nicht / zappeln
    react = 0.60 + 0.38 * difficulty
    if world.rng.random() > react:
        return (False, False, False)
    if world.rng.random() < 0.04 * (1.0 - difficulty):
        pick = world.rng.choice((-1, 1))
        return (pick < 0, pick > 0, False)

    danger = straight < look * 0.55
    if danger and abs(best_off) < 0.05:
        # geradeaus wird eng, aber die Seiten sind kaum besser -> trotzdem lenken
        left_room = clear_at(c.heading - 0.6)
        right_room = clear_at(c.heading + 0.6)
        best_off = -0.6 if left_room >= right_room else 0.6

    left = best_off < -0.03
    right = best_off > 0.03

    powerup = straight < look * 0.32 and c.pu.can_use()
    return (left, right, powerup)
