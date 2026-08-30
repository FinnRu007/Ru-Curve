"""Gemeinsame Bausteine fuer Menue-artige Szenen."""

from __future__ import annotations

import pygame

from .. import theme as T
from ..ui.widgets import Widget, draw_text


class BaseMenuScene:
    """Basisklasse: weisser Hintergrund, Kopfzeile, Liste von Widgets."""

    title = "Ru-Curve"
    subtitle = ""

    def __init__(self, app) -> None:
        self.app = app
        self.widgets: list[Widget] = []
        self._overlay_widgets: list = []

    # -- lifecycle ------------------------------------------------------
    def on_enter(self) -> None:
        self.build()

    def on_exit(self) -> None:
        pass

    def build(self) -> None:
        """Von Unterklassen ueberschrieben - baut self.widgets."""

    def rebuild(self) -> None:
        self.widgets.clear()
        self.build()

    # -- helpers ------------------------------------------------------
    @property
    def size(self):
        return self.app.screen.get_size()

    def content_rect(self) -> pygame.Rect:
        w, h = self.size
        cw = min(880, w - 80)
        return pygame.Rect((w - cw) // 2, 120, cw, h - 180)

    # -- events / update / draw --------------------------------------
    def handle_events(self, events) -> None:
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                if self.on_escape():
                    continue
            # Overlays (offene Dropdowns) zuerst
            handled = False
            for w in self._overlay_widgets:
                if w.open and w.handle_event(e):
                    handled = True
                    break
            if handled:
                continue
            for w in self.widgets:
                if w.handle_event(e):
                    break

    def on_escape(self) -> bool:
        return False

    def update(self, dt: float) -> None:
        for w in self.widgets:
            w.update(dt)

    def draw(self, surf) -> None:
        surf.fill(T.BG)
        w, h = self.size
        # Kopf
        draw_text(surf, self.app.fonts.display(34), self.title, T.TEXT, (48, 44))
        if self.subtitle:
            draw_text(surf, self.app.fonts.body(17), self.subtitle, T.TEXT_MUTED, (50, 86))
        pygame.draw.line(surf, T.BORDER, (48, 112), (w - 48, 112), 1)

        self._overlay_widgets = [x for x in self.widgets if x.__class__.__name__ == "Dropdown"]
        for x in self.widgets:
            x.draw(surf, self.app.fonts)
        for x in self._overlay_widgets:
            if getattr(x, "open", False):
                x.draw_overlay(surf, self.app.fonts)

    # -- navigation --------------------------------------------------
    def go(self, scene) -> None:
        self.app.audio.play("click")
        self.app.set_scene(scene)
