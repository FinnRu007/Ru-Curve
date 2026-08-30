"""Die autoritative Simulation: fester Zeitschritt, Kurven, Runden, Punkte.

Der Host (auch beim lokalen Spiel) besitzt genau eine World. Clients rendern nur
Snapshots und Segmente, die von hier kommen.
"""

from __future__ import annotations

import math
import random

from .collision import CollisionGrid
from .curve import Curve
from . import powerups

TICK = 1.0 / 60.0


def _wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


class World:
    def __init__(self, settings, curves: list[Curve], rng: random.Random | None = None) -> None:
        self.s = settings.clamped()
        self.curves = curves
        self.rng = rng or random.Random()
        self.grid = CollisionGrid(self.s.arena_width, self.s.arena_height)

        self.phase = "countdown"          # countdown -> running -> finished
        self.countdown = self.s.countdown_seconds
        self.time = 0.0

        self.segments: list[tuple] = []   # (cid, x0, y0, x1, y1, width, gap_bool)
        self.events: list[tuple] = []     # ("death", cid) / ("pu_use", cid, kind) / ...
        self._death_order: list[int] = []
        self.round_standings: list[dict] | None = None

        self._neck = max(self.s.line_width * 2.5, 14.0)
        self._place_spawns()

    # ================================================================== #
    #  Aufbau
    # ================================================================== #
    def _roll_gap(self) -> float:
        j = self.s.gap_distance_jitter
        return max(20.0, self.s.gap_distance * (1.0 + self.rng.uniform(-j, j)))

    def _place_spawns(self) -> None:
        s = self.s
        w, h = s.arena_width, s.arena_height
        cx, cy = w / 2.0, h / 2.0
        margin = min(min(w, h) * 0.34, max(120.0, 2.2 * s.turn_radius))
        n = max(1, len(self.curves))
        min_dist = max(min(w, h) / (math.sqrt(n) + 0.8), s.line_width * 22, 130.0)
        min_dist = min(min_dist, (min(w, h) - 2 * margin) * 0.6)

        placed: list[tuple[float, float, float]] = []
        for c in self.curves:
            spot = None
            for attempt in range(600):
                x = self.rng.uniform(margin, w - margin)
                y = self.rng.uniform(margin, h - margin)
                md = min_dist * (1.0 - 0.4 * attempt / 600)  # notfalls lockern
                if any((x - px) ** 2 + (y - py) ** 2 < md * md for px, py, _ in placed):
                    continue
                # grob Richtung Mitte, aber mit breitem Streuwinkel -> kein Frontal-Crash
                heading = math.atan2(cy - y, cx - x) + self.rng.uniform(-1.35, 1.35)
                bad = False
                for px, py, _ph in placed:
                    if (px - x) ** 2 + (py - y) ** 2 < (min_dist * 1.5) ** 2:
                        if abs(_wrap(math.atan2(py - y, px - x) - heading)) < 0.45:
                            bad = True
                            break
                if bad:
                    continue
                spot = (x, y, heading)
                break
            if spot is None:  # gleichmaessiger Kreis als Fallback
                i = len(placed)
                ang = 2 * math.pi * i / n
                rad = (min(w, h) / 2.0 - margin) * 0.85
                x = cx + math.cos(ang) * rad
                y = cy + math.sin(ang) * rad
                heading = math.atan2(cy - y, cx - x) + self.rng.uniform(-0.4, 0.4)
                spot = (x, y, heading)
            placed.append(spot)
            c.x, c.y, c.heading = spot
            c.reset_runtime(self.s.powerup_charges)
            c.next_gap_at = self._roll_gap() + self.s.gap_distance * 0.4

    # ================================================================== #
    #  Eingaben
    # ================================================================== #
    def set_input(self, cid: int, left: bool, right: bool, powerup: bool) -> None:
        c = self._by_id(cid)
        if c is None:
            return
        c.turn = (1 if right else 0) - (1 if left else 0)
        c.powerup_pressed = bool(powerup)

    def _by_id(self, cid: int) -> Curve | None:
        for c in self.curves:
            if c.id == cid:
                return c
        return None

    # ================================================================== #
    #  Simulation
    # ================================================================== #
    def step(self) -> None:
        if self.phase == "countdown":
            self.countdown -= TICK
            if self.countdown <= 0:
                self.phase = "running"
                self.events.append(("go",))
            return
        if self.phase != "running":
            return

        self.time += TICK
        for c in self.curves:
            if c.alive:
                c.tick_effects(TICK)
        for c in self.curves:
            if c.alive:
                self._advance(c)
        self._head_on_collisions()
        for c in self.curves:
            self._commit_pending(c, force=not c.alive)

        self._check_round_end()

    def _advance(self, c: Curve) -> None:
        s = self.s
        speed_mult, width_mult, ghost = c.effect_mods()

        if c.powerup_pressed and not c._pu_edge:
            powerups.activate(self, c)
        c._pu_edge = c.powerup_pressed

        speed = s.speed * speed_mult
        turn_rate = s.turn_rate()          # aus der Grundgeschwindigkeit -> Radius bleibt stabil
        radius = s.line_width * 0.5 * width_mult

        dist = speed * TICK
        steps = max(1, math.ceil(dist / max(0.75, s.line_width * 0.5)))
        ds = dist / steps
        dh = c.turn * turn_rate * TICK / steps

        for _ in range(steps):
            c.heading += dh
            nx = c.x + math.cos(c.heading) * ds
            ny = c.y + math.sin(c.heading) * ds

            if not ghost and self.grid.hits(nx, ny, max(1.0, radius * 0.9)):
                c.x, c.y = nx, ny
                self._kill(c)
                return

            drawing = True
            if c.gap_left > 0:
                c.gap_left -= ds
                drawing = False
            else:
                c.dist_since_gap += ds
                if c.dist_since_gap >= c.next_gap_at:
                    c.gap_left = s.gap_size
                    c.dist_since_gap = 0.0
                    c.next_gap_at = self._roll_gap()
            if ghost:
                drawing = False

            if drawing:
                c.pending.append((nx, ny, radius, c.dist_travelled))
            self.segments.append((c.id, c.x, c.y, nx, ny, radius * 2.0, not drawing))

            c.x, c.y = nx, ny
            c.dist_travelled += ds

    def _head_on_collisions(self) -> None:
        alive = [c for c in self.curves if c.alive]
        thr = self.s.line_width * 1.1
        for i in range(len(alive)):
            for j in range(i + 1, len(alive)):
                a, b = alive[i], alive[j]
                if a.effect_mods()[2] or b.effect_mods()[2]:
                    continue
                if (a.x - b.x) ** 2 + (a.y - b.y) ** 2 <= thr * thr:
                    self._kill(a)
                    self._kill(b)

    def _commit_pending(self, c: Curve, force: bool = False) -> None:
        while c.pending:
            x, y, r, d0 = c.pending[0]
            if force or (c.dist_travelled - d0) > self._neck:
                self.grid.stamp_circle(x, y, r)
                c.pending.popleft()
            else:
                break

    def _kill(self, c: Curve) -> None:
        if not c.alive:
            return
        c.alive = False
        self._death_order.append(c.id)
        self._commit_pending(c, force=True)
        self.events.append(("death", c.id))

    # ================================================================== #
    #  Rundenende + Punkte
    # ================================================================== #
    def _check_round_end(self) -> None:
        alive = [c for c in self.curves if c.alive]
        n = len(self.curves)
        time_up = self.s.round_time_limit > 0 and self.time >= self.s.round_time_limit
        if n == 1:
            done = not alive or time_up
        else:
            done = len(alive) <= 1 or time_up
        if done:
            self._finish_round(alive)

    def _finish_round(self, alive: list[Curve]) -> None:
        # Reihenfolge: Ueberlebende (nach id), dann Tote in umgekehrter Sterbereihenfolge
        order: list[Curve] = list(alive)
        for cid in reversed(self._death_order):
            c = self._by_id(cid)
            if c is not None and c not in order:
                order.append(c)
        for c in self.curves:
            if c not in order:
                order.append(c)

        n = len(self.curves)
        standings: list[dict] = []
        for place, c in enumerate(order, start=1):
            c.place = place
            gained = self.s.points_per_opponent * (n - place)
            c.score += gained
            standings.append(
                {
                    "id": c.id,
                    "name": c.name,
                    "color_index": c.color_index,
                    "place": place,
                    "gained": gained,
                    "score": c.score,
                }
            )
        self.round_standings = standings
        self.phase = "finished"
        self.events.append(("round_over", standings))

    # ================================================================== #
    #  Netzwerk / Rendering
    # ================================================================== #
    def drain_segments(self) -> list[tuple]:
        seg, self.segments = self.segments, []
        return seg

    def drain_events(self) -> list[tuple]:
        ev, self.events = self.events, []
        return ev

    def snapshot(self) -> dict:
        return {
            "phase": self.phase,
            "countdown": round(self.countdown, 2),
            "time": round(self.time, 2),
            "curves": [
                {
                    "id": c.id,
                    "x": round(c.x, 1),
                    "y": round(c.y, 1),
                    "h": round(c.heading, 3),
                    "alive": c.alive,
                    "pu": c.pu.charges,
                    "cd": round(c.pu.cooldown_left, 1),
                    "score": c.score,
                    "boost": any(e[0] == "speed" for e in c.effects),
                }
                for c in self.curves
            ],
        }

    def match_winner(self) -> Curve | None:
        best = max(self.curves, key=lambda c: c.score, default=None)
        if best and best.score >= self.s.target_score:
            # eindeutiger Vorsprung?
            top = sorted((c.score for c in self.curves), reverse=True)
            if len(top) == 1 or top[0] > top[1]:
                return best
        return None
