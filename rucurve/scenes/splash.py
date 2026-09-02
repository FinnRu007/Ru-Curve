"""Startanimation "Ru-Services" - kurz, wie das Logo vor einem Unity-Spiel.

Eine Kurve zeichnet sich um den Schriftzug, der dabei aufblendet; danach
blendet alles weg und das Hauptmenue kommt. Jede Taste oder ein Klick
ueberspringt sie.
"""

from __future__ import annotations

import math

import pygame

from ..party import ui as U

DURATION = 3.1
DRAW_IN = 1.5          # bis wann die Kurve gezeichnet ist
TEXT_IN = 0.75         # ab wann der Schriftzug aufblendet
FADE_OUT = 0.55        # letzte Sekunden: Ausblenden


class SplashScene:
    def __init__(self, app, nxt=None) -> None:
        self.app = app
        self._next = nxt
        self.t = 0.0
        self._done = False
        self._played = False

    # ------------------------------------------------------------------ #
    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        pass

    def resize(self) -> None:
        pass

    def handle_events(self, events) -> None:
        for e in events:
            if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self._finish()
                return

    def update(self, dt: float) -> None:
        self.t += dt
        if not self._played and self.t >= TEXT_IN:
            self._played = True
            self.app.audio.play("whistle")
        if self.t >= DURATION:
            self._finish()

    def _finish(self) -> None:
        if self._done:
            return
        self._done = True
        from .menu import MenuScene

        self.app.set_scene(self._next() if self._next else MenuScene(self.app))

    # ------------------------------------------------------------------ #
    def draw(self, surf) -> None:
        U.backdrop(surf)
        w, h = surf.get_size()
        cx, cy = w // 2, h // 2
        fonts = self.app.fonts

        prog = min(1.0, self.t / DRAW_IN)
        eased = 1.0 - (1.0 - prog) ** 3

        # Die Kurve zeichnet sich - eine Schleife um den Schriftzug
        radius = min(w, h) * 0.22
        pts = []
        steps = max(2, int(240 * eased))
        for i in range(steps):
            a = -math.pi * 0.5 + (i / 240) * math.tau
            r = radius * (1.0 + 0.16 * math.sin(a * 3))
            pts.append((cx + math.cos(a) * r * 1.5, cy + math.sin(a) * r))
        if len(pts) > 1:
            pygame.draw.lines(surf, U.ACCENT, False, pts, 7)
            head = pts[-1]
            pygame.draw.circle(surf, (255, 255, 255), (int(head[0]), int(head[1])), 9)
            pygame.draw.circle(surf, U.ACCENT, (int(head[0]), int(head[1])), 5)

        # Schriftzug blendet auf
        if self.t > TEXT_IN:
            k = min(1.0, (self.t - TEXT_IN) / 0.7)
            alpha = int(255 * k)
            size = int(64 + 8 * (1 - k))
            ru = fonts.display(size).render("Ru", True, U.ACCENT)
            se = fonts.display(size).render("-Services", True, U.TEXT)
            total = ru.get_width() + se.get_width()
            x = cx - total // 2
            for img, dx in ((ru, 0), (se, ru.get_width())):
                img = img.copy()
                img.set_alpha(alpha)
                surf.blit(img, (x + dx, cy - img.get_height() // 2))

        if self.t > TEXT_IN + 0.5:
            k = min(1.0, (self.t - TEXT_IN - 0.5) / 0.6)
            sub = fonts.body(18).render("praesentiert", True, U.MUTED)
            sub.set_alpha(int(200 * k))
            surf.blit(sub, sub.get_rect(midtop=(cx, cy + 52)))

        # Ausblenden zum Schluss
        left = DURATION - self.t
        if left < FADE_OUT:
            veil = pygame.Surface((w, h))
            veil.fill((0, 0, 0))
            veil.set_alpha(int(255 * (1.0 - max(0.0, left) / FADE_OUT)))
            surf.blit(veil, (0, 0))

        hint = fonts.body(13).render("Taste druecken zum Ueberspringen", True, U.MUTED)
        surf.blit(hint, hint.get_rect(midbottom=(cx, h - 18)))
