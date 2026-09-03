"""Die Arenaspiele: Ru-Sumo, Ru-Jagd, Ru-Ernte.

Alle drei leben davon, dass Spieler direkt aufeinander einwirken - genau das
wird hier geprueft, dazu die gemeinsame Grundlage (Stoss, Waende, Netz) und
dass ein Durchgang eine sinnvolle Laenge hat.
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
from rucurve.party.arena import LOGIC_H, LOGIC_W  # noqa: E402
from rucurve.party.base import GameContext, PartyPlayer  # noqa: E402
from rucurve.party.games.harvest import HarvestGame  # noqa: E402
from rucurve.party.games.sumo import SumoGame  # noqa: E402
from rucurve.party.games.tag import TagGame  # noqa: E402
from rucurve.party.registry import ALL_GAMES, INTERACTIVE_IDS  # noqa: E402

ARENAS = (SumoGame, TagGame, HarvestGame)
_app = None
AREA = pygame.Rect(0, 90, 1004, 520)


def app():
    global _app
    if _app is None:
        _app = App()
    return _app


def make(cls, diffs=(0.5, 0.5), seed=1, host=True, bots=True):
    players = [PartyPlayer(pid=i, name="P%d" % i, color=color_for(i),
                           color_index=i, is_bot=bots, is_local=True,
                           difficulty=d)
               for i, d in enumerate(diffs)]
    cfg = cls.make_config(random.Random(seed), players)
    ctx = GameContext(app=app(), players=players,
                      local_pids=[p.pid for p in players], bindings={},
                      config=cfg, area=AREA, is_host=host)
    g = cls(ctx)
    g.start()
    return g


def play(g, seconds=None):
    limit = seconds if seconds is not None else g.max_seconds + 2
    t = 0.0
    while not g.finished and t < limit:
        g.update(1 / 60.0)
        t += 1 / 60.0
    return t


DIFFS = [0.2, 0.5, 0.75, 1.0, 0.6, 0.4]


# =========================================================================== #
#  Gemeinsame Grundlage
# =========================================================================== #
def test_every_arena_game_is_host_authoritative():
    """Direkte Einwirkung geht nur, wenn EINER fuer alle rechnet."""
    for cls in ARENAS:
        assert cls.authoritative, cls.name
        assert cls.id in INTERACTIVE_IDS, cls.name


def test_players_start_apart_and_inside():
    for cls in ARENAS:
        g = make(cls, DIFFS)
        pos = [(u["x"], u["y"]) for u in g.units.values()]
        for x, y in pos:
            assert 0 < x < LOGIC_W and 0 < y < LOGIC_H, cls.name
        for i in range(len(pos)):
            for j in range(i + 1, len(pos)):
                d = math.dist(pos[i], pos[j])
                assert d > cls.RADIUS * 2, (
                    "%s: Start zu eng (%.0f px)" % (cls.name, d))


def test_collision_pushes_players_apart():
    g = make(SumoGame)
    a, b = g.units[0], g.units[1]
    a.update({"x": 800.0, "y": 450.0, "h": 0.0, "v": 300.0})
    b.update({"x": 810.0, "y": 450.0, "h": math.pi, "v": 300.0})
    g._collide()
    assert math.dist((a["x"], a["y"]), (b["x"], b["y"])) > 10.0


def test_knockback_moves_against_the_steering():
    """Ein Stoss muss wirken, obwohl man stur vorwaerts faehrt."""
    g = make(SumoGame)
    u = g.units[0]
    u.update({"x": 800.0, "y": 450.0, "h": 0.0, "v": 0.0})
    g.knockback(u, math.pi, 400.0, 0.5)
    for _ in range(20):
        g._move(u, 1 / 60.0)
    assert u["x"] < 790.0, "Stoss hatte keine Wirkung (x=%.1f)" % u["x"]


def test_bouncing_walls_keep_players_in():
    g = make(TagGame)
    u = g.units[0]
    u.update({"x": LOGIC_W - 40.0, "y": 450.0, "h": 0.0, "v": 400.0})
    for _ in range(240):
        g._move(u, 1 / 60.0)
        assert 0 <= u["x"] <= LOGIC_W and 0 <= u["y"] <= LOGIC_H


def test_state_travels_over_the_wire():
    for cls in ARENAS:
        host = make(cls, DIFFS, seed=4)
        play(host, seconds=8.0)
        players = [PartyPlayer(pid=p.pid, name=p.name, color=p.color,
                               color_index=p.color_index, is_bot=p.is_bot,
                               is_local=False, difficulty=p.difficulty)
                   for p in host.ctx.players]
        ctx = GameContext(app=app(), players=players, local_pids=[],
                          bindings={}, config=dict(host.cfg), area=AREA,
                          is_host=False)
        client = cls(ctx)
        client.apply_state(host.net_state())
        for pid, hu in host.units.items():
            cu = client.units[pid]
            assert math.dist((hu["x"], hu["y"]), (cu["x"], cu["y"])) < 1.0, cls.name
            assert cu["alive"] == hu["alive"], cls.name
            assert abs(cu["score"] - hu["score"]) < 0.05, cls.name
        client.draw(app().screen)          # darf beim Client nicht abstuerzen


def test_client_input_reaches_the_host():
    for cls in ARENAS:
        g = make(cls, (0.5, 0.5), bots=False)
        g.apply_input(9, {"in": [[1, True, False, True]]})
        assert g._remote_input[1] == (True, False, True), cls.name
        before = g.units[1]["h"]
        for _ in range(30):
            g._step(1 / 60.0, dict(g._remote_input))
        assert g.units[1]["h"] != before, "%s: Lenkbefehl wirkte nicht" % cls.name


def test_rounds_have_a_sensible_length():
    for cls in ARENAS:
        times = [play(make(cls, DIFFS, seed=s)) for s in range(4)]
        med = statistics.median(times)
        assert 12.0 < med < 60.0, "%s: %.1f s" % (cls.name, med)


# =========================================================================== #
#  Ru-Sumo
# =========================================================================== #
def test_sumo_ring_shrinks():
    g = make(SumoGame, DIFFS)
    first = g.ring
    play(g, seconds=25.0)
    assert g.ring < first * 0.85, "Ring schrumpft nicht (%.0f -> %.0f)" % (first, g.ring)


def test_sumo_leaving_the_ring_is_out():
    g = make(SumoGame, DIFFS)
    u = g.units[0]
    u["x"], u["y"] = g.cx + g.ring + 200.0, g.cy
    g.step_world(1 / 60.0)
    assert not u["alive"]
    assert 0 in g.out_order


def test_sumo_ends_with_a_single_survivor():
    g = make(SumoGame, DIFFS)
    play(g)
    assert g.finished
    alive = g.alive_units()
    assert len(alive) <= 1, "Sumo endete mit %d im Ring" % len(alive)


def test_sumo_ramming_hits_harder_than_drifting():
    """Der Rammstoss ist der Sinn der Aktionstaste - er muss sich lohnen."""
    def shove(with_dash):
        g = make(SumoGame)
        a, b = g.units[0], g.units[1]
        a.update({"x": 700.0, "y": 450.0, "h": 0.0, "v": 300.0,
                  "dash_left": 0.3 if with_dash else 0.0})
        b.update({"x": 700.0 + SumoGame.RADIUS * 1.8, "y": 450.0,
                  "h": 0.0, "v": 60.0, "dash_left": 0.0})
        g._collide()
        return b["kv"]

    soft, hard = shove(False), shove(True)
    assert hard > soft * 1.8, "Rammen wirkt kaum staerker (%.0f vs %.0f)" % (hard, soft)


def test_sumo_bots_do_not_all_drive_out_at_once():
    """Der Wendekreis am Ringrand war der Grund, warum eine fruehe Fassung
    nach sieben Sekunden vorbei war."""
    for seed in range(4):
        g = make(SumoGame, DIFFS, seed=seed)
        play(g, seconds=8.0)
        assert len(g.alive_units()) >= 3, (
            "nach 8 s nur noch %d im Ring" % len(g.alive_units()))


def test_stronger_sumo_bots_last_longer():
    g = make(SumoGame, DIFFS, seed=3)
    play(g)
    strong = g.results()[3].raw          # Stufe 1.00
    weak = g.results()[0].raw            # Stufe 0.20
    assert strong > weak, "starker Bot (%.1f s) nicht besser als schwacher (%.1f s)" % (
        strong, weak)


# =========================================================================== #
#  Ru-Jagd
# =========================================================================== #
def test_tag_only_the_hunter_earns_nothing():
    g = make(TagGame, DIFFS)
    before = {pid: u["score"] for pid, u in g.units.items()}
    for _ in range(30):
        g.step_world(1 / 60.0)
    for pid, u in g.units.items():
        if u["hunter"]:
            assert u["score"] == before[pid], "Faenger sammelt trotzdem Punkte"
        else:
            assert u["score"] > before[pid], "Fluechtender sammelt nicht"


def test_tag_hunter_is_faster():
    g = make(TagGame, DIFFS)
    g.step_world(1 / 60.0)
    hunter = g.hunters()[0]
    other = next(u for u in g.units.values() if not u["hunter"])
    assert hunter["slow"] > other["slow"], "Faenger ist nicht schneller"


def test_tag_scales_the_number_of_hunters_with_the_field():
    """Mit einem Faenger und zwanzig Leuten wird kaum jemand erwischt - dann
    teilen sich am Ende zehn Spieler den ersten Platz."""
    for n, want in ((2, 1), (6, 1), (10, 2), (15, 3), (20, 4)):
        g = make(TagGame, [0.5] * n)
        assert len(g.hunters()) == want, (
            "%d Spieler -> %d Faenger (erwartet %d)" % (n, len(g.hunters()), want))
        assert len(g.hunters()) < n, "es muss immer jemand zu fangen sein"


def test_tag_big_field_does_not_end_in_a_mass_tie():
    """Der Fall aus der Praxis: 20 Spieler, und die Haelfte teilt Platz 1."""
    from rucurve.party.tournament import rank_results

    worst = 0
    for seed in range(3):
        g = make(TagGame, [0.5] * 20, seed=seed)
        play(g)
        rows = rank_results(g.results(), TagGame.scoring)
        first = sum(1 for r in rows if r["place"] == 1)
        worst = max(worst, first)
    assert worst <= 3, "%d Spieler teilen sich den ersten Platz" % worst


def test_tag_catching_someone_breaks_a_tie():
    """Gleiche freie Zeit: wer selbst jemanden gefangen hat, steht vorn."""
    g = make(TagGame, [0.5] * 4)
    play(g, seconds=2.0)
    for u in g.units.values():
        u["hunter"] = False
        u["score"] = 20.0
    g.it_time = {pid: 5.0 for pid in g.units}
    g.catches = {0: 2, 1: 0, 2: 0, 3: 0}
    g.finish()
    res = g.results()
    assert res[0].raw == res[1].raw, "Testaufbau: Rohwerte muessen gleich sein"
    assert res[0].time < res[1].time, "Faenge brechen den Gleichstand nicht"


def test_tag_role_does_not_ping_pong():
    """Fruehere Fassung: die Rolle sprang nur zwischen denselben zwei Leuten
    hin und her, vier von sechs waren nie dran."""
    seen = set()
    for seed in range(6):
        g = make(TagGame, DIFFS, seed=seed)
        involved = set()
        t = 0.0
        while not g.finished and t < TagGame.max_seconds:
            g.update(1 / 60.0)
            t += 1 / 60.0
            involved.update(u["pid"] for u in g.hunters())
        seen.add(len(involved))
        assert len(involved) >= 3, (
            "Seed %d: nur %d verschiedene Faenger" % (seed, len(involved)))
    assert max(seen) >= 4, "die Rolle wandert nie weit: %s" % sorted(seen)


def test_tag_fresh_hunter_cannot_tag_immediately():
    g = make(TagGame, DIFFS)
    it = g.hunters()[0]
    victim = next(u for u in g.units.values() if not u["hunter"])
    it.update({"x": 800.0, "y": 450.0, "h": 0.0, "v": 300.0, "cool": 0.0})
    victim.update({"x": 800.0 + TagGame.RADIUS * 1.5, "y": 450.0, "h": math.pi,
                   "v": 300.0, "immune": 0.0})
    g._collide()
    assert victim["hunter"], "Beruehrung hat nicht gefangen"
    assert not it["hunter"], "der Faenger blieb Faenger"
    assert victim["cool"] > 0.0, "frischer Faenger darf nicht sofort fangen"
    assert it["immune"] > 0.0, "wer abgibt, muss kurz sicher sein"
    # Sofort noch einmal: darf NICHT zurueckwechseln
    g._collide()
    assert victim["hunter"] and not it["hunter"], "Rolle sprang sofort zurueck"


def test_tag_hunter_prefers_the_leader():
    """Wer vorn liegt, wird gejagt - sonst lohnt es sich, weit weg zu warten."""
    g = make(TagGame, (0.5, 0.5, 0.5))
    hunter = g.hunters()[0]
    hunter.update({"x": 800.0, "y": 450.0})
    others = [u for u in g.units.values() if not u["hunter"]]
    near, far = others[0], others[1]
    near.update({"x": 800.0, "y": 620.0, "score": 1.0})     # nah, wenig Punkte
    far.update({"x": 800.0, "y": 200.0, "score": 40.0})     # weiter, fuehrt
    assert g._prey(hunter) is far, "Faenger nimmt sich nicht den Fuehrenden"


# =========================================================================== #
#  Ru-Ernte
# =========================================================================== #
def test_harvest_collecting_scores():
    g = make(HarvestGame, DIFFS)
    u = g.units[0]
    it = g.items[0]
    u["x"], u["y"] = it["x"], it["y"]
    before = u["score"]
    g.step_world(1 / 60.0)
    assert u["score"] > before
    assert len(g.items) >= HarvestGame.N_CRYSTALS - 1, "Kristall nicht ersetzt"


def test_harvest_ramming_pays_for_the_rammer():
    """Ohne direkten Gewinn war Rammen selbstlos - die Beute lag dann nur
    fuer alle anderen herum, und starke Bots verloren dadurch."""
    g = make(HarvestGame)
    a, b = g.units[0], g.units[1]
    a.update({"x": 700.0, "y": 450.0, "h": 0.0, "v": 400.0, "dash_left": 0.3,
              "score": 0.0})
    b.update({"x": 700.0 + HarvestGame.RADIUS * 1.8, "y": 450.0, "h": 0.0,
              "v": 50.0, "dash_left": 0.0, "score": 20.0})
    n_items = len(g.items)
    g._collide()
    assert b["score"] < 20.0, "Getroffener verliert nichts"
    assert a["score"] > 0.0, "Rammender gewinnt nichts"
    assert len(g.items) > n_items, "keine Splitter gefallen"


def test_harvest_only_a_real_dash_steals():
    g = make(HarvestGame)
    a, b = g.units[0], g.units[1]
    a.update({"x": 700.0, "y": 450.0, "h": 0.0, "v": 400.0, "dash_left": 0.0,
              "score": 0.0})
    b.update({"x": 700.0 + HarvestGame.RADIUS * 1.8, "y": 450.0, "h": 0.0,
              "v": 50.0, "dash_left": 0.0, "score": 20.0})
    g._collide()
    assert b["score"] == 20.0, "Streifen hat geklaut"
    assert a["score"] == 0.0


def test_harvest_a_broke_player_cannot_be_robbed():
    g = make(HarvestGame)
    a, b = g.units[0], g.units[1]
    a.update({"x": 700.0, "y": 450.0, "h": 0.0, "v": 400.0, "dash_left": 0.3,
              "score": 0.0})
    b.update({"x": 700.0 + HarvestGame.RADIUS * 1.8, "y": 450.0, "h": 0.0,
              "v": 50.0, "dash_left": 0.0, "score": 0.0})
    g._collide()
    assert a["score"] == 0.0 and b["score"] == 0.0


def test_harvest_items_stay_inside_the_arena():
    g = make(HarvestGame, DIFFS, seed=7)
    play(g, seconds=20.0)
    for it in g.items:
        assert 0 < it["x"] < LOGIC_W and 0 < it["y"] < LOGIC_H


# =========================================================================== #
def test_the_two_lonely_precision_games_are_gone():
    """"Stopp!" und "Zeitgefuehl" waren reine Einzelpraezision - bewusst raus."""
    ids = {g.id for g in ALL_GAMES}
    assert "stopbar" not in ids
    assert "timesense" not in ids
    assert len(INTERACTIVE_IDS) >= 5, (
        "zu wenig Spiele mit direkter Einwirkung: %s" % INTERACTIVE_IDS)


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
