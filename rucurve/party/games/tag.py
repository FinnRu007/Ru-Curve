"""Ru-Jagd: die Fänger jagen, alle anderen fliehen.

Punkte gibt es fuer jede Sekunde, in der man NICHT Faenger ist. Wer gefangen
wird, ist selbst dran - und sammelt in der Zeit nichts. Damit richtet sich
das ganze Feld dauernd neu aus: wer vorn liegt, wird bevorzugt gejagt.

**Die Zahl der Faenger waechst mit dem Feld** (einer je HUNTERS_PER Spieler).
Mit einem einzigen Faenger und zwanzig Leuten wird kaum jemand erwischt -
dann haben am Ende zehn Leute genau die gleiche Zeit, teilen sich den ersten
Platz, und das Spiel entscheidet nichts mehr.

Zwei getrennte Sperren halten die Rollen in Bewegung:
  * `cool`   - wer gerade Faenger geworden ist, darf kurz nicht fangen
  * `immune` - wer gerade abgegeben hat, ist eine Weile unantastbar
Mit einer gemeinsamen Sperre pendelte die Rolle zwischen denselben zwei
Spielern hin und her.
"""

from __future__ import annotations

import math

import pygame

from ...ui.widgets import draw_text
from .. import ui as U
from ..arena import LOGIC_H, LOGIC_W, ArenaGame

HUNTERS_PER = 5            # ein Faenger je so vielen Spielern
IT_SPEED = 1.22            # Tempoaufschlag fuer die Faenger
TAG_COOL = 1.0             # frischer Faenger darf so lange nicht fangen
IMMUNE = 3.0               # so lange ist man nach dem Abgeben sicher
IT_COLOR = (255, 96, 96)
SAFE_COLOR = (150, 220, 255)


