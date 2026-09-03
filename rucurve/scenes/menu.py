"""Hauptmenue."""

from __future__ import annotations

import rucurve
from .. import theme as T
import pygame

from ..ui.widgets import Button, draw_text, wrap_text
from .common import BaseMenuScene


class MenuScene(BaseMenuScene):
    title = "Ru-Curve"
    subtitle = "Turnier mit 11 Minispielen - lokal an einem PC oder zusammen im LAN"

    def on_enter(self) -> None:
        self.app.audio.music("menu")
        self.build()

    def build(self) -> None:
        w, h = self.size
        cw = 360
        x = (w - cw) // 2
        y = 200
        gap = 66

        def add(label, fn, kind="primary"):
            nonlocal y
            self.widgets.append(Button((x, y, cw, 52), label, fn, kind))
            y += gap

        add("An einem PC spielen", self._local)
        add("Uber LAN hosten", self._host)
        add("Uber LAN beitreten", self._join)
        y += 10
        add("Einstellungen", self._settings, "ghost")
        add("Steuerung", self._controls, "ghost")
        add("Beenden", self._quit, "ghost")
        # Update-Band ueber die Knoepfe - der Streifen unter der Kopfzeile ist
        # ohnehin frei, unten wuerde es bei kleinen Fenstern kollidieren.
        self._update_rect = pygame.Rect(w // 2 - 260, 138, 520, 44)

    # ------------------------------------------------------------------ #
    def handle_events(self, events) -> None:
        chk = getattr(self.app, "update_check", None)
        box = getattr(self, "_update_rect", None)
        if chk is not None and chk.available and box is not None:
            for e in events:
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1                         and box.collidepoint(e.pos):
                    import webbrowser

                    try:
                        webbrowser.open(chk.page)
                    except Exception:
                        pass
                    return
        super().handle_events(events)

    def _local(self) -> None:
        from .lobby import LobbyScene

        self.go(LobbyScene(self.app, mode="local"))

    def _host(self) -> None:
        from .lobby import LobbyScene

        self.go(LobbyScene(self.app, mode="host"))

    def _join(self) -> None:
        from .join import JoinScene

        self.go(JoinScene(self.app))

    def _settings(self) -> None:
        from .settings_scene import SettingsScene

        self.go(SettingsScene(self.app, back=lambda: MenuScene(self.app)))

    def _controls(self) -> None:
        from .controls import ControlsScene

        self.go(ControlsScene(self.app, back=lambda: MenuScene(self.app)))

    def _quit(self) -> None:
        self.app.running = False

    # ------------------------------------------------------------------ #
    def _draw_update_hint(self, surf) -> None:
        """Band mit Hinweis, wenn auf der Ru-Services-Seite etwas Neues liegt."""
        chk = getattr(self.app, "update_check", None)
        if chk is None or not chk.available:
            return
        box = getattr(self, "_update_rect", None)
        if box is None:
            return
        from ..ui.widgets import hover_here

        fonts = self.app.fonts
        hover = hover_here(box)
        pygame.draw.rect(surf, T.SURFACE_ALT if hover else T.ACCENT_SOFT, box,
                         border_radius=T.R_PILL)
        pygame.draw.rect(surf, T.ACCENT, box, width=3 if hover else 2,
                         border_radius=T.R_PILL)
        text = "Neue Version %s verfuegbar - hier klicken zum Herunterladen" % chk.latest
        draw_text(surf, fonts.body_bold(15), text, T.ACCENT_DARK,
                  box.center, center=True)

    # ------------------------------------------------------------------ #
    def draw(self, surf) -> None:
        super().draw(surf)
        w, h = self.size
        draw_text(
            surf,
            self.app.fonts.body(14),
            f"v{rucurve.__version__}   -   Jeder Spieler hat drei Tasten: links, Aktion, rechts",
            T.TEXT_MUTED,
            (w // 2, h - 40),
            center=True,
        )
        self._draw_update_hint(surf)
