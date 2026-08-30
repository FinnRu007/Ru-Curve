"""Anwendungsgeruest: Fenster, Hauptschleife, Szenenverwaltung."""

from __future__ import annotations

import pygame

from . import theme as T
from .audio import Audio
from .config import Config


class Scene:
    def __init__(self, app: "App") -> None:
        self.app = app

    @property
    def size(self):
        return self.app.screen.get_size()

    def on_enter(self) -> None: ...
    def on_exit(self) -> None: ...
    def handle_events(self, events) -> None: ...
    def update(self, dt: float) -> None: ...
    def draw(self, surf) -> None: ...


class App:
    FPS = 144

    def __init__(self) -> None:
        pygame.init()
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        except pygame.error:
            pass
        self.config = Config.load()
        self.fonts = T.FontBook()
        self.audio = Audio(self.config.settings)
        self.screen = None
        self._build_window()
        self.clock = pygame.time.Clock()
        self.running = True
        self.scene: Scene | None = None
        self._pending_scene: Scene | None = None

    # ------------------------------------------------------------------ #
    def _build_window(self) -> None:
        s = self.config.settings
        icon_path = T.asset_path("icon.png")
        try:
            if pygame.image.get_extended():
                import os

                if os.path.isfile(icon_path):
                    pygame.display.set_icon(pygame.image.load(icon_path))
        except pygame.error:
            pass
        if s.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((s.window_width, s.window_height))
        pygame.display.set_caption("Ru-Curve")

    def rebuild_window(self) -> None:
        self._build_window()

    # ------------------------------------------------------------------ #
    def set_scene(self, scene: Scene) -> None:
        self._pending_scene = scene

    def _swap_scene(self) -> None:
        if self._pending_scene is None:
            return
        if self.scene is not None:
            self.scene.on_exit()
        self.scene = self._pending_scene
        self._pending_scene = None
        self.scene.on_enter()

    def save_config(self) -> None:
        self.config.save()

    # ------------------------------------------------------------------ #
    def run(self) -> None:
        from .scenes.menu import MenuScene

        self.set_scene(MenuScene(self))
        self._swap_scene()

        while self.running:
            dt = min(0.05, self.clock.tick(self.FPS) / 1000.0)
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    self.running = False
            if self.scene is not None:
                self.scene.handle_events(events)
                self.scene.update(dt)
                self.scene.draw(self.screen)
            pygame.display.flip()
            if self._pending_scene is not None:
                self._swap_scene()

        if self.scene is not None:
            self.scene.on_exit()
        self.save_config()
        pygame.quit()
