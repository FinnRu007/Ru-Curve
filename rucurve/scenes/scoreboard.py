"""Zwischenstand nach jeder Runde + Siegerbildschirm am Matchende.

Die Liste ist scrollbar (Mausrad / Pfeiltasten / Bild auf-ab) und bricht bei
vielen Spielern automatisch in zwei Spalten um.
"""

from __future__ import annotations

import pygame

from .. import theme as T
from ..colors import color_for
from ..ui.widgets import Button, draw_text
from .common import BaseMenuScene

ROW_H = 58
ROW_GAP = 6


class ScoreboardScene(BaseMenuScene):
    def __init__(self, app, session) -> None:
        super().__init__(app)
        self.session = session
        self.winner = session.match_winner()
        self.title = "Match gewonnen!" if self.winner else "Zwischenstand"
        self.scroll_y = 0
        self._rows: list[dict] = []
        self._list_rect = pygame.Rect(0, 0, 10, 10)
        self._cols = 1
        self._content_h = 0

    # ------------------------------------------------------------------ #
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

    def resize(self) -> None:
        self.build()

    def build(self) -> None:
        w, h = self.size
        self._rows = self.session.standings()
        self._list_rect = pygame.Rect(48, 132, w - 96, h - 132 - 96)
        self._cols = 2 if (len(self._rows) > 9 and self._list_rect.w >= 900) else 1
        per_col = (len(self._rows) + self._cols - 1) // max(1, self._cols)
        self._content_h = max(0, per_col * (ROW_H + ROW_GAP))
        self.scroll_y = min(self.scroll_y, self._max_scroll())

        cx = w // 2
        self.widgets = []
        if self.winner:
            self.widgets.append(Button((cx - 170, h - 74, 340, 48), "Zurueck zur Lobby",
                                       self._to_lobby, "primary"))
        else:
            self.widgets.append(Button((cx - 180, h - 74, 360, 48), "Naechste Runde",
                                       self._next_round, "primary"))
            self.widgets.append(Button((w - 210, h - 74, 170, 48), "Match beenden",
                                       self._to_lobby, "ghost"))

    def _max_scroll(self) -> int:
        return max(0, self._content_h - self._list_rect.h)

    # ------------------------------------------------------------------ #
    def _next_round(self) -> None:
        from .game import GameScene

        self.app.audio.play("click")
        self.app.set_scene(GameScene(self.app, self.session))

    def _to_lobby(self) -> None:
        from .lobby import LobbyScene

        self.app.audio.play("click")
        for c in self.session.curves:      # Punkte fuer ein neues Match zuruecksetzen
            c.score = 0
        mode = "host" if (self.session.host or self.session.beacon) else "local"
        scene = LobbyScene(self.app, mode=mode)
        scene.adopt(self.session)
        self.app.set_scene(scene)

    # ------------------------------------------------------------------ #
    def handle_events(self, events) -> None:
        for e in events:
            if e.type == pygame.MOUSEWHEEL:
                self.scroll_y = max(0, min(self._max_scroll(), self.scroll_y - e.y * 50))
                continue
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                    step = 60 if e.key == pygame.K_DOWN else self._list_rect.h
                    self.scroll_y = min(self._max_scroll(), self.scroll_y + step)
                    continue
                if e.key in (pygame.K_UP, pygame.K_PAGEUP):
                    step = 60 if e.key == pygame.K_UP else self._list_rect.h
                    self.scroll_y = max(0, self.scroll_y - step)
                    continue
                if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    (self._to_lobby if self.winner else self._next_round)()
                    return
            for wd in self.widgets:
                if wd.handle_event(e):
                    break

    # ------------------------------------------------------------------ #
    def draw(self, surf) -> None:
        surf.fill(T.BG)
        w, h = self.size
        fonts = self.app.fonts

        draw_text(surf, fonts.display(34), self.title, T.TEXT, (48, 36))
        if self.winner:
            draw_text(surf, fonts.body(18), f"{self.winner.name} erreicht {self.winner.score} Punkte.",
                      color_for(self.winner.color_index), (50, 82))
        else:
            draw_text(surf, fonts.body(16),
                      f"Ziel: {self.session.settings.target_score} Punkte   -   "
                      f"{len(self._rows)} Spieler",
                      T.TEXT_MUTED, (50, 82))
        pygame.draw.line(surf, T.BORDER, (48, 118), (w - 48, 118), 1)

        self._draw_list(surf, fonts)

        for wd in self.widgets:
            wd.draw(surf, fonts)

    def _draw_list(self, surf, fonts) -> None:
        last = self.session.world.round_standings if self.session.world else []
        gained = {r["id"]: r["gained"] for r in (last or [])}
        area = self._list_rect
        per_col = (len(self._rows) + self._cols - 1) // max(1, self._cols)
        col_w = (area.w - (self._cols - 1) * 18) // self._cols

        prev_clip = surf.get_clip()
        surf.set_clip(area)
        for i, r in enumerate(self._rows, start=1):
            col = (i - 1) // per_col if per_col else 0
            row_in_col = (i - 1) % per_col if per_col else 0
            x = area.x + col * (col_w + 18)
            y = area.y + row_in_col * (ROW_H + ROW_GAP) - self.scroll_y
            if y + ROW_H < area.y - 10 or y > area.bottom + 10:
                continue
            self._draw_row(surf, fonts, pygame.Rect(x, y, col_w, ROW_H), i, r, gained)
        surf.set_clip(prev_clip)

        if self._max_scroll() > 0:
            track = pygame.Rect(area.right - 5, area.y, 4, area.h)
            pygame.draw.rect(surf, T.SURFACE_ALT, track, border_radius=2)
            frac = area.h / max(1, self._content_h)
            bh = max(28, int(area.h * frac))
            by = area.y + int((area.h - bh) * (self.scroll_y / self._max_scroll()))
            pygame.draw.rect(surf, T.BORDER, (track.x, by, 4, bh), border_radius=2)
            draw_text(surf, fonts.body(13), "scrollen mit Mausrad / Pfeiltasten",
                      T.TEXT_MUTED, (area.x, area.bottom + 6))

    def _draw_row(self, surf, fonts, box, place, r, gained) -> None:
        pygame.draw.rect(surf, T.ACCENT_SOFT if place == 1 else T.SURFACE, box, border_radius=T.R_SM)
        pygame.draw.rect(surf, color_for(r["color_index"]), (box.x, box.y, 6, box.h), border_radius=3)
        draw_text(surf, fonts.display(19), str(place), T.TEXT_MUTED, (box.x + 20, box.y + 17))
        draw_text(surf, fonts.body_bold(18), r["name"][:16], T.TEXT, (box.x + 62, box.y + 10))
        g = gained.get(r["pid"])
        if g is not None:
            draw_text(surf, fonts.body(14), f"+{g}", T.OK if g else T.TEXT_MUTED,
                      (box.x + 62, box.y + 32))
        draw_text(surf, fonts.display(22), str(r["score"]), T.TEXT,
                  (box.right - 22, box.y + 15), right=True)
