"""Sound-/Musik-Verwaltung. Fehlt eine Datei oder das Mixer-Subsystem,
werden alle Aufrufe still ignoriert."""

from __future__ import annotations

import os

import pygame

from . import theme as T

_SFX = ("crash", "powerup", "countdown", "go", "click", "win")


class Audio:
    def __init__(self, settings) -> None:
        self.settings = settings
        self.ok = pygame.mixer.get_init() is not None
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self._music_name: str | None = None
        if self.ok:
            for name in _SFX:
                path = T.asset_path("sounds", f"{name}.wav")
                if os.path.isfile(path):
                    try:
                        self.sounds[name] = pygame.mixer.Sound(path)
                    except pygame.error:
                        pass

    def play(self, name: str) -> None:
        snd = self.sounds.get(name)
        if snd is None:
            return
        snd.set_volume(max(0.0, min(1.0, self.settings.sound_volume)))
        snd.play()

    def music(self, name: str, *, loop: bool = True) -> None:
        if not self.ok:
            return
        if self._music_name == name and pygame.mixer.music.get_busy():
            self.refresh_volume()
            return
        path = T.asset_path("music", f"{name}.ogg")
        if not os.path.isfile(path):
            path = T.asset_path("music", f"{name}.wav")
        if not os.path.isfile(path):
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(max(0.0, min(1.0, self.settings.music_volume)))
            pygame.mixer.music.play(-1 if loop else 0)
            self._music_name = name
        except pygame.error:
            pass

    def stop_music(self) -> None:
        if self.ok:
            pygame.mixer.music.stop()
            self._music_name = None

    def refresh_volume(self) -> None:
        if self.ok:
            pygame.mixer.music.set_volume(max(0.0, min(1.0, self.settings.music_volume)))
