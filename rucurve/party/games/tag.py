"""Ru-Jagd: einer ist der Fänger, alle anderen fliehen.

Punkte gibt es fuer jede Sekunde, in der man NICHT der Faenger ist. Wer
gefangen wird, ist selbst dran - und sammelt in der Zeit nichts. Damit
richtet sich das ganze Feld dauernd neu aus: wer vorn liegt, wird gejagt.

Der Faenger ist etwas schneller als die Fluechtenden, sonst faengt er nie
jemanden. Nach einem Wechsel ist der frisch Befreite kurz unantastbar, damit
es kein Hin-und-Her auf der Stelle gibt.
"""

from __future__ import annotations

import math

import pygame

from ...ui.widgets import draw_text
from .. import ui as U
from ..arena import LOGIC_H, LOGIC_W, ArenaGame

IT_SPEED = 1.22            # Tempoaufschlag fuer den Faenger
# Zwei getrennte Sperren, und das ist der Kern des Spiels:
#   TAG_COOL  - der frische Faenger darf kurz gar nicht fangen
#   IMMUNE    - wer gerade abgegeben hat, ist eine Weile unantastbar
# Mit nur einer gemeinsamen Sperre pendelt die Rolle zwischen denselben
# zwei Spielern hin und her und die anderen sind nie dran.
TAG_COOL = 1.0
IMMUNE = 3.0
IT_COLOR = (255, 96, 96)


