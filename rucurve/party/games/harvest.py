"""Ru-Ernte: Kristalle sammeln - und dem Fuehrenden welche abnehmen.

Sammeln allein waere nur ein Wettrennen zum naechsten Punkt. Der Kniff ist
die zweite Regel: **wer rammt, klaut.** Ein Treffer kostet den Getroffenen
Kristalle, die als lose Splitter liegen bleiben - und wer viel hat, verliert
pro Treffer mehr. Damit ist der Fuehrende automatisch die Zielscheibe des
ganzen Feldes, und ein Vorsprung ist nie sicher.
"""

from __future__ import annotations

import math

import pygame

from ...ui.widgets import draw_text
from .. import ui as U
from ..arena import LOGIC_H, LOGIC_W, ArenaGame

MARGIN = 70.0
PICK_RADIUS = 34.0          # zusaetzlich zum Spielerradius
STEAL_SHARE = 0.30          # Anteil, den ein Treffer kostet
STEAL_MIN = 1               # aber mindestens so viele
CRYSTAL = (120, 224, 255)
SHARD = (255, 214, 120)


class HarvestGame(ArenaGame):
    goal = ("Sammle die blauen Kristalle ein. Ein Rammstoss schlaegt einem "
            "anderen Kristalle aus der Hand - die Haelfte davon bekommst du "
            "sofort, der Rest fliegt als Splitter aufs Feld.")
    key_help = ("nach links lenken", "Rammstoss (selten!)", "nach rechts lenken")
    scoring_help = ("je gesammeltem Kristall. Wer viel hat, verliert pro "
                    "Treffer mehr - der Fuehrende ist Zielscheibe.")
    id = "harvest"
    name = "Ru-Ernte"
    rules = ("Sammle die blauen Kristalle. Aktionstaste = Rammstoss - wer "
             "rammt, schlaegt dem anderen Kristalle aus der Hand. Wer viel "
             "hat, verliert mehr.")
    live_unit = ""
    max_seconds = 50.0

    SPEED = 305.0
    TURN_RATE = 4.0
    DASH_FACTOR = 1.85
    DASH_TIME = 0.4
    # Der Rammstoss ist hier eine Waffe, kein Fortbewegungsmittel: er soll
    # eine bewusste Entscheidung sein, nicht etwas, das man dauernd drueckt.
    # DASH_MAX reicht fuer genau EINEN Stoss - man kann also nichts horten -
    # und danach dauert es rund viereinhalb Sekunden bis zum naechsten.
    DASH_REFILL = 0.09
    DASH_MAX = 0.45
    RADIUS = 26.0
    WALLS = "bounce"

    N_CRYSTALS = 14             # so viele liegen gleichzeitig herum

    # ------------------------------------------------------------------ #
    def setup(self):
        self.items: list[dict] = []       # {x, y, kind} kind: 0 Kristall, 1 Splitter
        self._next_id = 0
        for _ in range(self.N_CRYSTALS):
            self._spawn_crystal()

    def _rand_spot(self):
        return (self.rng.uniform(MARGIN, LOGIC_W - MARGIN),
                self.rng.uniform(MARGIN, LOGIC_H - MARGIN))

    def _spawn_crystal(self):
        # Nicht direkt auf einem Spieler auftauchen lassen
        for _ in range(20):
            x, y = self._rand_spot()
            if all(math.hypot(u["x"] - x, u["y"] - y) > 120.0
                   for u in self.units.values()):
                break
        self.items.append({"x": x, "y": y, "kind": 0, "age": 0.0})

    # ------------------------------------------------------------------ #
    def step_world(self, dt):
        for it in self.items:
            it["age"] += dt
        # Aufsammeln
        reach = self.RADIUS + PICK_RADIUS
        for u in self.units.values():
            if not u["alive"]:
                continue
            for it in list(self.items):
                if math.hypot(it["x"] - u["x"], it["y"] - u["y"]) <= reach:
                    self.items.remove(it)
                    u["score"] += 1
                    u["last_gain"] = self.sim_time
                    self.ctx.play("powerup" if it["kind"] == 0 else "correct")
                    if it["kind"] == 0:
                        self._spawn_crystal()
        # Splitter verschwinden nach einer Weile, Kristalle bleiben
        self.items = [it for it in self.items
                      if it["kind"] == 0 or it["age"] < 9.0]

    def on_contact(self, a, b, closing):
        if closing <= 25.0:
            return
        for pusher, victim in ((a, b), (b, a)):
            if pusher["dash_left"] <= 0.0:
                continue                     # nur ein echter Stoss klaut
            if victim["score"] <= 0:
                continue
            lost = max(STEAL_MIN, int(victim["score"] * STEAL_SHARE))
            lost = min(lost, int(victim["score"]))
            victim["score"] -= lost
            # Die Haelfte greift sich der Rammende sofort, der Rest fliegt
            # als Splitter weg. Ohne diesen direkten Gewinn waere Rammen
            # selbstlos - man haette die Beute nur fuer alle anderen verteilt.
            grabbed = lost // 2
            pusher["score"] += grabbed
            if grabbed:
                pusher["last_gain"] = self.sim_time
            ang = math.atan2(victim["y"] - pusher["y"], victim["x"] - pusher["x"])
            self.knockback(victim, ang, 150.0 + closing * 0.4, 0.45)
            self._scatter(victim, lost - grabbed)
            self.ctx.play("crash")

    def _scatter(self, u, count):
        """Verlorene Kristalle liegen als Splitter herum - jeder kann sie holen."""
        for i in range(min(count, 8)):
            a = self.rng.uniform(0, math.tau)
            d = self.rng.uniform(70.0, 190.0)
            x = max(MARGIN, min(LOGIC_W - MARGIN, u["x"] + math.cos(a) * d))
            y = max(MARGIN, min(LOGIC_H - MARGIN, u["y"] + math.sin(a) * d))
            self.items.append({"x": x, "y": y, "kind": 1, "age": 0.0})

    # -- Bots -----------------------------------------------------------
    def bot_target(self, u):
        skill = u.get("skill", 1.0)
        # Starke Bots gehen den Fuehrenden an, wenn er nah und lohnend ist
        if skill > 0.62:
            leader = max((o for o in self.units.values() if o is not u),
                         key=lambda o: o["score"], default=None)
            if (leader is not None and leader["score"] >= u["score"] + 3
                    and u["dash"] >= self.DASH_TIME):
                dist = math.hypot(leader["x"] - u["x"], leader["y"] - u["y"])
                if dist < 520.0:
                    return leader["x"], leader["y"], dist < self.RADIUS * 5
        best, best_d = None, 1e18
        for it in self.items:
            d = (it["x"] - u["x"]) ** 2 + (it["y"] - u["y"]) ** 2
            if it["kind"] == 1:
                d *= 0.7                     # Splitter sind attraktiver
            if d < best_d:
                best_d, best = d, it
        if best is None:
            return LOGIC_W / 2, LOGIC_H / 2, False
        return best["x"], best["y"], False

    # -- Netz -----------------------------------------------------------
    def world_wire(self):
        return {"i": [[round(it["x"], 1), round(it["y"], 1), it["kind"]]
                      for it in self.items]}

    def apply_world_wire(self, data):
        rows = data.get("i")
        if rows is None:
            return
        self.items = [{"x": r[0], "y": r[1], "kind": int(r[2]), "age": 0.0}
                      for r in rows]

    # -- Ergebnis -------------------------------------------------------
    def score_detail(self, u):
        return "%d Kristalle" % round(u["score"])

    def finish(self):
        super().finish()
        if not self.ctx.is_host:
            return
        # Gleiche Zahl Kristalle: wer sie frueher zusammen hatte, steht vorn.
        # Sonst teilen sich bei vielen Mitspielern reihenweise Leute die
        # Plaetze, weil die Punktzahlen ganze Zahlen sind.
        for pid, r in self.results_map.items():
            r.time = round(self.units[pid].get("last_gain", self.max_seconds), 3)

    # -- Anzeige --------------------------------------------------------
    def draw_world(self, surf):
        area = self.ctx.area
        view = self.view_rect
        surf.fill((14, 18, 30), area)
        pygame.draw.rect(surf, (20, 26, 42), view)
        pygame.draw.rect(surf, U.LINE, view, 2)
        for it in self.items:
            x, y = self.to_screen(it["x"], it["y"])
            if it["kind"] == 0:
                r = self.px(17)
                pts = [(x, y - r), (x + r * 0.8, y), (x, y + r), (x - r * 0.8, y)]
                pygame.draw.polygon(surf, CRYSTAL, pts)
                pygame.draw.polygon(surf, (30, 60, 80), pts, 2)
            else:
                r = self.px(12)
                blink = it["age"] > 6.5 and int(it["age"] * 6) % 2 == 0
                if not blink:
                    pygame.draw.circle(surf, SHARD, (int(x), int(y)), r)
                    pygame.draw.circle(surf, (90, 70, 30), (int(x), int(y)), r, 1)
        self.draw_key_help(surf, area, "Rammstoss (klaut Kristalle)")

    HUD_TITLE = "Kristalle"

    def hud_own(self, u):
        return "%d Kristalle" % round(u["score"])

    def draw_hud(self, surf, area):
        super().draw_hud(surf, area)
        fonts = self.ctx.fonts
        left = max(0.0, self.max_seconds - self.sim_time)
        draw_text(surf, fonts.display(20), "%.0f s" % left, U.TEXT,
                  (area.right - 76, area.y + 6))
