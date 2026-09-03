"""Ru-Sumo: schubse die anderen aus dem Ring.

Das direkteste Spiel im Turnier - hier passiert *nichts* ausser Interaktion.
Der Ring schrumpft, es wird also mit der Zeit zwangslaeufig eng, und wer
draussen ist, bleibt draussen. Gewertet wird die ueberlebte Zeit.

Die Aktionstaste ist ein Rammstoss: kurz viel schneller, und ein Treffer
waehrend des Stosses schleudert den anderen deutlich weiter. Wer blind
draufhaelt, fliegt allerdings mit Anlauf selbst hinaus.
"""

from __future__ import annotations

import math

import pygame

from ...ui.widgets import draw_text
from .. import ui as U
from ..arena import LOGIC_H, LOGIC_W, ArenaGame

RING_START = 0.46          # Anteil der kurzen Bildseite
RING_END = 0.16
SHRINK_AFTER = 6.0         # so lange bleibt der Ring gross
SHRINK_TIME = 30.0         # Dauer des Schrumpfens

RING_FILL = (38, 34, 58)
RING_EDGE = (150, 128, 220)
OUTSIDE = (16, 14, 24)


class SumoGame(ArenaGame):
    id = "sumo"
    name = "Ru-Sumo"
    rules = ("Schubse die anderen aus dem Ring. Aktionstaste = Rammstoss. "
             "Der Ring schrumpft - wer draussen ist, ist raus.")
    live_unit = " s"
    max_seconds = 70.0

    SPEED = 280.0
    TURN_RATE = 3.4
    DASH_FACTOR = 2.2
    DASH_TIME = 0.35
    DASH_REFILL = 0.5
    DASH_MAX = 1.05
    RADIUS = 30.0
    WALLS = "none"             # der Ring ist die Grenze, nicht der Bildrand

    # ------------------------------------------------------------------ #
    def setup(self):
        self.cx, self.cy = LOGIC_W / 2, LOGIC_H / 2
        self.short = min(LOGIC_W, LOGIC_H)
        self.ring = self.short * RING_START
        self.out_order: list[int] = []

    def spawn_pose(self, index, total):
        # Enger als der Standardkreis, damit es gleich losgeht
        r = min(LOGIC_W, LOGIC_H) * RING_START * 0.62
        a = -math.pi / 2 + index / max(1, total) * math.tau
        return (LOGIC_W / 2 + math.cos(a) * r,
                LOGIC_H / 2 + math.sin(a) * r,
                a + math.pi)

    # ------------------------------------------------------------------ #
    def step_world(self, dt):
        # Ring schrumpfen
        t = max(0.0, self.sim_time - SHRINK_AFTER) / SHRINK_TIME
        k = min(1.0, t)
        self.ring = self.short * (RING_START + (RING_END - RING_START) * k)

        for u in list(self.units.values()):
            if not u["alive"]:
                continue
            u["score"] = self.sim_time
            d = math.hypot(u["x"] - self.cx, u["y"] - self.cy)
            # Erst wenn man wirklich drueber ist, nicht schon beim Anritzen
            if d > self.ring + self.RADIUS * 0.5:
                u["alive"] = False
                self.out_order.append(u["pid"])
                self.ctx.play("crash")

        if len(self.alive_units()) <= 1 and len(self.units) > 1:
            self.finish()

    def on_contact(self, a, b, closing):
        """Wer rammt, teilt aus - und zwar deutlich mehr als beim Streifen."""
        if closing <= 10.0:
            return
        for pusher, victim in ((a, b), (b, a)):
            power = 1.0
            if pusher["dash_left"] > 0.0:
                power = 2.4
            elif victim["dash_left"] > 0.0:
                continue                     # der andere rammt gerade, nicht du
            ang = math.atan2(victim["y"] - pusher["y"], victim["x"] - pusher["x"])
            self.knockback(victim, ang, (140.0 + closing * 0.7) * power, 0.55)
        self.ctx.play("crash")

    # -- Bots -----------------------------------------------------------
    def bot_target(self, u):
        d_edge = self.ring - math.hypot(u["x"] - self.cx, u["y"] - self.cy)
        # Der Wendekreis bestimmt, wann man abdrehen MUSS: bei Tempo v und
        # TURN_RATE braucht eine Kehre 2 * v / TURN_RATE an Platz. Mit zu
        # kleinem Sicherheitsabstand faehrt das ganze Feld aus dem Ring.
        turn_room = 2.0 * u["v"] / self.TURN_RATE
        if d_edge < turn_room + self.RADIUS * 1.5:
            return self.cx, self.cy, False
        foe = self.nearest_other(u)
        if foe is None:
            return self.cx, self.cy, False
        # Von hinten/aussen anschieben: Ziel ist der Gegner, Stoss wenn nah
        dist = math.hypot(foe["x"] - u["x"], foe["y"] - u["y"])
        want_dash = (dist < self.RADIUS * 4.5 and u["dash"] >= self.DASH_TIME
                     and u.get("skill", 1.0) > 0.7)
        return foe["x"], foe["y"], want_dash

    # -- Netz -----------------------------------------------------------
    def world_wire(self):
        return {"r": round(self.ring, 1)}

    def apply_world_wire(self, data):
        if "r" in data:
            self.ring = float(data["r"])

    # -- Ergebnis -------------------------------------------------------
    def score_detail(self, u):
        return "%.1f s" % u["score"]

    # -- Anzeige --------------------------------------------------------
    def draw_world(self, surf):
        area = self.ctx.area
        surf.fill(OUTSIDE, area)
        c = self.to_screen(self.cx, self.cy)
        r = self.px(self.ring)
        pygame.draw.circle(surf, RING_FILL, (int(c[0]), int(c[1])), r)
        # Randmarkierung: dick, damit man die Kante im Getuemmel sieht
        pygame.draw.circle(surf, RING_EDGE, (int(c[0]), int(c[1])), r, max(3, r // 40))
        pygame.draw.circle(surf, (70, 62, 100), (int(c[0]), int(c[1])),
                           max(2, int(r * 0.55)), 1)
        pygame.draw.circle(surf, (70, 62, 100), (int(c[0]), int(c[1])), max(2, r // 12))
        self.draw_key_help(surf, area, "Rammstoss")

    HUD_TITLE = "noch drin"

    def hud_rows(self):
        alive = sorted(self.alive_units(), key=lambda u: -u["score"])
        rows = [(u["pid"], "drin") for u in alive]
        for pid in reversed(self.out_order):
            rows.append((pid, "raus"))
        return rows

    def hud_own(self, u):
        if not u["alive"]:
            return "rausgeflogen"
        d = self.ring - math.hypot(u["x"] - self.cx, u["y"] - self.cy)
        return "Rand: %d" % max(0, int(d))

    def draw_hud(self, surf, area):
        super().draw_hud(surf, area)
        left = [u for u in self.alive_units()]
        if len(left) == 1 and len(self.units) > 1:
            U.banner(surf, self.ctx.fonts,
                     "%s gewinnt!" % self.unit_name(left[0]), U.GOLD,
                     y=area.centery - 40, size=44)
        else:
            draw_text(surf, self.ctx.fonts.body_bold(15),
                      "%d noch im Ring" % len(left), U.MUTED,
                      (area.right - 130, area.y + 8))
