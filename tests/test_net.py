"""Loopback-Test fuer Host <-> Client (TCP-Frames + Threads)."""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Tests niemals auf die echte config.json des Nutzers loslassen
os.environ["RUCURVE_CONFIG"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_tmp", "config.json")

from rucurve.net.client import GameClient
from rucurve.net.host import GameHost


def _wait_for(fn, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        r = fn()
        if r:
            return r
        time.sleep(0.02)
    return None


def run():
    port = 53555
    host = GameHost(port)
    host.start()
    time.sleep(0.1)

    client = GameClient()
    assert client.connect("127.0.0.1", port), client.error

    # Host sieht die Verbindung
    msgs = _wait_for(lambda: [m for m in host.poll() if m[1].get("type") == "__connect__"])
    assert msgs, "kein __connect__ beim Host"
    cid = msgs[0][0]

    # Host -> Client
    host.send(cid, {"type": "welcome", "cid": cid})
    host.broadcast({"type": "lobby", "players": []})
    got: list = []
    end = time.time() + 2.0
    while time.time() < end and {m["type"] for m in got} < {"welcome", "lobby"}:
        got += client.poll()
        time.sleep(0.02)
    types = {m["type"] for m in got}
    assert "welcome" in types and "lobby" in types, types

    # Client -> Host
    client.send({"type": "hello", "players": [{"name": "Gast", "powerup": "speed", "color_index": 2}]})
    hello = _wait_for(lambda: [m for m in host.poll() if m[1].get("type") == "hello"])
    assert hello and hello[0][1]["players"][0]["name"] == "Gast"

    # viele Snapshots hintereinander
    for i in range(50):
        host.broadcast({"type": "snapshot", "t": i})
    snaps = _wait_for(lambda: [m for m in client.poll() if m.get("type") == "snapshot"] or None)
    assert snaps

    # Disconnect
    client.close()
    dc = _wait_for(lambda: [m for m in host.poll() if m[1].get("type") == "__disconnect__"])
    assert dc, "kein __disconnect__"

    host.stop()
    print("ok   Netzwerk-Loopback")


if __name__ == "__main__":
    run()
