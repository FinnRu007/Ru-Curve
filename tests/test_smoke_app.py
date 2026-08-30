"""Startet die App headless und klickt sich durch Menue -> Lobby -> Spiel ->
Scoreboard, um Laufzeitfehler in den Szenen zu finden."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Tests niemals auf die echte config.json des Nutzers loslassen
os.environ["RUCURVE_CONFIG"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_tmp", "config.json")

import pygame  # noqa: E402

from rucurve.app import App  # noqa: E402
from rucurve.scenes.menu import MenuScene  # noqa: E402
from rucurve.scenes.lobby import LobbyScene  # noqa: E402
from rucurve.scenes.game import GameScene  # noqa: E402
from rucurve.scenes.scoreboard import ScoreboardScene  # noqa: E402


def run():
    app = App()
    surf = app.screen

    menu = MenuScene(app)
    menu.on_enter()
    menu.draw(surf)

    lobby = LobbyScene(app, mode="local")
    lobby.on_enter()
    # Nur 2 lokale Spieler + 2 Bots, damit die Runde schnell endet
    lobby._add_bot()
    lobby._add_bot()
    lobby.update(0.016)
    lobby.draw(surf)

    app.config.settings.countdown_seconds = 0.0
    app.config.settings.target_score = 3
    lobby._start()
    assert isinstance(app._pending_scene, GameScene)
    game = app._pending_scene
    app._swap_scene()

    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (10, 10)})

    rounds_seen = 0
    clicks = 0
    for i in range(60 * 180):  # bis zu 3 Minuten Spiel-Zeit simulieren
        game.update(1 / 60)
        if i % 20 == 0:
            game.draw(surf)
        # Runde vorbei -> das Feld bleibt stehen, bis geklickt wird
        if getattr(game, "_await_click", False):
            game.draw(surf)
            game.handle_events([click])
            clicks += 1
        nxt = app._pending_scene
        if isinstance(nxt, ScoreboardScene):
            app._swap_scene()
            nxt.draw(surf)
            rounds_seen += 1
            if nxt.winner:
                break
            nxt._next_round()
            app._swap_scene()
            game = app.scene
    else:
        raise AssertionError("Match wurde nie entschieden")

    assert clicks >= rounds_seen, "Runde muss auf einen Klick warten"
    print(f"ok   Match nach {rounds_seen} Runde(n) entschieden ({clicks} Weiter-Klicks)")
    pygame.quit()


if __name__ == "__main__":
    run()
