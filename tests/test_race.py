"""Ru-Rennen: Strecke, Rundenzaehlung, Bot-Staerke, Rempler.

Rein rechnerisch, ohne Fenster - laeuft damit auch in der CI.
"""

from __future__ import annotations

import math
import os
import random
import statistics
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["RUCURVE_CONFIG"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_tmp", "config.json")

import pygame  # noqa: E402

from rucurve.app import App  # noqa: E402
from rucurve.colors import color_for  # noqa: E402
from rucurve.party.base import GameContext, PartyPlayer  # noqa: E402
from rucurve.party.games.race import (  # noqa: E402
    LOGIC_H,
    LOGIC_W,
    MAX_SPEED,
    TRACK_HALF,
    TURN_RATE,
    RaceGame,
    build_track,
    min_curve_radius,
)

_app = None
AREA = pygame.Rect(0, 90, 1004, 520)


def app():
    global _app
    if _app is None:
        _app = App()
    return _app


def make_game(diffs, seed=1, human=()):
    players = [
        PartyPlayer(pid=i, name="P%d" % i, color=color_for(i), color_index=i,
                    is_bot=(i not in human), is_local=True, difficulty=d)
        for i, d in enumerate(diffs)
    ]
    cfg = RaceGame.make_config(random.Random(seed), players)
    ctx = GameContext(app=app(), players=players, local_pids=[p.pid for p in players],
                      bindings={}, config=cfg, area=AREA, is_host=True)
    g = RaceGame(ctx)
    g.start()
    return g


def race(diffs, seed=1, limit=95.0):
    g = make_game(diffs, seed)
    t = 0.0
    while not g.finished and t < limit:
        g.update(1 / 60.0)
        t += 1 / 60.0
    return g, t


# =========================================================================== #
def test_track_is_wide_enough_to_drive():
    """Die Innenkante darf sich nirgends selbst schneiden."""
    worst = min(min_curve_radius(build_track(s)) for s in range(120))
    assert worst > TRACK_HALF * 1.3, (
        "engste Kurve %.0f px - bei halber Breite %.0f schneidet sich die "
        "Innenkante" % (worst, TRACK_HALF))


def test_track_stays_inside_the_arena():
    for seed in range(60):
        for x, y in build_track(seed):
            assert TRACK_HALF < x < LOGIC_W - TRACK_HALF
            assert TRACK_HALF < y < LOGIC_H - TRACK_HALF


def test_full_speed_fits_through_the_tightest_corner():
    """Ohne Bremse muss der Wendekreis bei Vollgas in die engste Kurve passen."""
    agility_at_top = 0.60                      # siehe _drive
    radius = MAX_SPEED / (TURN_RATE * agility_at_top)
    tightest = min(min_curve_radius(build_track(s)) for s in range(120))
    assert radius < tightest + TRACK_HALF, (
        "Wendekreis %.0f px passt nicht in Kurve %.0f px" % (radius, tightest))


def test_no_free_lap_from_the_starting_grid():
    """Wer hinter der Start-Ziel-Linie steht, darf keine Gratisrunde bekommen."""
    g = make_game([0.5] * 6)
    for pid, car in g.cars.items():
        assert car["prog"] <= 0.02, "Auto %d startet mit Vorsprung %.2f" % (pid, car["prog"])
    g2, t = race([0.5] * 6, seed=4)
    for pid, r in g2.results().items():
        assert r.raw <= g2.laps + 1e-6
        # Zielzeit muss zur gefahrenen Strecke passen (keine abgekuerzte Runde)
        if r.time < 90:
            assert r.time > 8.0, "Auto %d war nach %.1f s im Ziel" % (pid, r.time)


def test_stronger_bots_are_faster():
    times = {}
    for d in (0.0, 0.5, 1.0):
        ts = []
        for seed in range(6):
            _g, t = race([d], seed=seed)
            ts.append(t)
        times[d] = statistics.median(ts)
    assert times[0.0] > times[0.5] > times[1.0], "Bot-Staerke wirkt nicht: %s" % times
    assert times[0.0] - times[1.0] > 2.0, "Unterschied zu klein: %s" % times


def test_bots_stay_on_the_track():
    g = make_game([1.0], seed=2)
    off = 0
    t = 0.0
    while not g.finished and t < 95:
        g.update(1 / 60.0)
        t += 1 / 60.0
        if g._distance_to_center(g.cars[0]) > TRACK_HALF:
            off += 1
    assert off / 60.0 < 1.5, "starker Bot war %.1f s im Gras" % (off / 60.0)


def test_race_takes_a_sensible_amount_of_time():
    durations = [race([0.2, 0.5, 0.75, 1.0, 0.6, 0.4], seed=s)[1] for s in range(8)]
    med = statistics.median(durations)
    assert 10.0 < med < 35.0, "Renndauer %.1f s passt nicht zu einem Minispiel" % med


def test_touching_side_by_side_does_not_brake():
    """Nebeneinander fahren darf nicht bremsen - sonst kriecht das ganze Feld."""
    g = make_game([0.5, 0.5])
    a, b = g.cars[0], g.cars[1]
    a.update({"x": 400.0, "y": 400.0, "h": 0.0, "v": 400.0})
    b.update({"x": 400.0, "y": 430.0, "h": 0.0, "v": 400.0})   # dicht daneben
    g._bumps()
    assert a["v"] > 399.0 and b["v"] > 399.0, "Streifen kostete Tempo: %.1f/%.1f" % (a["v"], b["v"])
    assert abs(a["y"] - b["y"]) > 30.0, "Autos wurden nicht auseinandergeschoben"


def test_rear_ending_costs_the_one_behind_more():
    g = make_game([0.5, 0.5])
    a, b = g.cars[0], g.cars[1]
    a.update({"x": 400.0, "y": 400.0, "h": 0.0, "v": 420.0})   # faehrt auf
    b.update({"x": 430.0, "y": 400.0, "h": 0.0, "v": 200.0})   # wird gerammt
    g._bumps()
    assert a["v"] < 420.0 and b["v"] < 200.0, "Aufprall kostete gar nichts"
    assert (420.0 - a["v"]) / 420.0 > (200.0 - b["v"]) / 200.0, (
        "der Auffahrende muss mehr verlieren")


def test_progress_ignores_driving_backwards():
    g = make_game([0.5])
    car = g.cars[0]
    car["lap"] = 1
    car["idx"] = 5.0
    car["prog"] = 1.0 + 5.0 / len(g.center)
    # rueckwaerts ueber die Start-Ziel-Linie
    x, y, _h = g._pose_at(len(g.center) - 6)
    car["x"], car["y"] = x, y
    g._track_progress(0, car)
    assert car["lap"] == 1, "Rueckwaertsfahren hat eine Runde gutgeschrieben"


def test_lost_car_gets_towed_back_to_the_track():
    """Wer nicht lenkt, darf nicht bis zum Rennende am Bildrand kleben."""
    from rucurve.party.games.race import TOW_AFTER, TOW_DIST

    g = make_game([0.5])
    car = g.cars[0]
    x, y, _h = g._pose_at(car["idx"])
    car["x"], car["y"] = 8.0, 8.0            # in die Ecke gesetzt
    assert g._distance_to_center(car) > TOW_DIST
    for _ in range(int((TOW_AFTER + 0.2) * 60)):
        g._tow_if_lost(car, 1 / 60.0)
    assert g._distance_to_center(car) < TRACK_HALF, (
        "Auto wurde nicht zurueckgesetzt (%.0f px daneben)"
        % g._distance_to_center(car))


def test_towing_does_not_trigger_on_the_track():
    g = make_game([0.5])
    car = g.cars[0]
    before = (car["x"], car["y"])
    for _ in range(300):
        g._tow_if_lost(car, 1 / 60.0)
    assert (car["x"], car["y"]) == before, "Auto auf der Strecke wurde versetzt"


def test_idle_player_still_finishes_somewhere():
    """Ein Spieler, der gar keine Taste drueckt, blockiert das Rennen nicht."""
    g = make_game([0.5, 0.5])
    for p in g.ctx.players:
        p.is_bot = False                      # niemand lenkt
    t = 0.0
    while not g.finished and t < 95:
        g.update(1 / 60.0)
        t += 1 / 60.0
    assert g.finished
    for car in g.cars.values():
        assert car["prog"] > 0.05, "Auto kam gar nicht vom Fleck"


def test_state_travels_over_the_wire():
    host = make_game([0.5, 0.7], seed=9)
    for _ in range(240):
        host.update(1 / 60.0)
    players = [PartyPlayer(pid=p.pid, name=p.name, color=p.color,
                           color_index=p.color_index, is_bot=p.is_bot,
                           is_local=False, difficulty=p.difficulty)
               for p in host.ctx.players]
    ctx = GameContext(app=app(), players=players, local_pids=[], bindings={},
                      config=dict(host.cfg), area=AREA, is_host=False)
    client = RaceGame(ctx)
    client.apply_state(host.net_state())
    for pid, hc in host.cars.items():
        cc = client.cars[pid]
        assert math.hypot(hc["x"] - cc["x"], hc["y"] - cc["y"]) < 1.0
        assert cc["lap"] == hc["lap"]
        assert abs(cc["prog"] - hc["prog"]) < 0.01
    # Und die Strecke ist auf beiden Rechnern dieselbe
    assert client.center == host.center


def test_client_input_reaches_the_host():
    g = make_game([0.5, 0.5])
    g.apply_input(7, {"in": [[1, True, False, True]]})
    assert g._remote_input[1] == (True, False, True)
    before = g.cars[1]["h"]
    for _ in range(30):
        g._step(1 / 60.0, dict(g._remote_input))
    assert g.cars[1]["h"] != before, "Lenkbefehl vom Client wirkte nicht"


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
