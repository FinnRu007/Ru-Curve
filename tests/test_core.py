"""Headless-Tests fuer Simulation, Kollision, Punkte und Protokoll."""

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

pygame.init()

from rucurve.config import GameSettings  # noqa: E402
from rucurve.game.collision import CollisionGrid  # noqa: E402
from rucurve.game.curve import Curve  # noqa: E402
from rucurve.game.world import World  # noqa: E402
from rucurve.net.protocol import FrameReader, encode  # noqa: E402


def _curve(cid, name="P"):
    return Curve(cid, name, (255, 0, 0), color_index=cid)


def _settings(pu=None, **kw):
    """GameSettings mit optionalen Powerup-Ueberschreibungen: pu={"speed": {...}}."""
    s = GameSettings(**kw)
    for pid, vals in (pu or {}).items():
        cfg = s.powerup_cfg(pid)
        for k, v in vals.items():
            setattr(cfg, k, v)
    return s


def test_grid_stamp_and_hit():
    g = CollisionGrid(200, 200)
    assert not g.hits(100, 100, 3)
    g.stamp_circle(100, 100, 5)
    assert g.hits(100, 100, 2)
    assert not g.hits(150, 150, 2)


def test_grid_bounds_are_deadly():
    g = CollisionGrid(100, 100)
    assert g.hits(1, 50, 3)
    assert g.hits(99, 50, 3)
    assert not g.hits(50, 50, 3)


def test_turn_rate_matches_radius():
    s = GameSettings(speed=120, turn_radius=60)
    assert abs(s.turn_rate() - 2.0) < 1e-9


def test_spawns_are_inside_and_separated():
    s = GameSettings(arena_width=1200, arena_height=800)
    curves = [_curve(i) for i in range(6)]
    w = World(s, curves)
    for c in curves:
        assert 0 < c.x < s.arena_width
        assert 0 < c.y < s.arena_height
    for i in range(len(curves)):
        for j in range(i + 1, len(curves)):
            d = ((curves[i].x - curves[j].x) ** 2 + (curves[i].y - curves[j].y) ** 2) ** 0.5
            assert d > 40


def test_spawn_not_instant_death():
    s = GameSettings(countdown_seconds=0.0)
    curves = [_curve(i) for i in range(5)]
    w = World(s, curves, )
    # 40 Ticks laufen lassen - niemand darf sofort am Spawn sterben
    for _ in range(40):
        w.step()
    assert sum(c.alive for c in curves) >= 4


def test_round_ends_and_awards_points():
    s = GameSettings(countdown_seconds=0.0, points_per_opponent=1, gap_distance=99999)
    curves = [_curve(i) for i in range(3)]
    w = World(s, curves)
    # alle fahren geradeaus in Waende -> Runde endet
    for _ in range(60 * 60):
        w.step()
        if w.phase == "finished":
            break
    assert w.phase == "finished"
    assert w.round_standings is not None
    places = sorted(r["place"] for r in w.round_standings)
    assert places == [1, 2, 3]
    # Rundensieger bekommt (N-1) Punkte, Letzter 0
    by_place = {r["place"]: r for r in w.round_standings}
    assert by_place[1]["gained"] == 2
    assert by_place[3]["gained"] == 0


def test_self_collision_toggle():
    s = GameSettings(countdown_seconds=0.0, self_collision=True, turn_radius=14,
                     speed=140, gap_distance=99999, arena_width=1400, arena_height=1000)
    c = _curve(0)
    w = World(s, [c])
    c.x, c.y, c.heading = 700, 500, 0.0
    c.reset_runtime(s)
    c.turn = 1  # dauerhaft im Kreis -> irgendwann eigene Spur
    died = False
    for _ in range(60 * 12):
        w.step()
        if not c.alive:
            died = True
            break
    assert died


def test_speed_powerup_boosts_and_consumes_charge():
    s = _settings(countdown_seconds=0.0, gap_distance=99999,
                  arena_width=2400, arena_height=1600,
                  pu={"speed": {"charges": 2, "duration": 1.0, "strength": 2.0}})
    c = _curve(0)
    c.powerup_kind = "speed"
    w = World(s, [c])
    c.x, c.y, c.heading = 1200, 800, 0.0
    c.reset_runtime(s)
    w.step()
    x0 = c.x
    for _ in range(30):
        w.set_input(0, False, False, False)
        w.step()
    normal = c.x - x0
    x1 = c.x
    w.set_input(0, False, False, True)
    w.step()
    w.set_input(0, False, False, False)
    for _ in range(29):
        w.step()
    boosted = c.x - x1
    assert boosted > normal * 1.5
    assert c.pu.charges == 1


