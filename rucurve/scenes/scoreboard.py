"""Zwischenstand nach jeder Runde + Siegerbildschirm am Matchende."""

from __future__ import annotations

import pygame

from .. import theme as T
from ..colors import color_for
from ..ui.widgets import Button, draw_text
from .common import BaseMenuScene


class ScoreboardScene(BaseMenuScene):
    def __init__(self, app, session) -> None:
        super().__init__(app)
        self.session = session
        self.winner = session.match_winner()
        self.title = "Match gewonnen!" if self.winner else "Zwischenstand"
        self._auto = 8.0 if not self.winner else 1e9

    def on_enter(self) -> None:
        if self.winner:
            self.app.audio.play("win")
            if self.session.host:
                self.session.host.broadcast({
                    "type": "match_over",
                    "winner": {"name": self.winner.name, "color_index": self.winner.color_index},
                    "standings": self.session.standings(),
                })
        self.build()

    def build(self) -> None:
        w, h = self.size
        cx = w // 2
        self.widgets = []
        if self.winner:
            self.widgets.append(Button((cx - 170, h - 90, 340, 48), "Zurueck zur Lobby", self._to_lobby, "primary"))
        else:
            self.widgets.append(Button((cx - 170, h - 90, 340, 48), "Naechste Runde", self._next_round, "primary"))
            self.widgets.append(Button((w - 210, h - 90, 170, 48), "Match beenden", self._to_lobby, "ghost"))

    # ------------------------------------------------------------------ #
    def _next_round(self) -> None:
        from .game import GameScene

        self.app.audio.play("click")
        self.app.set_scene(GameScene(self.app, self.session))

    def _to_lobby(self) -> None:
        self.app.audio.play("click")
        # Punkte zuruecksetzen fuer ein neues Match
        for c in self.session.curves:
            c.score = 0
        if self.session.host or self.session.beacon:
            from .lobby import LobbyScene

            scene = LobbyScene(self.app, mode="host")
            scene.adopt(self.session)
            self.app.set_scene(scene)
        else:
            from .lobby import LobbyScene

            scene = LobbyScene(self.app, mode="local")
            scene.adopt(self.session)
            self.app.set_scene(scene)

    def update(self, dt: float) -> None:
        super().update(dt)
        self._auto -= dt
        if self._auto <= 0 and not self.winner:
            self._next_round()

    # ------------------------------------------------------------------ #
    def draw(self, surf) -> None:
        surf.fill(T.BG)
        w, h = self.size
        draw_text(surf, self.app.fonts.display(36), self.title, T.TEXT, (48, 40))
        if self.winner:
            draw_text(surf, self.app.fonts.body(18),
                      f"{self.winner.name} erreicht {self.winner.score} Punkte.",
                      color_for(self.winner.color_index), (50, 88))
        else:
            draw_text(surf, self.app.fonts.body(16),
                      f"Ziel: {self.session.settings.target_score} Punkte   -   naechste Runde automatisch in {max(0, int(self._auto))}s",
                      T.TEXT_MUTED, (50, 88))
        pygame.draw.line(surf, T.BORDER, (48, 118), (w - 48, 118), 1)

        rows = self.session.standings()
        last = self.session.world.round_standings if self.session.world else []
        gained = {r["id"]: r["gained"] for r in (last or [])}
        y = 150
        for i, r in enumerate(rows, start=1):
            box = pygame.Rect(60, y, min(760, w - 120), 52)
            pygame.draw.rect(surf, T.SURFACE if i > 1 else T.ACCENT_SOFT, box, border_radius=T.R_SM)
            pygame.draw.rect(surf, color_for(r["color_index"]), (box.x, box.y, 6, box.h), border_radius=3)
            draw_text(surf, self.app.fonts.display(20), f"{i}", T.TEXT_MUTED, (box.x + 20, box.y + 14))
            draw_text(surf, self.app.fonts.body_bold(18), r["name"], T.TEXT, (box.x + 60, box.y + 8))
            g = gained.get(r["pid"])
            if g is not None:
                draw_text(surf, self.app.fonts.body(14), f"+{g}", T.OK, (box.x + 60, box.y + 30))
            draw_text(surf, self.app.fonts.display(22), str(r["score"]), T.TEXT, (box.right - 30, box.y + 12), right=True)
            y += 60

        for wd in self.widgets:
            wd.draw(surf, self.app.fonts)
