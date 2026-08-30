"""Rendert die wichtigsten Szenen headless in PNG-Dateien (zur Sichtpruefung)."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Tests niemals auf die echte config.json des Nutzers loslassen
os.environ["RUCURVE_CONFIG"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_tmp", "config.json")

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

    st = SettingsScene(app, back=lambda: m); st.on_enter()
    st.draw(app.screen); save(app, "2_settings")
    st._open = {"spiel"}; st._rebuild_keep_scroll()
    st.draw(app.screen); save(app, "2b_settings_spiel")
    st._open = {"powerups"}; st._open_pu = {"speed"}; st._rebuild_keep_scroll()
    st.draw(app.screen); save(app, "2c_settings_powerups")

    c = ControlsScene(app, back=lambda: m); c.on_enter(); c.draw(app.screen); save(app, "3_controls")

    app.config.settings.countdown_seconds = 0.0
    app.config.settings.target_score = 40
    lob = LobbyScene(app, mode="local"); lob.on_enter()
    for _ in range(4):
        lob._add_bot()
    lob.update(0.0); lob.draw(app.screen); save(app, "4_lobby")

    j = JoinScene(app); j.on_enter(); j.draw(app.screen); save(app, "5_join")

    from rucurve.session import GameSession
    from rucurve.scenes.scoreboard import ScoreboardScene

    sess = GameSession(app.config.settings, lob.players)
    g = GameScene(app, sess); g.on_enter()
    for i in range(60 * 90):
        g.update(1 / 60)
        if i == 120:                      # Nebel zum Anschauen erzwingen
            for cv in g.world.curves:     # andere Effekte (z.B. Invert) kurz weg
                cv.effects.clear()
            g.world.curves[0].effects.append(["fog", 1.5, 150.0])
            g.draw(app.screen); save(app, "6b_fog")
        if g.world.phase == "finished":
            break
    g.draw(app.screen); save(app, "6_game_running")
    for _ in range(60):
        g.update(1 / 60)
    g.draw(app.screen); save(app, "7_round_end_click")

    sb = ScoreboardScene(app, sess); sb.on_enter(); sb.draw(app.screen); save(app, "8_scoreboard")

    print("shots in", OUT)


if __name__ == "__main__":
    main()