def test_square_powerup_snaps_heading_to_90deg():
    import math

    s = _settings(countdown_seconds=0.0, gap_distance=99999,
                  arena_width=2400, arena_height=1600,
                  pu={"square": {"charges": 1, "duration": 3.0}})
    c = _curve(0)
    c.powerup_kind = "square"
    w = World(s, [c])
    c.x, c.y, c.heading = 1200, 800, 0.3
    c.reset_runtime(s)
    w.step()
    w.set_input(0, False, False, True)
    w.step()
    w.set_input(0, False, False, False)
    # nach dem Aktivieren ist der Kurs auf ein Vielfaches von 90 Grad gerastet
    q = math.pi / 2
    assert abs((c.heading / q) - round(c.heading / q)) < 1e-6
    # eine Rechts-Betaetigung dreht um genau 90 Grad
    h0 = c.heading
    w.set_input(0, False, True, False)
    w.step()
    assert abs(abs(c.heading - h0) - q) < 1e-6


def test_extra_gap_powerup_opens_a_gap():
    s = _settings(countdown_seconds=0.0, gap_distance=99999, gap_size=40,
                  arena_width=2400, arena_height=1600,
                  pu={"extra_gap": {"charges": 1, "strength": 140.0}})
    c = _curve(0)
    c.powerup_kind = "extra_gap"
    w = World(s, [c])
    c.x, c.y, c.heading = 1200, 800, 0.0
    c.reset_runtime(s)
    w.step()
    w.set_input(0, False, False, True)
    w.step()
    assert c.gap_left > 60


def test_invert_powerup_sets_screen_flag():
    s = _settings(countdown_seconds=0.0, gap_distance=99999,
                  arena_width=2400, arena_height=1600,
                  pu={"invert": {"charges": 1, "duration": 2.0}})
    c = _curve(0)
    c.powerup_kind = "invert"
    w = World(s, [c])
    c.x, c.y, c.heading = 1200, 800, 0.0
    c.reset_runtime(s)
    w.step()
    assert not w.screen_inverted()
    w.set_input(0, False, False, True)
    w.step()
    assert w.screen_inverted()


def test_arena_dims_follow_window_aspect():
    s = GameSettings(arena_size=900)
    w, h = s.arena_dims(1920, 1080)
    assert h == 900
    assert 1550 <= w <= 1650   # ~ 16:9
    w2, h2 = s.arena_dims(1024, 1280)
    assert w2 < w2 + 1 and w2 < h2   # Hochformat -> schmaler


def test_bots_react_earlier_survive_longer_than_wall_dash():
    from rucurve.game import bots

    s = GameSettings(countdown_seconds=0.0, gap_distance=99999,
                     arena_width=1600, arena_height=1000)
    survived = []
    for _ in range(5):
        cs = [_curve(i) for i in range(3)]
        for c in cs:
            c.is_bot = True
        w = World(s, cs)
        for _ in range(60 * 30):
            for c in cs:
                if c.alive:
                    l, r, p = bots.control_bot(w, c, 0.7)
                    w.set_input(c.id, l, r, p)
            w.step()
            if w.phase == "finished":
                break
        survived.append(w.time)
    # gute Bots halten deutlich laenger als die ~2-3 s bis zur Wand
    assert max(survived) > 6.0


def test_shield_absorbs_one_hit():
    s = _settings(countdown_seconds=0.0, gap_distance=99999, turn_radius=14,
                  speed=150, arena_width=1400, arena_height=1000,
                  pu={"shield": {"charges": 1, "duration": 20.0, "strength": 1.0}})
    c = _curve(0)
    c.powerup_kind = "shield"
    w = World(s, [c])
    c.x, c.y, c.heading = 700, 500, 0.0
    c.reset_runtime(s)
    w.step()
    w.set_input(0, False, False, True)
    w.step()
    w.set_input(0, False, False, False)
    c.turn = 1                      # im Kreis -> trifft die eigene Spur
    absorbed = 0
    for _ in range(60 * 14):
        w.step()
        absorbed += sum(1 for e in w.drain_events() if e[0] == "shield")
        if not c.alive:
            break
    assert absorbed == 1, "Schild muss genau einen Treffer abfangen"
    assert not c.alive, "danach ist der Spieler wieder verwundbar"


