"""Ru-Klecks: fressen, wachsen, und dabei nicht selbst gefressen werden.

Die Idee kennt man von agar.io. Man sammelt Krumen und wird davon groesser -
und wer deutlich groesser ist als ein anderer, kann diesen verschlucken.

Damit hat das Spiel drei Ebenen, die staendig gegeneinander stehen:

* **Gross werden lohnt sich** - nur so kann man andere fressen.
* **Gross sein ist langsam.** Das Tempo faellt mit der Masse, ein dicker
  Klecks holt niemanden mehr ein und wird selbst zur Beute der Mittelgrossen,
  sobald die aufgeholt haben.
* **Der Schub kostet Masse.** Er ist die einzige Moeglichkeit, jemanden zu
  erwischen oder zu entkommen - aber jeder Einsatz macht einen kleiner.

Wer gefressen wird, ist nicht raus, sondern faengt klein wieder an. Rausfliegen
waere bei einem Minispiel von einer Minute zu hart; so bleibt jeder bis zum
Ende dabei und kann sich zurueckarbeiten.
"""

from __future__ import annotations

import math

import pygame

from ...ui.widgets import draw_text
from .. import ui as U
from ..arena import LOGIC_H, LOGIC_W, ArenaGame

MARGIN = 60.0
START_MASS = 10.0
CRUMB_MASS = 2.0
N_CRUMBS = 58

EAT_RATIO = 1.25          # so viel groesser muss man sein, um zu fressen
EAT_KEEP = 0.70           # so viel von der Beute wird gutgeschrieben
BOOST_COST = 0.09         # Anteil der Masse je Schub
SAFE_AFTER_EAT = 2.5      # Schonzeit fuer den frisch Gefressenen

CRUMB = (150, 230, 190)
FIELD = (16, 22, 30)
GRID = (24, 32, 42)


