"""Der echte Weg beim LAN-Turnier: Host-Lobby -> TURNIER -> Client spielt mit.

Regression: kamen "pt_begin" und "pt_game" im selben Poll-Paket an, verwarf der
Client beim Szenenwechsel den Rest - das Minispiel kam nie an und der
Mitspieler sah nur einen leeren Bildschirm.
"""

from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["RUCURVE_CONFIG"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_tmp", "config.json")

import pygame  # noqa: E402

from rucurve.app import App  # noqa: E402
from rucurve.net.client import GameClient  # noqa: E402
from rucurve.scenes.join import ClientLobbyScene  # noqa: E402
from rucurve.scenes.lobby import LobbyScene  # noqa: E402
from rucurve.scenes.tournament import TournamentScene  # noqa: E402

PORT_HINT = 54400


class FakeKeys:
    def __getitem__(self, k):
        return False


def _pump(scenes, frames=1, dt=1 / 60.0, draw=None):
    for _ in range(frames):
        for sc in scenes:
            if sc is None:
                continue
            sc.update(dt)
        time.sleep(0.004)


def setup_lan(pause_before_client_polls=0.0):
    """Host-Lobby mit einem Client, der ueber ClientLobbyScene beitritt."""
    app = App()
    app.config.settings.bot_count = 1
    app.config.settings.party_games = 2
    app.config.slots[0].enabled = True
    app.config.slots[1].enabled = False

    from rucurve.config import DEFAULT_GAME_PORT
    import rucurve.config as cfgmod

    lob = LobbyScene(app, mode="host")
    lob.on_enter()
    assert lob.host, "Host startete nicht"

    client = GameClient()
    assert client.connect("127.0.0.1", lob.host.port, timeout=4), client.error
    cl = ClientLobbyScene(app, client)
    cl.on_enter()

    # Begruessung + Lobby austauschen
    for _ in range(60):
        lob.update(1 / 60)
        cl.update(1 / 60)
        time.sleep(0.01)
        if any(p.client_id >= 0 for p in lob.players):
            break
    assert any(p.client_id >= 0 for p in lob.players), "Client kam nicht in die Lobby"
    return app, lob, cl, client


def test_client_follows_into_the_tournament():
    app, lob, cl, client = setup_lan()
    try:
        lob._start_tournament()
        host_scene = app._pending_scene
        assert isinstance(host_scene, TournamentScene)
        app._swap_scene()
        host_scene.on_enter()

        # Genau der kritische Fall: der Client pollt erst, wenn Host schon
        # pt_begin UND pt_game geschickt hat - beide liegen dann im selben Paket.
        time.sleep(0.5)
        host_scene.update(1 / 60)
        time.sleep(0.3)

        cl.update(1 / 60)
        client_scene = app._pending_scene
        assert isinstance(client_scene, TournamentScene), "Client wechselte nicht ins Turnier"
        app._swap_scene()
        client_scene.on_enter()

        # Jetzt muss das Minispiel beim Client ankommen
        ok = False
        for _ in range(240):
            host_scene.update(1 / 60)
            client_scene.update(1 / 60)
            time.sleep(0.005)
            if client_scene.game is not None:
                ok = True
                break
        assert ok, "Client hat nie ein Minispiel bekommen (sieht nichts)"
        assert client_scene.game_cls.id == host_scene.game_cls.id, \
            "Client spielt ein anderes Spiel als der Host"

        # ... und er muss auch wirklich losspielen duerfen
        started = False
        for _ in range(400):
            host_scene.update(1 / 60)
            client_scene.update(1 / 60)
            time.sleep(0.004)
            if client_scene.phase == "play":
                started = True
                break
        assert started, "Client blieb im Intro haengen (pt_go verpasst)"
    finally:
        client.close()
        if lob.host:
            lob.host.stop()
        if lob.beacon:
            lob.beacon.stop()


def test_client_recovers_when_it_misses_the_game_message():
    """Selbst wenn pt_game verlorengeht, muss der Client aufholen."""
    app, lob, cl, client = setup_lan()
    try:
        lob._start_tournament()
        host_scene = app._pending_scene
        app._swap_scene()
        host_scene.on_enter()
        time.sleep(0.4)

        cl.update(1 / 60)
        client_scene = app._pending_scene
        app._swap_scene()
        client_scene.on_enter()

        # Nachrichten absichtlich wegwerfen - simuliert einen verpassten Start
        client_scene._inbox = []
        client.poll()
        client_scene.game = None
        client_scene.game_cls = None

        ok = False
        for _ in range(400):
            host_scene.update(1 / 60)
            client_scene.update(1 / 60)
            time.sleep(0.005)
            if client_scene.game is not None:
                ok = True
                break
        assert ok, "Client holte den verpassten Spielstart nicht nach"
    finally:
        client.close()
        if lob.host:
            lob.host.stop()
        if lob.beacon:
            lob.beacon.stop()


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
