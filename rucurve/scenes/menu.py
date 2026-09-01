"""Hauptmenue."""

from __future__ import annotations

import rucurve
from .. import theme as T
from ..ui.widgets import Button, draw_text
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

    # ------------------------------------------------------------------ #
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
