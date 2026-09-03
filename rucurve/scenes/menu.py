"""Hauptmenue."""

from __future__ import annotations

import rucurve
from .. import theme as T
import pygame

from ..ui.widgets import Button, draw_text, wrap_text
from .common import BaseMenuScene


class MenuScene(BaseMenuScene):
    title = "Ru-Curve"
    subtitle = "Turnier mit vielen Minispielen - an einem PC, im WLAN oder uebers Internet"

    def on_enter(self) -> None:
        self.app.audio.music("menu")
        self.build()

    def build(self) -> None:
        w, h = self.size
        cw = 360
        # Bei breitem Fenster nach links ruecken - rechts steht die Erklaerung.
        x = (w - cw) // 2 - (130 if w >= 940 else 0)
        y = 200
        gap = 66

        def add(label, fn, kind="primary"):
            nonlocal y
            self.widgets.append(Button((x, y, cw, 52), label, fn, kind))
            y += gap

        add("An einem PC spielen", self._local)
        add("Spiel eroeffnen  (LAN oder Online)", self._host)
        add("Spiel beitreten  (LAN oder Online)", self._join)
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
    def _draw_mode_help(self, surf) -> None:
        """Erklaert die drei Spielarten - "LAN" allein sagt niemandem etwas.

        Steht als eigene Spalte rechts neben den Knoepfen; ist das Fenster zu
        schmal, faellt sie weg, statt in die Knoepfe zu laufen.
        """
        w, h = self.size
        fonts = self.app.fonts
        btn = next((wd.rect for wd in self.widgets if hasattr(wd, "on_click")), None)
        if btn is None:
            return
        x = btn.right + 34
        box_w = w - x - 48
        if box_w < 200:
            return
        y = btn.y - 4

        draw_text(surf, fonts.body_bold(15), "Was ist was?", T.TEXT, (x, y))
        y += 26
        for label, text in (
            ("An einem PC",
             "Alle sitzen an dieser Tastatur. Jeder hat drei Tasten."),
            ("Spiel eroeffnen",
             "Du bist Gastgeber. Im gleichen WLAN finden dich die anderen von "
             "allein. Von weiter weg schickst du ihnen deine Adresse - die "
             "zeigt die Lobby oben rechts an, fuers WLAN und fuers Internet."),
            ("Spiel beitreten",
             "Bei jemand anderem mitspielen. Im gleichen WLAN aus der Liste "
             "waehlen, sonst die Adresse des Gastgebers eintippen."),
        ):
            draw_text(surf, fonts.body_bold(13), label, T.ACCENT, (x, y))
            y += 19
            for line in wrap_text(fonts.body(12), text, box_w):
                if y > h - 70:
                    return
                draw_text(surf, fonts.body(12), line, T.TEXT_MUTED, (x, y))
                y += 16
            y += 10

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
        self._draw_mode_help(surf)
        draw_text(
            surf,
            self.app.fonts.body(14),
            f"v{rucurve.__version__}   -   Jeder Spieler hat drei Tasten: links, Aktion, rechts",
            T.TEXT_MUTED,
            (w // 2, h - 40),
            center=True,
        )
        self._draw_update_hint(surf)