def test_clear_powerup_wipes_trails():
    s = _settings(countdown_seconds=0.0, gap_distance=99999,
                  arena_width=2000, arena_height=1400,
                  pu={"clear": {"charges": 1}})
    c = _curve(0)
    c.powerup_kind = "clear"
    w = World(s, [c])
    c.x, c.y, c.heading = 1000, 700, 0.0
    c.reset_runtime(s)
    for _ in range(90):
        w.step()
    assert w.grid.grid.any(), "es sollte eine Spur geben"
    w.set_input(0, False, False, True)
    w.step()
    assert not w.grid.grid.any(), "Radiergummi loescht alle Spuren"


def test_reverse_others_flips_steering():
    s = _settings(countdown_seconds=0.0, gap_distance=99999,
                  arena_width=2400, arena_height=1600,
                  pu={"reverse_others": {"charges": 1, "duration": 5.0}})
    a, b = _curve(0), _curve(1)
    a.powerup_kind = "reverse_others"
    w = World(s, [a, b])
    b.x, b.y, b.heading = 1200, 800, 0.0
    a.reset_runtime(s)
    b.reset_runtime(s)
    w.step()
    w.set_input(1, False, True, False)          # b lenkt nach rechts
    w.step()
    normal = b.heading
    w.set_input(0, False, False, True)          # a dreht b um
    w.step()
    w.set_input(0, False, False, False)
    h0 = b.heading
    for _ in range(10):
        w.step()
    assert normal > 0, "rechts lenken erhoeht den Kurs"
    assert b.heading < h0, "nach dem Powerup lenkt dieselbe Taste nach links"


def test_fat_others_widens_only_opponents():
    s = _settings(countdown_seconds=0.0, gap_distance=99999,
                  arena_width=2400, arena_height=1600,
                  pu={"fat_others": {"charges": 1, "duration": 5.0, "strength": 3.0}})
    a, b = _curve(0), _curve(1)
    a.powerup_kind = "fat_others"
    w = World(s, [a, b])
    a.reset_runtime(s)
    b.reset_runtime(s)
    w.step()
    w.set_input(0, False, False, True)
    w.step()
    assert abs(a.mods().width - 1.0) < 1e-9
    assert b.mods().width > 2.5


def test_disabled_powerup_gives_no_charges():
    s = _settings(countdown_seconds=0.0, pu={"speed": {"enabled": False, "charges": 5}})
    c = _curve(0)
    c.powerup_kind = "speed"
    World(s, [c])
    assert c.pu.charges == 0


def test_settings_json_roundtrip_keeps_powerups(tmp_path=None):
    import json
    from dataclasses import asdict
    from rucurve.config import settings_from_dict

    s = _settings(pu={"ghost": {"duration": 4.25, "charges": 7, "enabled": False}})
    back = settings_from_dict(json.loads(json.dumps(asdict(s))))
    g = back.powerup_cfg("ghost")
    assert g.duration == 4.25 and g.charges == 7 and g.enabled is False
    assert "ghost" not in back.enabled_powerups()


def test_old_config_migrates_to_per_powerup():
    from rucurve.config import settings_from_dict

    old = {"speed": 120, "powerup_charges": 9, "powerup_cooldown": 2.5,
           "powerup_boost_factor": 3.0}
    s = settings_from_dict(old)
    assert s.speed == 120
    assert s.powerup_cfg("ghost").charges == 9
    assert s.powerup_cfg("ghost").cooldown == 2.5
    assert s.powerup_cfg("speed").strength == 3.0


def test_bot_difficulty_scales_survival():
    from rucurve.game import bots

    def run(diff, seed):
        import random as _r
        s = _settings(countdown_seconds=0.0, arena_width=1267, arena_height=950)
        cs = [_curve(i) for i in range(4)]
        for c in cs:
            c.is_bot = True
        w = World(s, cs, rng=_r.Random(seed))
        for _ in range(60 * 45):
            for c in cs:
                if c.alive:
                    l, r, p = bots.control_bot(w, c, diff)
                    w.set_input(c.id, l, r, p)
            w.step()
            if w.phase == "finished":
                break
        return w.time

    weak = sum(run(0.0, i) for i in range(4)) / 4
    strong = sum(run(1.0, i) for i in range(4)) / 4
    assert strong > weak * 1.3, f"starke Bots muessen laenger leben ({weak:.1f}s -> {strong:.1f}s)"


def test_protocol_roundtrip():
    r = FrameReader()
    msgs = [{"type": "hello", "a": 1}, {"type": "snapshot", "curves": [1, 2, 3]}]
    blob = b"".join(encode(m) for m in msgs)
    # in zwei Haelften fuettern
    got = list(r.feed(blob[:5]))
    got += list(r.feed(blob[5:]))
    assert got == msgs


if __name__ == "__main__":
    import traceback

    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except Exception:
                fails += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    sys.exit(1 if fails else 0)
