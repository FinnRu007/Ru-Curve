"""Anwendungsgeruest: Fenster, Hauptschleife, Szenenverwaltung."""

from __future__ import annotations

import os

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
        # Schaut im Hintergrund, ob es auf der Ru-Services-Seite eine
        # neuere Version gibt (blockiert nie den Start).
        from .net.internet import UpdateCheck

        self.update_check = UpdateCheck()
        self.update_check.start()

    # ------------------------------------------------------------------ #
    def _desktop_size(self) -> tuple[int, int]:
        try:
            return pygame.display.get_desktop_sizes()[0]
        except Exception:
            info = pygame.display.Info()
            return info.current_w, info.current_h

    def _fit_size(self, w: int, h: int) -> tuple[int, int]:
        dw, dh = self._desktop_size()
        w = min(int(w), dw - 20)
        h = min(int(h), dh - 90)          # Platz fuer Titelleiste + Taskleiste
        return max(900, w), max(600, h)

    def _build_window(self) -> None:
        s = self.config.settings
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        icon_path = T.asset_path("icon.png")
        try:
            if os.path.isfile(icon_path):
                pygame.display.set_icon(pygame.image.load(icon_path))
        except pygame.error:
            pass
        if s.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            w, h = self._fit_size(s.window_width, s.window_height)
            self.screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
        pygame.display.set_caption("Ru-Curve")

    def rebuild_window(self) -> None:
        self._build_window()

    def _on_resize(self, w: int, h: int) -> None:
        w, h = max(900, w), max(600, h)
        self.config.settings.window_width = w
        self.config.settings.window_height = h
        self.screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
        if self.scene is not None and hasattr(self.scene, "resize"):
            self.scene.resize()

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
    def run(self, splash: bool = True) -> None:
        from .scenes.menu import MenuScene
        from .scenes.splash import SplashScene

        self.set_scene(SplashScene(self) if splash else MenuScene(self))
        self._swap_scene()

        while self.running:
            dt = min(0.05, self.clock.tick(self.FPS) / 1000.0)
            events = pygame.event.get()
            resized = None
            for e in events:
                if e.type == pygame.QUIT:
                    self.running = False
                elif e.type == pygame.VIDEORESIZE and not self.config.settings.fullscreen:
                    resized = (e.w, e.h)
            if resized is not None:
                self._on_resize(*resized)
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
