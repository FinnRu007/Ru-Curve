"""Faehrt ein komplettes Turnier durch alle Minispiele - headless.

Findet Laufzeitfehler in jedem einzelnen Minispiel und prueft, dass am Ende
eine sinnvolle Rangliste steht.
"""

from __future__ import annotations

import os
import random
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ["RUCURVE_CONFIG"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_tmp", "config.json")

import pygame  # noqa: E402

from rucurve.app import App  # noqa: E402
from rucurve.colors import color_for  # noqa: E402
from rucurve.party.base import PartyPlayer, Result  # noqa: E402
from rucurve.party.registry import ALL_GAMES, GAME_IDS  # noqa: E402
from rucurve.party.tournament import Tournament, points_for_place, rank_results  # noqa: E402
from rucurve.scenes.tournament import TournamentScene  # noqa: E402


class FakeKeys:
    def __init__(self, down=()):
        self.down = set(down)

    def __getitem__(self, k):
        return k in self.down


def make_players(app, n_local=2, n_bots=2):
    players = []
    pid = 0
    for i in range(n_local):
        app.config.slots[i].enabled = True
        s = app.config.slots[i]
        players.append(PartyPlayer(pid, s.name, color_for(s.color_index),
                                   s.color_index, is_local=True, slot_index=i))
        pid += 1
    for b in range(n_bots):
        players.append(PartyPlayer(pid, "Bot %d" % (b + 1), color_for(6 + b),
                                   6 + b, is_local=True, is_bot=True,
                                   difficulty=0.6))
        pid += 1
    return players


def run_tournament(order, n_local=2, n_bots=2, seed=1, verbose=True):
    rng = random.Random(seed)
    app = App()
    app.config.settings.bot_difficulty = 0.6
    players = make_players(app, n_local, n_bots)
    scene = TournamentScene(app, players, order=list(order), points_top=10)
    scene.on_enter()

    real_get_pressed = pygame.key.get_pressed
    held = FakeKeys()
    pygame.key.get_pressed = lambda: held

    human = [p for p in players if p.is_local and not p.is_bot]
    seen_games = set()
    t0 = time.time()
    try:
        for frame in range(60 * 900):        # harte Obergrenze
            if scene.phase == "over":
                break
            if scene.game_cls:
                seen_games.add(scene.game_cls.id)

            events = []
            if scene.phase == "play":
                # Menschen druecken ab und zu zufaellig eine ihrer drei Tasten
                for p in human:
                    b = scene.bindings.get(p.pid)
                    if b and rng.random() < 0.06:
                        events.append(pygame.event.Event(
                            pygame.KEYDOWN, {"key": rng.choice(b)}))
                if scene.game_cls and scene.game_cls.input_mode == "mouse":
                    area = scene.play_rect()
                    if rng.random() < 0.10:
                        g = scene.game
                        rect = g._target_rect(area) if hasattr(g, "_target_rect") else None
                        pos = rect.center if rect else area.center
                        events.append(pygame.event.Event(
                            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": pos}))
                if scene.game_cls and scene.game_cls.input_mode == "curve":
                    down = []
                    for p in human:
                        b = scene.bindings.get(p.pid)
                        if b:
                            down.append(b[rng.randrange(3)])
                    held = FakeKeys(down)

            scene.handle_events(events)
            scene.update(1 / 60.0)
            if frame % 17 == 0:
                scene.draw(app.screen)
            if scene.phase == "result":
                scene._advance_from_result()
        else:
            raise AssertionError("Turnier wurde nie fertig (Phase %s)" % scene.phase)
    finally:
        pygame.key.get_pressed = real_get_pressed

    if verbose:
        print("   %d Spiele in %.1f s Rechenzeit" % (len(order), time.time() - t0))
    return scene, seen_games


# =========================================================================== #
def test_points_and_ranking():
    assert points_for_place(1, 4, 10) == 10
    assert points_for_place(4, 4, 10) == 1
    assert points_for_place(1, 1, 10) == 10
    res = {1: Result(5, 2.0, done=True), 2: Result(5, 1.0, done=True),
           3: Result(9, 9.0, done=True), 4: Result(0, 0, done=False)}
    rows = {r["pid"]: r for r in rank_results(res, "high")}
    assert rows[3]["place"] == 1, "hoechster Rohwert gewinnt"
    assert rows[2]["place"] == 2, "bei Gleichstand die schnellere Zeit"
    assert rows[1]["place"] == 3
    assert rows[4]["place"] == 4, "wer nicht mitspielt, ist hinten"


def test_ranking_low_is_better():
    res = {1: Result(0.30, 0.30, done=True), 2: Result(0.22, 0.22, done=True)}
    rows = {r["pid"]: r for r in rank_results(res, "low")}
    assert rows[2]["place"] == 1


def test_build_order_covers_all_games():
    order = Tournament.build_order(random.Random(4), GAME_IDS, len(GAME_IDS))
    assert sorted(order) == sorted(GAME_IDS), "jedes Spiel genau einmal"
    long = Tournament.build_order(random.Random(4), GAME_IDS, len(GAME_IDS) + 3)
    assert len(long) == len(GAME_IDS) + 3


def test_every_minigame_runs_and_scores():
    """Jedes der 11 Minispiele einmal komplett durchspielen."""
    scene, seen = run_tournament(GAME_IDS)
    assert seen == set(GAME_IDS), "nicht alle Spiele liefen: %s" % (set(GAME_IDS) - seen)
    assert len(scene.tour.history) == len(GAME_IDS)
    for rec in scene.tour.history:
        assert rec.rows, "%s lieferte keine Ergebnisse" % rec.game_id
        places = sorted(r["place"] for r in rec.rows)
        assert places[0] == 1, "%s hat keinen ersten Platz" % rec.game_id
        assert any(r["points"] > 0 for r in rec.rows), \
            "%s vergab keine Punkte" % rec.game_id
    st = scene.tour.standings()
    assert len(st) == 4
    assert st[0]["points"] >= st[-1]["points"]
    assert sum(r["points"] for r in st) > 0


def test_tournament_with_many_players():
    scene, _ = run_tournament(["reaction", "math", "mash", "curve"],
                              n_local=2, n_bots=6, seed=3)
    st = scene.tour.standings()
    assert len(st) == 8
    assert scene.phase == "over"


def test_lobby_button_starts_tournament():
    """Der Weg, den der Nutzer nimmt: Lobby -> TURNIER."""
    from rucurve.scenes.lobby import LobbyScene

    app = App()
    app.config.settings.bot_count = 2
    app.config.settings.party_games = 3
    lob = LobbyScene(app, mode="local")
    lob.on_enter()
    lob._start_tournament()
    scene = app._pending_scene
    assert isinstance(scene, TournamentScene), "Turnier-Szene wurde nicht gesetzt"
    assert len(scene.tour.order) == 3
    assert len(scene.players) == len(lob.players)
    assert scene.local_pids, "Host muss eigene Spieler haben"
    scene.on_enter()
    assert scene.game is not None, "erstes Minispiel wurde nicht gebaut"


def test_disabled_games_are_skipped():
    from rucurve.config import GameSettings

    s = GameSettings()
    for gid in GAME_IDS:
        s.party_enabled[gid] = gid in ("mash", "reaction")
    assert set(s.enabled_party_games()) == {"mash", "reaction"}
    order = Tournament.build_order(random.Random(2), s.enabled_party_games(), 5)
    assert set(order) == {"mash", "reaction"}
    assert len(order) == 5


def test_single_player_tournament():
    scene, _ = run_tournament(["reaction", "mash"], n_local=1, n_bots=0, seed=5)
    assert scene.phase == "over"
    assert len(scene.tour.standings()) == 1


if __name__ == "__main__":
    import traceback

    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok   %s" % name)
            except Exception:
                fails += 1
                print("FAIL %s" % name)
                traceback.print_exc()
    sys.exit(1 if fails else 0)