class TagGame(ArenaGame):
    id = "tag"
    name = "Ru-Jagd"
    rules = ("Die rot markierten Spieler sind die Faenger. Punkte gibt es "
             "fuer jede Sekunde, in der du KEIN Faenger bist. "
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
        pids = sorted(self.units)
        if len(pids) > 1:
            self.n_hunters = max(1, min(len(pids) - 1, len(pids) // HUNTERS_PER))
        else:
            self.n_hunters = 0
        # Wer anfaengt, wird gewuerfelt - auf jedem Rechner gleich, weil der
        # Seed vom Host kommt.
        chosen = self.rng.sample(pids, self.n_hunters) if self.n_hunters else []
        self.catches: dict[int, int] = {pid: 0 for pid in pids}
        self.it_time: dict[int, float] = {pid: 0.0 for pid in pids}
        for pid, u in self.units.items():
            u["hunter"] = pid in chosen
            u["cool"] = TAG_COOL if u["hunter"] else 0.0
            u["immune"] = 0.0

    # -- Rollen ---------------------------------------------------------
    def hunters(self) -> list:
        return [u for u in self.units.values() if u.get("hunter")]

    def is_hunter(self, pid: int) -> bool:
        u = self.units.get(pid)
        return bool(u and u.get("hunter"))

    # ------------------------------------------------------------------ #
    def step_world(self, dt):
        for pid, u in self.units.items():
            u["cool"] = max(0.0, u.get("cool", 0.0) - dt)
            if u.get("hunter"):
                self.it_time[pid] = self.it_time.get(pid, 0.0) + dt
                u["slow"] = IT_SPEED
                u["immune"] = 0.0          # als Faenger nuetzt sie nichts
            else:
                u["immune"] = max(0.0, u.get("immune", 0.0) - dt)
                u["score"] += dt
                u["slow"] = 1.0

    def on_contact(self, a, b, closing):
        a_h, b_h = bool(a.get("hunter")), bool(b.get("hunter"))
        if a_h == b_h:
            # Zwei Faenger oder zwei Fluechtende: nur auseinanderschieben
            if closing > 40.0:
                ang = math.atan2(b["y"] - a["y"], b["x"] - a["x"])
                self.knockback(b, ang, 90.0, 0.25)
                self.knockback(a, ang + math.pi, 90.0, 0.25)
            return

        hunter, prey = (a, b) if a_h else (b, a)
        if hunter.get("cool", 0.0) > 0.0 or prey.get("immune", 0.0) > 0.0:
            ang = math.atan2(prey["y"] - hunter["y"], prey["x"] - hunter["x"])
            self.knockback(prey, ang, 120.0, 0.25)
            return

        # Gefangen: Rollen tauschen - die Zahl der Faenger bleibt gleich
        hunter["hunter"] = False
        hunter["immune"] = IMMUNE
        prey["hunter"] = True
        prey["cool"] = TAG_COOL
        self.catches[hunter["pid"]] = self.catches.get(hunter["pid"], 0) + 1
        ang = math.atan2(prey["y"] - hunter["y"], prey["x"] - hunter["x"])
        self.knockback(hunter, ang + math.pi, 220.0, 0.45)
        self.knockback(prey, ang, 120.0, 0.3)
        prey["hit"] = 0.5
        self.ctx.play("whistle")

    # -- Bots -----------------------------------------------------------
    def bot_target(self, u):
        if u.get("hunter"):
            foe = self._prey(u)
            if foe is None:
                return None
            dist = math.hypot(foe["x"] - u["x"], foe["y"] - u["y"])
            # etwas vorhalten, sonst laeuft der Bot immer nur hinterher
            lead = min(1.0, dist / 500.0) * 220.0
            return (foe["x"] + math.cos(foe["h"]) * lead,
                    foe["y"] + math.sin(foe["h"]) * lead,
                    dist < self.RADIUS * 6 and u["dash"] >= self.DASH_TIME)

        threat = self._nearest_hunter(u)
        if threat is None:
            return None
        dist = math.hypot(threat["x"] - u["x"], threat["y"] - u["y"])
        tx, ty = self.push_away_target(u, threat["x"], threat["y"])
        # nicht in die Ecke fliehen - zur Mitte hin ausweichen
        tx = tx * 0.7 + LOGIC_W / 2 * 0.3
        ty = ty * 0.7 + LOGIC_H / 2 * 0.3
        return tx, ty, dist < self.RADIUS * 7 and u["dash"] >= self.DASH_TIME

    def _nearest_hunter(self, u):
        best, best_d = None, 1e18
        for o in self.hunters():
            if o is u:
                continue
            d = (o["x"] - u["x"]) ** 2 + (o["y"] - u["y"]) ** 2
            if d < best_d:
                best_d, best = d, o
        return best

    def _prey(self, u):
        """Wen ein Faenger sich vornimmt.

        Nicht einfach den Naechsten: dann lohnt es sich, weit weg herumzuirren,
        und der Punktestand spielt keine Rolle mehr. Wer viel freie Zeit
        gesammelt hat, ist attraktiver - so wird der Fuehrende automatisch
        gejagt und ein Vorsprung bleibt nie bequem.
        """
        best, best_cost = None, 1e18
        candidates = [o for o in self.units.values()
                      if o is not u and o["alive"] and not o.get("hunter")
                      and o.get("immune", 0.0) <= 0.0]
        top = max((o["score"] for o in candidates), default=0.0) or 1.0
        for o in candidates:
            dist = math.hypot(o["x"] - u["x"], o["y"] - u["y"])
            share = max(0.0, min(1.0, o["score"] / top))
            cost = dist / (0.55 + 0.9 * share)
            if cost < best_cost:
                best_cost, best = cost, o
        return best

    # -- Netz -----------------------------------------------------------
    def world_wire(self):
        return {"its": [u["pid"] for u in self.hunters()]}

    def apply_world_wire(self, data):
        its = data.get("its")
        if its is None:
            return
        wanted = {int(p) for p in its}
        for pid, u in self.units.items():
            u["hunter"] = pid in wanted

    def player_wire(self, u):
        return [self.catches.get(u["pid"], 0), round(u.get("immune", 0.0), 2),
                round(u.get("cool", 0.0), 2)]

    def apply_player_wire(self, u, extra):
        if not extra:
            return
        self.catches[u["pid"]] = int(extra[0])
        if len(extra) > 1:
            u["immune"] = float(extra[1])
        if len(extra) > 2:
            u["cool"] = float(extra[2])

    # -- Ergebnis -------------------------------------------------------
    def score_detail(self, u):
        return "%.1f s frei - %dx gefangen" % (
            u["score"], self.catches.get(u["pid"], 0))

    def finish(self):
        super().finish()
        if not self.ctx.is_host:
            return
        # Gleichstand bei der freien Zeit bricht, wer selbst jemanden gefangen
        # hat: weniger Zeit als Faenger ist besser, und jeder eigene Fang
        # zieht noch ein Stueckchen nach vorn. `time` ist der Entscheider bei
        # gleichem Rohwert (kleiner = besser).
        for pid, r in self.results_map.items():
            r.time = round(self.it_time.get(pid, 0.0)
                           - 0.01 * self.catches.get(pid, 0), 4)

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
        hunter = bool(u.get("hunter"))
        ring = IT_COLOR if hunter else (
            SAFE_COLOR if u.get("immune", 0.0) > 0.0 else None)
        super().draw_unit(surf, u, ring=ring)
        if hunter:
            x, y = self.to_screen(u["x"], u["y"])
            r = self.px(self.RADIUS)
            img = self.ctx.fonts.body_bold(13).render("FAENGER", True, IT_COLOR)
            surf.blit(img, img.get_rect(midtop=(x, y + r + 4)))

    HUD_TITLE = "freie Zeit"

    def hud_own(self, u):
        if u.get("hunter"):
            if u.get("cool", 0.0) > 0.0:
                return "du faengst - noch %.1f s" % u["cool"]
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
        n = len(self.hunters())
        draw_text(surf, fonts.body_bold(14),
                  "1 Faenger" if n == 1 else "%d Faenger" % n, IT_COLOR,
                  (area.right - 170, area.y + 34))
