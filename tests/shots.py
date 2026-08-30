"""Rendert die wichtigsten Szenen headless in PNG-Dateien (zur Sichtpruefung)."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pygame  # noqa

from rucurve.app import App
from rucurve.scenes.menu import MenuScene
from rucurve.scenes.lobby import LobbyScene
from rucurve.scenes.settings_scene import SettingsScene
from rucurve.scenes.controls import ControlsScene
from rucurve.scenes.game import GameScene
from rucurve.scenes.join import JoinScene

OUT = os.path.join(os.path.dirname(__file__), "_shots")
os.makedirs(OUT, exist_ok=True)


def save(app, name):
    pygame.image.save(app.screen, os.path.join(OUT, name + ".png"))


def main():
    app = App()

    m = MenuScene(app); m.on_enter(); m.draw(app.screen); save(app, "1_menu")

    s = SettingsScene(app, back=lambda: m); s.on_enter(); s.draw(app.screen); save(app, "2_settings")

    c = ControlsScene(app, back=lambda: m); c.on_enter(); c.draw(app.screen); save(app, "3_controls")

    lob = LobbyScene(app, mode="local"); lob.on_enter()
    lob._add_bot(); lob.update(0.0); lob.draw(app.screen); save(app, "4_lobby")

    j = JoinScene(app); j.on_enter(); j.draw(app.screen); save(app, "5_join")

    app.config.settings.countdown_seconds = 1.0
    app.config.settings.bot_count = 4
    lob2 = LobbyScene(app, mode="local"); lob2.on_enter()
    from rucurve.session import GameSession
    g = GameScene(app, GameSession(app.config.settings, lob2.players))
    g.on_enter()
    for i in range(60 * 16):
        g.update(1 / 60)
        if g.world.phase == "finished":
            break
    g.draw(app.screen); save(app, "6_game_running")
    for i in range(60 * 40):
        g.update(1 / 60)
        if g.world.phase == "finished":
            break
    g.draw(app.screen); save(app, "7_game_over")

    print("shots in", OUT)


if __name__ == "__main__":
    main()
