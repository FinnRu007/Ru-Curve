"""Zielen: Ziele so schnell wie moeglich anklicken.

Einziges Maus-Minispiel. Sitzen mehrere Leute an einer Tastatur, spielen sie
nacheinander (Hot-Seat) - jeder bekommt dieselbe Zielfolge, also gleiche
Bedingungen. Ueber LAN spielt jede Maschine gleichzeitig ihre eigenen Leute ab.
"""

from __future__ import annotations

import random

import pygame

from ...ui.widgets import draw_text
from .. import ui as U
from ..base import MiniGame


class AimGame(MiniGame):
    id = "aim"
    name = "Zielen"
    rules = "Klicke die Ziele so schnell wie moeglich an. Jeder ist einzeln dran."
    input_mode = "mouse"
    hotseat = True
    scoring = "high"
    turn_seconds = 12.0
    n_targets = 40

    @staticmethod
    def make_config(rng, players):
        return {
            "turn_seconds": AimGame.turn_seconds,
            "targets": [(round(rng.uniform(0.08, 0.92), 4),
                         round(rng.uniform(0.10, 0.90), 4),
                         round(rng.uniform(0.55, 1.0), 3))
                        for _ in range(AimGame.n_targets)],
            "bot_seed": rng.randrange(1 << 30),
        }

    def __init__(self, ctx):
        super().__init__(ctx)
        self.turn_seconds = float(self.cfg.get("turn_seconds", 12.0))
        self.targets = self.cfg.get("targets", [])
        self.order = list(ctx.local_pids)
        self.turn = 0
        self.t = 0.0
        self.phase = "ready"          # ready -> play -> ready ...
        self.tindex = 0
        self.hits = {pid: 0 for pid in ctx.local_pids}
        self.spent = {pid: 0.0 for pid in ctx.local_pids}
        self.pop = 0.0
        self.miss_flash = 0.0
        self.max_seconds = (self.turn_seconds + 3.5) * max(1, len(self.order)) + 3
        rng = random.Random(self.cfg.get("bot_seed", 13))
        self._bot_iv = {p.pid: max(0.22, rng.gauss(0.95 - 0.55 * p.difficulty, 0.10))
                        for p in ctx.local_players if p.is_bot}
        self._bot_next = 0.0

    # ------------------------------------------------------------------ #
    @property
    def current_pid(self):
        if self.turn < len(self.order):
            return self.order[self.turn]
        return None

    @property
    def current_player(self):
        pid = self.current_pid
        return self.ctx.player(pid) if pid is not None else None

    def _target_rect(self, area):
        if self.tindex >= len(self.targets):
            return None
        fx, fy, fs = self.targets[self.tindex % len(self.targets)]
        pad = 70
        r = int(26 * fs) + 12
        x = area.x + pad + fx * (area.w - 2 * pad)
        y = area.y + pad + fy * (area.h - 2 * pad - 60)
        return pygame.Rect(int(x - r), int(y - r), r * 2, r * 2)

    # ------------------------------------------------------------------ #
    def handle_events(self, events):
        if self.phase != "play":
            for e in events:
                if e.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                    if self.phase == "ready" and self.current_pid is not None:
                        self.phase = "play"
                        self.t = 0.0
            return
        pid = self.current_pid
        if pid is None:
            return
        p = self.ctx.player(pid)
        if p is not None and p.is_bot:
            return
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                rect = self._target_rect(self.ctx.area)
                if rect and rect.collidepoint(e.pos):
                    self._hit(pid)
                else:
                    self.miss_flash = 0.2
                    self.ctx.play("wrong")

    def _hit(self, pid):
        self.hits[pid] = self.hits.get(pid, 0) + 1
        self.spent[pid] = self.t
        self.tindex += 1
        self.pop = 0.22
        self.ctx.play("correct")

    # ------------------------------------------------------------------ #
    def update(self, dt):
        super().update(dt)
        if self.finished:
            return
        self.pop = max(0.0, self.pop - dt)
        self.miss_flash = max(0.0, self.miss_flash - dt)

        pid = self.current_pid
        if pid is None:
            self.finish()
            return

        p = self.ctx.player(pid)
        if self.phase == "ready":
            self.t += dt
            if p is not None and p.is_bot:
                if self.t > 0.8:
                    self.phase = "play"
                    self.t = 0.0
                    self._bot_next = self._bot_iv.get(pid, 0.6)
            elif self.t > 3.0:            # Notbremse, falls niemand klickt
                self.phase = "play"
                self.t = 0.0
            return

        self.t += dt
        if p is not None and p.is_bot and self.t >= self._bot_next:
            self._hit(pid)
            self._bot_next = self.t + self._bot_iv.get(pid, 0.6)

        if self.t >= self.turn_seconds:
            self.turn += 1
            self.phase = "ready"
            self.t = 0.0
            self.tindex = 0
            if self.turn >= len(self.order):
                self.finish()

    def finish(self):
        for pid in self.ctx.local_pids:
            r = self.results_map[pid]
            r.raw = self.hits.get(pid, 0)
            r.time = round(self.spent.get(pid, self.turn_seconds), 3)
            r.detail = "%d Treffer" % r.raw
        super().finish()

    def live_rows(self):
        return dict(self.hits)

    # ------------------------------------------------------------------ #
    def draw(self, surf):
        area = self.ctx.area
        fonts = self.ctx.fonts
        p = self.current_player
        if p is None:
            U.title(surf, fonts, "Fertig", area.centery - 20, center_x=area.centerx)
            return

        if self.phase == "ready":
            U.title(surf, fonts, p.name + " ist dran", area.centery - 90, size=44,
                    color=p.color, center_x=area.centerx)
            U.subtitle(surf, fonts, "Klicken oder Taste druecken zum Starten",
                       area.centery - 20, size=20, center_x=area.centerx)
            if p.is_bot:
                U.subtitle(surf, fonts, "(Bot spielt gleich)", area.centery + 14, center_x=area.centerx)
            self._turn_strip(surf, area)
            return

        left = max(0.0, self.turn_seconds - self.t)
        draw_text(surf, fonts.body_bold(17), p.name, p.color, (area.x + 6, area.y))
        img = fonts.display(30).render("%.1f s" % left, True,
                                       U.BAD if left < 3 else U.TEXT)
        surf.blit(img, img.get_rect(midtop=(area.centerx, area.y - 4)))
        img2 = fonts.display(26).render(str(self.hits.get(p.pid, 0)), True, U.OK)
        surf.blit(img2, img2.get_rect(topright=(area.right - 6, area.y)))
        U.timer_bar(surf, (area.x, area.y + 40, area.w, 8), left / self.turn_seconds)

        if self.miss_flash > 0:
            s = pygame.Surface(area.size, pygame.SRCALPHA)
            s.fill((240, 92, 92, int(60 * self.miss_flash / 0.2)))
            surf.blit(s, area)

        rect = self._target_rect(area)
        if rect:
            grow = int(6 * self.pop / 0.22)
            r = rect.width // 2 + grow
            c = rect.center
            pygame.draw.circle(surf, U.BAD, c, r)
            pygame.draw.circle(surf, U.TEXT, c, max(3, int(r * 0.62)), 3)
            pygame.draw.circle(surf, U.TEXT, c, max(2, int(r * 0.16)))
        self._turn_strip(surf, area)

    def _turn_strip(self, surf, area):
        fonts = self.ctx.fonts
        locals_ = self.ctx.local_players
        if len(locals_) <= 1:
            return
        x = area.centerx - (len(locals_) * 116) // 2
        y = area.bottom - 46
        for i, p in enumerate(locals_):
            box = pygame.Rect(x, y, 108, 38)
            active = i == self.turn
            U.panel(surf, box, color=U.PANEL_HI if active else U.PANEL,
                    border=p.color if active else None, radius=10)
            draw_text(surf, fonts.body_bold(13), U.fit(fonts.body_bold(13), p.name, 62),
                      U.TEXT if active else U.MUTED, (box.x + 10, box.centery - 8))
            img = fonts.body_bold(14).render(str(self.hits.get(p.pid, 0)), True, U.OK)
            surf.blit(img, img.get_rect(midright=(box.right - 10, box.centery)))
            x += 116
