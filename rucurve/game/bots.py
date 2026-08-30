"""Bot-KI: Faecher aus Strahlen nach vorne, frueh in die freieste Richtung ausweichen.

Die Schwierigkeit steuert Sichtweite, Anzahl der geprueften Richtungen,
Reaktionsrate und wie clever das Powerup eingesetzt wird. Bei Stufe 1.0
schaut der Bot weit voraus, prueft viele Richtungen, bevorzugt offene Flaechen
und rettet sich mit dem Powerup aus Sackgassen.
"""

from __future__ import annotations

import math

from .curve import Curve
from .world import World

_FAN_EASY = (-0.8, -0.36, 0.0, 0.36, 0.8)
_FAN_HARD = (-1.30, -0.95, -0.62, -0.36, -0.16, 0.0, 0.16, 0.36, 0.62, 0.95, 1.30)

# Powerups, die aus einer Notlage helfen (in dieser Vorliebe)
_ESCAPE = ("ghost", "shield", "teleport", "agile", "speed", "thin", "clear", "square")
# Powerups, die man offensiv einsetzt, sobald sie bereit sind
_OFFENSIVE = ("slow_others", "fat_others", "reverse_others", "invert", "fog")


def control_bot(world: World, c: Curve, difficulty: float) -> tuple[bool, bool, bool]:
    """Gibt (links, rechts, powerup) fuer diesen Bot in diesem Tick zurueck."""
    s = world.s
    d = max(0.0, min(1.0, difficulty))
    m = c.mods()
    r = max(1.5, s.line_width * 0.9 * m.width)

    # Wie weit vorausschauen? Mindestens der eigene Wendekreis, sonst kein Ausweg.
    look = 95.0 + 260.0 * d + s.speed * (0.35 + 0.35 * d)
    look = max(look, s.turn_radius * (1.4 + 1.4 * d))

    fan = _FAN_HARD if d >= 0.6 else _FAN_EASY
    others = [(o.x, o.y, o.heading) for o in world.curves if o.alive and o.id != c.id]

    def clear_at(angle: float, dist_cap: float) -> float:
        dist = world.grid.ray_distance(c.x, c.y, angle, dist_cap, r)
        cx, sy = math.cos(angle), math.sin(angle)
        for ox, oy, oh in others:
            proj = (ox - c.x) * cx + (oy - c.y) * sy
            if 0 < proj < dist:
                perp = abs(-(ox - c.x) * sy + (oy - c.y) * cx)
                # Gegner-Koepfe sind gefaehrlich; wohin sie fahren erst recht
                if perp < r * 7:
                    dist = min(dist, proj)
                elif d >= 0.6 and perp < r * 14:
                    lead = 30.0 + 40.0 * d
                    fx, fy = ox + math.cos(oh) * lead, oy + math.sin(oh) * lead
                    fproj = (fx - c.x) * cx + (fy - c.y) * sy
                    fperp = abs(-(fx - c.x) * sy + (fy - c.y) * cx)
                    if 0 < fproj < dist and fperp < r * 7:
                        dist = min(dist, fproj)
        return dist

    straight = clear_at(c.heading, look)

    best_off, best_score = 0.0, -1e9
    for off in fan:
        ang = c.heading + off
        dist = clear_at(ang, look)
        score = dist
        if off == 0.0:
            score += 0.22 * look          # geradeaus ist billiger als lenken
        score -= abs(off) * (6.0 + 6.0 * d)
        if d >= 0.6 and dist > look * 0.9:
            # Bei freier Sicht: pruefen, ob es dahinter weitergeht (offene Flaeche)
            probe = look * 0.85
            px, py = c.x + math.cos(ang) * probe, c.y + math.sin(ang) * probe
            room = sum(
                world.grid.ray_distance(px, py, ang + side, look * 0.8, r)
                for side in (-0.7, 0.0, 0.7)
            )
            score += room / 3.0 * (0.35 * d)
        # Traegheit: starke Bots wechseln die Richtung nicht bei jedem Tick
        # (kein Zickzack, das sich selbst einsperrt). Schwache zappeln weiter.
        if off != 0.0 and c._bot_turn and (off > 0) == (c._bot_turn > 0):
            score += 0.14 * look * d
        if off == 0.0 and c._bot_turn == 0:
            score += 0.08 * look * d
        if score > best_score:
            best_score, best_off = score, off

    # Reaktionsrate: schwache Bots lassen oft aus, starke reagieren jeden Tick
    react = 0.35 + 0.65 * d
    trapped = straight < look * (0.30 + 0.25 * d)
    if not trapped and world.rng.random() > react:
        # Entscheidung ausgelassen. Starke Bots halten ihre Richtung, schwache
        # rucken zurueck auf geradeaus - das macht sie berechenbar schlechter.
        t = c._bot_turn if d >= 0.5 else 0
        return (t < 0, t > 0, False)
    if world.rng.random() < 0.09 * (1.0 - d) ** 2:
        pick = world.rng.choice((-1, 1))
        return (pick < 0, pick > 0, False)

    if trapped and abs(best_off) < 0.05:
        # geradeaus wird eng und der Faecher findet nichts Besseres -> Seite waehlen
        left_room = clear_at(c.heading - 0.75, look)
        right_room = clear_at(c.heading + 0.75, look)
        best_off = -0.75 if left_room >= right_room else 0.75

    left = best_off < -0.03
    right = best_off > 0.03
    c._bot_turn = (1 if right else 0) - (1 if left else 0)

    powerup = _wants_powerup(world, c, d, straight, look, trapped)
    return (left, right, powerup)


def _wants_powerup(world, c: Curve, d: float, straight: float, look: float, trapped: bool) -> bool:
    if not c.pu.can_use():
        return False
    kind = c.pu.kind
    if kind in _ESCAPE:
        # In Not sofort; starke Bots warten auf den richtigen Moment
        if trapped:
            return True
        return straight < look * 0.2 and world.rng.random() < d
    if kind in _OFFENSIVE:
        if d < 0.4:
            return world.rng.random() < 0.004        # planloses Gedrueckte
        # Starke Bots stoeren, wenn Gegner in der Naehe sind
        near = sum(
            1 for o in world.curves
            if o.alive and o.id != c.id
            and (o.x - c.x) ** 2 + (o.y - c.y) ** 2 < (look * 1.6) ** 2
        )
        if near and world.rng.random() < 0.010 + 0.030 * d:
            return True
        return False
    return trapped
