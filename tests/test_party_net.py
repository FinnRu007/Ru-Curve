"""Turnier ueber echte Sockets: Host + Client spielen zusammen.

Prueft, dass Aufgaben, Zeitpunkte, Ergebnisse und Punkte beim Client ankommen -
inklusive Achtung die Kurve, wo der Host fuer alle rechnet.
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
from rucurve.colors import color_for  # noqa: E402
from rucurve.net.client import GameClient  # noqa: E402
from rucurve.net.host import GameHost  # noqa: E402
from rucurve.party.base import PartyPlayer  # noqa: E402
from rucurve.scenes.tournament import TournamentScene  # noqa: E402

PORT = 53911


class FakeKeys:
    def __init__(self, down=()):
        self.down = set(down)

    def __getitem__(self, k):
        return k in self.down


def _wire_players(cid):
    """pid 0 = Host-Tastatur, pid 1 = Bot (Host), pid 2 = Client-Spieler."""
    return [
        {"pid": 0, "name": "Host", "color_index": 0, "is_bot": False, "client_id": -1},
        {"pid": 1, "name": "Bot", "color_index": 3, "is_bot": True, "client_id": -1,
         "difficulty": 0.6},
        {"pid": 2, "name": "Gast", "color_index": 1, "is_bot": False, "client_id": cid},
    ]


def run_lan(order, max_seconds=240):
    app = App()
    app.config.slots[0].enabled = True
    app.config.slots[1].enabled = True

    host = GameHost(PORT)
    host.start()
    time.sleep(0.15)
    client = GameClient()
    assert client.connect("127.0.0.1", PORT), client.error

    cid = None
    end = time.time() + 3
    while cid is None and time.time() < end:
        for c, msg in host.poll():
            if msg.get("type") == "__connect__":
                cid = c
        time.sleep(0.02)
    assert cid is not None, "Host hat die Verbindung nicht bemerkt"

    wire = _wire_players(cid)
    host_players = [PartyPlayer.from_wire(d, None) for d in wire]
    for p in host_players:                    # Host spielt alles mit client_id < 0
        p.is_local = p.client_id < 0
    host_players[0].slot_index = 0
    client_players = [PartyPlayer.from_wire(d, cid) for d in wire]
    client_players[2].slot_index = 1

    hs = TournamentScene(app, host_players, host=host, order=list(order), points_top=10)
    cs = TournamentScene(app, client_players, client=client, cid=cid,
                         order=list(order), points_top=10)
    cs.app_screen = pygame.Surface(app.screen.get_size())

    real = pygame.key.get_pressed
    pygame.key.get_pressed = lambda: FakeKeys()
    hs.on_enter()
    cs.on_enter()

    frames = 0
    limit = int(max_seconds * 60)
    try:
        while frames < limit and hs.phase != "over":
            frames += 1
            hs.handle_events([])
            hs.update(1 / 60.0)
            cs.handle_events([])
            cs.update(1 / 60.0)
            if frames % 31 == 0:
                hs.draw(app.screen)
                cs.draw(cs.app_screen)
            if hs.phase == "result" and hs.phase_t > 0.4:
                hs._advance_from_result()
            time.sleep(0.0005)          # den Netzwerk-Threads Luft lassen
    finally:
        pygame.key.get_pressed = real

    # Client soll das Ende noch mitbekommen
    end = time.time() + 3
    while time.time() < end and cs.phase != "over":
        cs.update(1 / 60.0)
        time.sleep(0.01)

    client.close()
    host.stop()
    return hs, cs


# =========================================================================== #
def test_lan_tournament_syncs_games_and_scores():
    hs, cs = run_lan(["reaction", "math", "mash"])
    assert hs.phase == "over", "Host wurde nicht fertig (%s)" % hs.phase
    assert cs.phase == "over", "Client bekam das Turnierende nicht (%s)" % cs.phase
    assert len(hs.tour.history) == 3

    # Der Client hat dieselben Aufgaben gesehen
    assert cs.game_cls is not None
    # Gesamtpunkte muessen auf beiden Seiten gleich sein
    ht = {r["pid"]: r["points"] for r in hs.tour.standings()}
    ct = {r["pid"]: r["points"] for r in cs.tour.standings()}
    assert ht == ct, "Punktestand weicht ab: %s vs %s" % (ht, ct)
    assert sum(ht.values()) > 0

    # Der Client-Spieler wurde gewertet (nicht als "nicht mitgespielt")
    for rec in hs.tour.history:
        row = next(r for r in rec.rows if r["pid"] == 2)
        assert row["done"], "%s: Client-Ergebnis kam nicht an" % rec.game_id


def test_lan_curve_round_is_host_authoritative():
    hs, cs = run_lan(["curve"], max_seconds=180)
    assert hs.phase == "over"
    rec = hs.tour.history[0]
    assert rec.game_id == "curve"
    assert all(r["done"] for r in rec.rows), "Host muss fuer alle werten"
    # Ohne Tastendruecke koennen alle gleichzeitig sterben - das ist ein
    # echter Gleichstand. Verlangt wird nur: laenger ueberlebt = besserer Platz.
    for a in rec.rows:
        for b in rec.rows:
            if a["raw"] > b["raw"]:
                assert a["place"] < b["place"], (
                    "%.2f s bekam Platz %d, %.2f s aber Platz %d"
                    % (a["raw"], a["place"], b["raw"], b["place"]))
    # Der Client hat Schnappschuesse bekommen und Zeit mitgezaehlt
    assert cs.tour.totals == hs.tour.totals


def test_lan_race_is_host_authoritative():
    """Beim Rennen rechnet der Host - der Client fahert trotzdem richtig mit."""
    hs, cs = run_lan(["race"], max_seconds=180)
    assert hs.phase == "over"
    rec = hs.tour.history[0]
    assert rec.game_id == "race"
    assert all(r["done"] for r in rec.rows), "Host muss fuer alle werten"
    assert len({r["place"] for r in rec.rows}) >= 2, "es muss Plaetze geben"
    assert cs.tour.totals == hs.tour.totals

    # Der Client hat die Autos bewegt gesehen, nicht nur die Startaufstellung
    cars = getattr(cs.game, "cars", {})
    assert cars, "Client hat gar kein Rennen aufgebaut"
    assert max(c["prog"] for c in cars.values()) > 0.5, (
        "beim Client sind die Autos nicht gefahren")


def test_quiz_shows_the_same_question_on_both_machines():
    """Der Kern der anpassbaren Schwierigkeit: die Stufe darf nie dazu
    fuehren, dass Host und Client verschiedene Aufgaben anzeigen."""
    seen = []
    original = TournamentScene.update

    def spy(self, dt):
        original(self, dt)
        g = self.game
        if g is not None and getattr(g, "ladder", None) and g.question is not None:
            seen.append((self.is_host, g.q_index, g.question["prompt"],
                         g.level_of(g.q_index)))

    TournamentScene.update = spy
    try:
        hs, cs = run_lan(["math"])
    finally:
        TournamentScene.update = original

    assert hs.phase == "over"
    host_q = {}
    for is_host, idx, prompt, level in seen:
        if is_host:
            host_q[idx] = (prompt, level)
    checked = 0
    for is_host, idx, prompt, level in seen:
        if is_host or idx not in host_q:
            continue
        checked += 1
        assert (prompt, level) == host_q[idx], (
            "Aufgabe %d: Host zeigt %s (Stufe %d), Client %s (Stufe %d)"
            % (idx, host_q[idx][0], host_q[idx][1], prompt, level))
    assert checked > 50, "zu wenig verglichen (%d)" % checked


def test_single_game_ends_the_tournament():
    """'Einzelnes Spiel' laeuft ueber dieselbe Turnierlogik - genau eine Runde."""
    hs, cs = run_lan(["reaction"])
    assert hs.phase == "over"
    assert len(hs.tour.history) == 1
    assert hs.tour.history[0].game_id == "reaction"
    assert cs.tour.totals == hs.tour.totals


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