class TagGame(ArenaGame):
    id = "tag"
    name = "Ru-Jagd"
    rules = ("Der rot markierte Spieler ist der Faenger. Punkte gibt es fuer "
             "jede Sekunde, in der du NICHT der Faenger bist. "
             "Aktionstaste = Sprint.")
    live_unit = " s"
    max_seconds = 45.0

    SPEED = 300.0
    TURN_RATE = 3.9
    DASH_FACTOR = 1.75
    DASH_TIME = 0.4
    DASH_REFILL = 0.42
    DASH_MAX = 1.1
    RADIUS = 26.0
    WALLS = "bounce"

    # ------------------------------------------------------------------ #
    def setup(self):
        # Der erste Faenger wird gewuerfelt - auf jedem Rechner gleich,
        # weil der Seed vom Host kommt.
        pids = sorted(self.units)
        self.it = pids[self.rng.randrange(len(pids))] if pids else -1
        self.tag_cool = TAG_COOL          # auch am Anfang kurz Ruhe
        self.catches: dict[int, int] = {pid: 0 for pid in self.units}
        self.it_time: dict[int, float] = {pid: 0.0 for pid in self.units}
        for u in self.units.values():
            u["immune"] = 0.0

    # ------------------------------------------------------------------ #
    def step_world(self, dt):
        self.tag_cool = max(0.0, self.tag_cool - dt)
        for pid, u in self.units.items():
            u["immune"] = max(0.0, u.get("immune", 0.0) - dt)
            if pid == self.it:
                self.it_time[pid] = self.it_time.get(pid, 0.0) + dt
                u["slow"] = IT_SPEED
                u["immune"] = 0.0          # als Faenger nuetzt sie nichts
            else:
                u["score"] += dt
                u["slow"] = 1.0

    def on_contact(self, a, b, closing):
        it, other = None, None
        if a["pid"] == self.it:
            it, other = a, b
        elif b["pid"] == self.it:
            it, other = b, a
        if it is not None and (self.tag_cool > 0.0 or other.get("immune", 0.0) > 0.0):
            # Beruehrung zaehlt nicht - aber wegschieben, damit sie nicht
            # aneinander kleben bleiben.
            ang = math.atan2(other["y"] - it["y"], other["x"] - it["x"])
            self.knockback(other, ang, 120.0, 0.25)
            return
        if it is None:
            # Zwei Fluechtende stossen zusammen: nur wegschieben
            if closing > 40.0:
                ang = math.atan2(b["y"] - a["y"], b["x"] - a["x"])
                self.knockback(b, ang, 90.0, 0.25)
                self.knockback(a, ang + math.pi, 90.0, 0.25)
            return

        # Gefangen: Rollen tauschen
        self.it = other["pid"]
        self.catches[it["pid"]] = self.catches.get(it["pid"], 0) + 1
        self.tag_cool = TAG_COOL
        it["immune"] = IMMUNE               # wer abgibt, ist erst mal sicher
        ang = math.atan2(other["y"] - it["y"], other["x"] - it["x"])
        self.knockback(it, ang + math.pi, 220.0, 0.45)   # Faenger prallt zurueck
        self.knockback(other, ang, 120.0, 0.3)
        other["hit"] = 0.5
        self.ctx.play("whistle")

    # -- Bots -----------------------------------------------------------
    def bot_target(self, u):
        if u["pid"] == self.it:
            foe = self._prey(u)
            if foe is None:
                return None
            dist = math.hypot(foe["x"] - u["x"], foe["y"] - u["y"])
            # etwas vorhalten, sonst laeuft der Bot immer hinterher
            lead = min(1.0, dist / 500.0) * 220.0
            return (foe["x"] + math.cos(foe["h"]) * lead,
                    foe["y"] + math.sin(foe["h"]) * lead,
                    dist < self.RADIUS * 6 and u["dash"] >= self.DASH_TIME)
        hunter = self.units.get(self.it)
        if hunter is None:
            return None
        dist = math.hypot(hunter["x"] - u["x"], hunter["y"] - u["y"])
        tx, ty = self.push_away_target(u, hunter["x"], hunter["y"])
        # nicht in die Ecke fliehen - zur Mitte hin ausweichen
        tx = tx * 0.7 + LOGIC_W / 2 * 0.3
        ty = ty * 0.7 + LOGIC_H / 2 * 0.3
        return tx, ty, dist < self.RADIUS * 7 and u["dash"] >= self.DASH_TIME

    def _prey(self, u):
        """Wen der Faenger sich vornimmt.

        Nicht einfach den Naechsten: dann lohnt es sich, einfach weit weg
        herumzuirren, und der Punktestand spielt keine Rolle mehr. Wer viel
        freie Zeit gesammelt hat, ist attraktiver - so wird der Fuehrende
        automatisch gejagt und ein Vorsprung bleibt nie bequem.
        """
        best, best_cost = None, 1e18
        top = max((o["score"] for o in self.units.values() if o is not u),
                  default=0.0) or 1.0
        for o in self.units.values():
            if o is u or not o["alive"] or o.get("immune", 0.0) > 0.0:
                continue
            dist = math.hypot(o["x"] - u["x"], o["y"] - u["y"])
            share = max(0.0, min(1.0, o["score"] / top))
            cost = dist / (0.55 + 0.9 * share)
            if cost < best_cost:
                best_cost, best = cost, o
        return best

    # -- Netz -----------------------------------------------------------
    def world_wire(self):
        return {"it": self.it, "c": round(self.tag_cool, 2)}

    def apply_world_wire(self, data):
        if "it" in data:
            self.it = int(data["it"])
        if "c" in data:
            self.tag_cool = float(data["c"])

    # -- Ergebnis -------------------------------------------------------
    def score_detail(self, u):
        return "%.1f s frei - %dx gefangen" % (
            u["score"], self.catches.get(u["pid"], 0))

    def player_wire(self, u):
        return [self.catches.get(u["pid"], 0), round(u.get("immune", 0.0), 2)]

    def apply_player_wire(self, u, extra):
        if extra:
            self.catches[u["pid"]] = int(extra[0])
            if len(extra) > 1:
                u["immune"] = float(extra[1])

    # -- Anzeige --------------------------------------------------------
    def draw_world(self, surf):
        area = self.ctx.area
        view = self.view_rect
        surf.fill((18, 20, 32), area)
        pygame.draw.rect(surf, (24, 27, 42), view)
        step = self.px(100)
        if step > 6:
            for gx in range(view.x, view.right, step):
                pygame.draw.line(surf, (30, 34, 52), (gx, view.y), (gx, view.bottom))
            for gy in range(view.y, view.bottom, step):
                pygame.draw.line(surf, (30, 34, 52), (view.x, gy), (view.right, gy))
        pygame.draw.rect(surf, U.LINE, view, 2)
        self.draw_key_help(surf, area, "Sprint")

    def draw_unit(self, surf, u):
        is_it = u["pid"] == self.it
        ring = None
        if is_it:
            ring = IT_COLOR
        elif u.get("immune", 0.0) > 0.0:
            ring = (150, 220, 255)          # kurz sicher
        super().draw_unit(surf, u, ring=ring)
        if is_it:
            x, y = self.to_screen(u["x"], u["y"])
            r = self.px(self.RADIUS)
            img = self.ctx.fonts.body_bold(13).render("FAENGER", True, IT_COLOR)
            surf.blit(img, img.get_rect(midtop=(x, y + r + 4)))

    HUD_TITLE = "freie Zeit"

    def hud_own(self, u):
        if u["pid"] == self.it:
            if self.tag_cool > 0.0:
                return "du faengst - noch %.1f s" % self.tag_cool
            return "du faengst!"
        if u.get("immune", 0.0) > 0.0:
            return "sicher (%.1f s)" % u["immune"]
        return "%.1f s frei" % u["score"]

    def draw_hud(self, surf, area):
        super().draw_hud(surf, area)
        fonts = self.ctx.fonts
        left = max(0.0, self.max_seconds - self.sim_time)
        draw_text(surf, fonts.display(20), "%.0f s" % left, U.TEXT,
                  (area.right - 76, area.y + 6))
        hunter = self.units.get(self.it)
        if hunter is not None:
            draw_text(surf, fonts.body_bold(14),
                      "Faenger: %s" % self.unit_name(hunter), IT_COLOR,
                      (area.right - 210, area.y + 34))
