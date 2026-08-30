"""Integration: Host-Szene + echter Client-Socket ueber Loopback durch eine
komplette Runde (Lobby -> round_start -> Snapshots -> Eingabe wirkt)."""

from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Tests niemals auf die echte config.json des Nutzers loslassen
os.environ["RUCURVE_CONFIG"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_tmp", "config.json")

import pygame  # noqa

from rucurve.app import App
from rucurve.net.client import GameClient
from rucurve.scenes.lobby import LobbyScene
from rucurve.scenes.game import GameScene


def pump(scene, n=6, dt=1 / 60):
    for _ in range(n):
        scene.update(dt)
        time.sleep(0.01)


def run():
    app = App()
    app.config.settings.countdown_seconds = 0.5
    app.config.settings.target_score = 2
    app.config.settings.bot_count = 0

    lobby = LobbyScene(app, mode="host")
    lobby.on_enter()
    assert lobby.host, "Host nicht gestartet"

    client = GameClient()
    assert client.connect("127.0.0.1", lobby.host.port), client.error

    pump(lobby, 10)  # __connect__ -> welcome + lobby
    got = client.poll()
    cid = next(m["cid"] for m in got if m["type"] == "welcome")

    client.send({"type": "hello", "players": [{"name": "Gast", "powerup": "speed", "color_index": 5}]})
    pump(lobby, 10)
    assert any(p.client_id == cid for p in lobby.players), "Client-Spieler nicht in der Lobby"

    lobby._start()
    app._swap_scene()
    game = app.scene
    assert isinstance(game, GameScene)

    # round_start beim Client
    rs = None
    for _ in range(50):
        for m in client.poll():
            if m["type"] == "round_start":
                rs = m
        if rs:
            break
        game.update(1 / 60)
        time.sleep(0.01)
    assert rs, "kein round_start empfangen"
    my_pids = [p["pid"] for p in rs["players"] if p.get("client_id") == cid]
    assert my_pids
    my_pid = my_pids[0]

    my_curve = next(c for c in game.world.curves if c.id == my_pid)

    # Snapshots einsammeln + dauerhaft "rechts" senden -> heading dreht sich
    h0 = my_curve.heading
    snaps = 0
    for i in range(240):
        client.send({"type": "input", "in": [[my_pid, False, True, False]]})
        game.update(1 / 60)
        for m in client.poll():
            if m["type"] == "snapshot":
                snaps += 1
        time.sleep(0.005)
        if abs(my_curve.heading - h0) > 0.5:
            break

    assert snaps > 0, "keine Snapshots beim Client"
    assert abs(my_curve.heading - h0) > 0.3, "Client-Eingabe wirkt nicht auf die Host-World"

    client.close()
    lobby.host.stop()
    if lobby.beacon:
        lobby.beacon.stop()
    print(f"ok   LAN-Runde: {snaps} Snapshots, Client-Lenkung wirkt")


if __name__ == "__main__":
    run()