class BlobGame(ArenaGame):
    id = "blob"
    name = "Ru-Klecks"
    rules = ("Frisst Krumen und wachse. Wer deutlich groesser ist, kann "
             "andere verschlucken - aber gross macht langsam.")
    goal = ("Sammle die Krumen und werde groesser. Bist du ein Viertel "
            "groesser als jemand anderes, kannst du ihn verschlucken. Aber "
            "Vorsicht: je groesser du wirst, desto langsamer bist du.")
    key_help = ("nach links lenken", "Schub (kostet Masse)", "nach rechts lenken")
    scoring_help = ("nach deiner Masse am Ende. Wer gefressen wird, faengt "
                    "klein wieder an - raus ist niemand.")
    live_unit = ""
    max_seconds = 60.0

    SPEED = 330.0             # Tempo bei Startmasse
    TURN_RATE = 3.6
    DASH_FACTOR = 1.8
    DASH_TIME = 0.35
    DASH_REFILL = 0.30
    DASH_MAX = 0.75
    WALLS = "bounce"

    # ------------------------------------------------------------------ #
    def setup(self):
        self.crumbs: list[list] = []
        for u in self.units.values():
            self._reset_blob(u, START_MASS)
        for _ in range(N_CRUMBS):
            self.crumbs.append(list(self._free_spot()))
        self.best: dict[int, float] = {pid: START_MASS for pid in self.units}

    def _free_spot(self, away=140.0):
        for _ in range(24):
            x = self.rng.uniform(MARGIN, LOGIC_W - MARGIN)
            y = self.rng.uniform(MARGIN, LOGIC_H - MARGIN)
            if all(math.hypot(u["x"] - x, u["y"] - y) > away
                   for u in self.units.values()):
                return x, y
        return x, y

    def _reset_blob(self, u, mass):
        u["mass"] = float(mass)
        u["r"] = self._radius(mass)
        u["safe"] = 0.0
        u["eaten"] = u.get("eaten", 0)

    @staticmethod
    def _radius(mass):
        # Flaeche proportional zur Masse -> Radius mit der Wurzel
        return 16.0 + 4.2 * math.sqrt(max(1.0, mass))

    def _speed_of(self, u):
        """Tempo faellt mit der Masse - das ist die Bremse gegen Dauerfressen."""
        return self.SPEED * (START_MASS / max(START_MASS, u["mass"])) ** 0.32

    # ------------------------------------------------------------------ #
    def _drive(self, u, dt, left, right, action):
        # Der Schub kostet Masse: er soll eine Entscheidung sein, kein
        # Dauerzustand. Deshalb VOR dem Auslösen pruefen und abziehen.
        will_dash = (action and u["dash_left"] <= 0.0
                     and u["dash"] >= self.DASH_TIME
                     and u["mass"] > START_MASS * 0.75)
        super()._drive(u, dt, left, right, will_dash)
        if will_dash and u["dash_left"] > 0.0:
            self._set_mass(u, u["mass"] * (1.0 - BOOST_COST))
        # `slow` ist der Faktor, mit dem die Basis das Tempo skaliert
        u["slow"] = self._speed_of(u) / self.SPEED

    def _set_mass(self, u, mass):
        u["mass"] = max(1.0, float(mass))
        u["r"] = self._radius(u["mass"])
        u["score"] = u["mass"]
        self.best[u["pid"]] = max(self.best.get(u["pid"], 0.0), u["mass"])

    # ------------------------------------------------------------------ #
    def step_world(self, dt):
        for u in self.units.values():
            u["safe"] = max(0.0, u.get("safe", 0.0) - dt)
            # Krumen aufsammeln
            r = self.unit_radius(u)
            for c in self.crumbs:
                if math.hypot(c[0] - u["x"], c[1] - u["y"]) <= r:
                    c[0], c[1] = self._free_spot(90.0)
                    self._set_mass(u, u["mass"] + CRUMB_MASS)
                    self.ctx.play("tick")
            u["score"] = u["mass"]

    def on_contact(self, a, b, closing):
        """Der Groessere frisst - aber nur, wenn der Abstand wirklich klein
        genug ist. Sich streifen reicht nicht, man muss den anderen ueberdecken.
        """
        big, small = (a, b) if a["mass"] >= b["mass"] else (b, a)
        if small.get("safe", 0.0) > 0.0:
            return
        if big["mass"] < small["mass"] * EAT_RATIO:
            return
        d = math.hypot(big["x"] - small["x"], big["y"] - small["y"])
        if d > self.unit_radius(big) * 0.85:
            return
        self._set_mass(big, big["mass"] + small["mass"] * EAT_KEEP)
        big["eaten"] = big.get("eaten", 0) + 1
        x, y = self._free_spot(220.0)
        small["x"], small["y"] = x, y
        self._reset_blob(small, START_MASS)
        small["safe"] = SAFE_AFTER_EAT
        small["score"] = small["mass"]
        small["hit"] = 0.6
        self.ctx.play("crash")

    # -- Bots -----------------------------------------------------------
    def bot_target(self, u):
        skill = u.get("skill", 1.0)
        # Ein guter Spieler sieht Gefahr und Beute frueher - deshalb haengen
        # beide Reichweiten an der Stufe.
        see_threat = 240.0 + 320.0 * skill
        see_prey = 200.0 + 340.0 * skill
        threat = None
        prey = None
        for o in self.units.values():
            if o is u:
                continue
            d = math.hypot(o["x"] - u["x"], o["y"] - u["y"])
            if o["mass"] >= u["mass"] * EAT_RATIO and d < see_threat:
                if threat is None or d < threat[1]:
                    threat = (o, d)
            elif (u["mass"] >= o["mass"] * EAT_RATIO and d < see_prey
                  and o.get("safe", 0.0) <= 0.0):
                if prey is None or d < prey[1]:
                    prey = (o, d)

        if threat is not None:
            o, d = threat
            tx, ty = self.push_away_target(u, o["x"], o["y"])
            return tx, ty, d < 210.0 and u["dash"] >= self.DASH_TIME
        if prey is not None and skill > 0.35:
            o, d = prey
            return o["x"], o["y"], d < 190.0 and u["dash"] >= self.DASH_TIME
        # sonst zur naechsten Krume
        best, bd = None, 1e18
        for c in self.crumbs:
            d = (c[0] - u["x"]) ** 2 + (c[1] - u["y"]) ** 2
            if d < bd:
                bd, best = d, c
        if best is None:
            return LOGIC_W / 2, LOGIC_H / 2, False
        return best[0], best[1], False

    # -- Netz -----------------------------------------------------------
    def player_wire(self, u):
        return [round(u["mass"], 2), round(u.get("safe", 0.0), 2),
                u.get("eaten", 0)]

    def apply_player_wire(self, u, extra):
        if not extra:
            return
        u["mass"] = float(extra[0])
        u["r"] = self._radius(u["mass"])
        if len(extra) > 1:
            u["safe"] = float(extra[1])
        if len(extra) > 2:
            u["eaten"] = int(extra[2])

    def world_wire(self):
        return {"c": [[round(c[0], 1), round(c[1], 1)] for c in self.crumbs]}

    def apply_world_wire(self, data):
        rows = data.get("c")
        if rows is not None:
            self.crumbs = [[r[0], r[1]] for r in rows]

    # -- Ergebnis -------------------------------------------------------
    def score_detail(self, u):
        n = u.get("eaten", 0)
        base = "Masse %d" % round(u["mass"])
        return base + (" - %dx gefressen" % n if n else "")

    def finish(self):
        super().finish()
        if not self.ctx.is_host:
            return
        # Gleiche Endmasse: wer zwischendurch groesser war, steht vorn.
        for pid, r in self.results_map.items():
            r.time = round(-self.best.get(pid, 0.0), 3)

    # -- Anzeige --------------------------------------------------------
    def draw_world(self, surf):
        area = self.ctx.area
        view = self.view_rect
        surf.fill((10, 14, 20), area)
        pygame.draw.rect(surf, FIELD, view)
        step = self.px(120)
        if step > 6:
            for gx in range(view.x, view.right, step):
                pygame.draw.line(surf, GRID, (gx, view.y), (gx, view.bottom))
            for gy in range(view.y, view.bottom, step):
                pygame.draw.line(surf, GRID, (view.x, gy), (view.right, gy))
        pygame.draw.rect(surf, U.LINE, view, 2)
        r = max(2, self.px(9))
        for c in self.crumbs:
            x, y = self.to_screen(c[0], c[1])
            pygame.draw.circle(surf, CRUMB, (int(x), int(y)), r)
        self.draw_key_help(surf, area, "Schub (kostet Masse)")

    def draw_unit(self, surf, u):
        ring = None
        if u.get("safe", 0.0) > 0.0:
            ring = (150, 220, 255)
        super().draw_unit(surf, u, ring=ring)
        # Masse in den Klecks schreiben, sobald er gross genug ist
        r = self.px(self.unit_radius(u))
        if r >= 16:
            x, y = self.to_screen(u["x"], u["y"])
            img = self.ctx.fonts.body_bold(min(20, max(11, r // 2))).render(
                "%d" % round(u["mass"]), True, (12, 14, 22))
            surf.blit(img, img.get_rect(center=(x, y)))

    HUD_TITLE = "Masse"

    def hud_rows(self):
        rows = sorted(self.units.values(), key=lambda u: -u["mass"])
        return [(u["pid"], "%d" % round(u["mass"])) for u in rows]

    def hud_own(self, u):
        if u.get("safe", 0.0) > 0.0:
            return "gerade sicher (%.1f s)" % u["safe"]
        return "Masse %d" % round(u["mass"])

    def draw_hud(self, surf, area):
        super().draw_hud(surf, area)
        fonts = self.ctx.fonts
        left = max(0.0, self.max_seconds - self.sim_time)
        draw_text(surf, fonts.display(20), "%.0f s" % left, U.TEXT,
                  (area.right - 76, area.y + 6))
        # Wen kann ich fressen, wer kann mich fressen?
        mine = [p for p in self.ctx.local_players if p.pid in self.units]
        if len(mine) == 1:
            me = self.units[mine[0].pid]
            danger = [o for o in self.units.values()
                      if o is not me and o["mass"] >= me["mass"] * EAT_RATIO]
            txt = ("%d koennen dich fressen" % len(danger) if danger
                   else "niemand ist dir gefaehrlich")
            draw_text(surf, fonts.body_bold(14), txt,
                      U.BAD if danger else U.OK, (area.right - 240, area.y + 34))
