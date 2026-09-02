"""Rendert jedes Minispiel + die Turnier-Bildschirme als PNG zur Sichtpruefung."""

from __future__ import annotations

import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["RUCURVE_CONFIG"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_tmp", "config.json")

import pygame  # noqa: E402

from rucurve.app import App  # noqa: E402
from rucurve.party.registry import GAME_IDS  # noqa: E402
from rucurve.scenes.tournament import TournamentScene  # noqa: E402
from test_party import FakeKeys, make_players  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "_shots_party")
os.makedirs(OUT, exist_ok=True)

# Wie weit soll jedes Spiel laufen, bevor der Screenshot faellt?
WARMUP = {
    "reaction": 2.6, "sequence": 1.2, "math": 1.6, "area": 1.6,
    "estimate": 1.2, "oddone": 1.2, "mash": 2.5, "stopbar": 1.2,
    "timesense": 2.0, "race": 8.0, "curve": 6.0,
}


def shot(app, name):
    pygame.image.save(app.screen, os.path.join(OUT, name + ".png"))


def main():
    rng = random.Random(7)
    app = App()
    app.config.settings.bot_difficulty = 0.6
    players = make_players(app, n_local=2, n_bots=3)

    real = pygame.key.get_pressed
    held = FakeKeys()
    pygame.key.get_pressed = lambda: held

    for i, gid in enumerate(GAME_IDS):
        scene = TournamentScene(app, players, order=[gid], points_top=10)
        scene.on_enter()
        # Intro
        for _ in range(20):
            scene.update(1 / 60)
        scene.draw(app.screen)
        if i == 0:
            shot(app, "0_intro")

        target = WARMUP.get(gid, 2.0)
        frames = 0
        while scene.phase in ("intro", "play") and frames < 60 * 70:
            frames += 1
            evs = []
            if scene.phase == "play":
                if scene.game_cls.input_mode == "mouse" and rng.random() < 0.2:
                    g = scene.game
                    r = g._target_rect(scene.play_rect())
                    if r:
                        evs.append(pygame.event.Event(
                            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": r.center}))
                elif scene.game_cls.input_mode == "keys" and rng.random() < 0.05:
                    p = players[0]
                    b = scene.bindings.get(p.pid)
                    if b:
                        evs.append(pygame.event.Event(
                            pygame.KEYDOWN, {"key": rng.choice(b)}))
                elif scene.game_cls.input_mode == "curve":
                    down = []
                    for p in players[:2]:
                        b = scene.bindings.get(p.pid)
                        if b and rng.random() < 0.5:
                            down.append(b[rng.randrange(3)])
                    held = FakeKeys(down)
            scene.handle_events(evs)
            scene.update(1 / 60)
            if scene.phase == "play" and scene.game.elapsed >= target:
                scene.draw(app.screen)
                shot(app, "%d_%s" % (i + 1, gid))
                break
        else:
            scene.draw(app.screen)
            shot(app, "%d_%s" % (i + 1, gid))

    # Ergebnis- und Endbildschirm
    scene = TournamentScene(app, players, order=["reaction", "mash"], points_top=10)
    scene.on_enter()
    for _ in range(60 * 40):
        scene.update(1 / 60)
        if scene.phase == "result":
            break
    scene.draw(app.screen)
    shot(app, "90_ergebnis")
    scene.tour.index = 99
    scene._finish_tournament()
    scene.draw(app.screen)
    shot(app, "91_endstand")

    pygame.key.get_pressed = real
    print("Screenshots in", OUT)


if __name__ == "__main__":
    main()
