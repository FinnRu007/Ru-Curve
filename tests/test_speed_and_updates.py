"""Tempo-Wertung bei den Quizspielen, Update-Hinweis und Startanimation."""

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
from rucurve.colors import color_for  # noqa: E402
from rucurve.net.internet import UpdateCheck, is_newer, parse_version  # noqa: E402
from rucurve.party.base import GameContext, PartyPlayer  # noqa: E402
from rucurve.party.games.quizzes import MathQuiz  # noqa: E402
from rucurve.party.tournament import rank_results  # noqa: E402
from rucurve.scenes.menu import MenuScene  # noqa: E402
from rucurve.scenes.splash import DURATION, SplashScene  # noqa: E402

_app = None
AREA = pygame.Rect(0, 90, 1004, 520)


def app():
    global _app
    if _app is None:
        _app = App()
    return _app


def make_quiz(n_players=2):
    players = [PartyPlayer(pid=i, name="P%d" % i, color=color_for(i), color_index=i,
                           is_bot=False, is_local=True)
               for i in range(n_players)]
    cfg = MathQuiz.make_config(random.Random(5), players)
    ctx = GameContext(app=app(), players=players, local_pids=[p.pid for p in players],
                      bindings={}, config=cfg, area=AREA, is_host=True)
    return MathQuiz(ctx)


# =========================================================================== #
def test_faster_correct_answer_scores_more():
    g = make_quiz()
    assert g.speed_points(0.0) == g.MAX_POINTS
    assert g.speed_points(g.per_q) == g.MIN_POINTS
    early, late = g.speed_points(0.5), g.speed_points(4.0)
    assert early > late, "frueh antworten muss mehr bringen (%d vs %d)" % (early, late)


def test_speed_decides_between_equally_correct_players():
    """Beide alles richtig - der Schnellere muss gewinnen, nicht nur den
    Gleichstand entscheiden."""
    g = make_quiz()
    for _ in range(len(g.questions)):
        q = g.question
        if q is None:
            break
        g.update(0.4)                       # Spieler 0 antwortet schnell
        g._answer(0, q["correct"])
        g.update(3.6)                       # Spieler 1 kurz vor Schluss
        g._answer(1, q["correct"])
        g.update(g.per_q)                   # Frage ablaufen lassen
    g.finish()
    res = g.results()
    assert res[0].raw > res[1].raw, (
        "gleiche Trefferzahl, aber Tempo zaehlt nicht: %s / %s"
        % (res[0].detail, res[1].detail))
    rows = rank_results(res, MathQuiz.scoring)
    places = {r["pid"]: r["place"] for r in rows}
    assert places[0] == 1 and places[1] == 2


def test_wrong_answer_scores_nothing():
    g = make_quiz()
    q = g.question
    g._answer(0, (q["correct"] + 1) % 3)
    assert g.points[0] == 0
    assert g.correct[0] == 0


def test_one_correct_beats_two_slow_ones_never():
    """Tempo darf Treffer nicht voellig ersetzen: zwei richtige schlagen eine."""
    g = make_quiz()
    fastest_single = g.speed_points(0.0)
    two_slow = 2 * g.speed_points(g.per_q)
    assert two_slow > fastest_single, (
        "eine blitzschnelle Antwort waere sonst mehr wert als zwei richtige")


# --------------------------------------------------------------------------- #
def test_version_comparison():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert is_newer("0.2.0", "0.1.0")
    assert is_newer("1.0", "0.9.9")
    assert not is_newer("0.1.0", "0.1.0")
    assert not is_newer("0.0.9", "0.1.0")
    assert not is_newer("kaputt", "0.1.0")


def test_update_check_reads_the_version_file():
    chk = UpdateCheck(current="0.1.0")
    chk.apply({"version": "0.4.0", "notes": "Rennen dabei"})
    assert chk.available and chk.latest == "0.4.0"
    chk2 = UpdateCheck(current="0.4.0")
    chk2.apply({"version": "0.4.0"})
    assert not chk2.available, "gleiche Version darf nicht als Update gelten"


def test_menu_shows_the_update_hint_without_covering_a_button():
    a = app()
    m = MenuScene(a)
    m.on_enter()
    a.update_check.latest = "9.9.9"
    a.update_check.available = True
    m.draw(a.screen)
    for wgt in m.widgets:
        assert not wgt.rect.colliderect(m._update_rect), (
            "Update-Band liegt ueber dem Knopf bei %s" % (wgt.rect,))


def test_splash_ends_and_can_be_skipped():
    a = app()
    sp = SplashScene(a)
    sp.on_enter()
    sp.draw(a.screen)                       # darf nicht abstuerzen
    sp.update(DURATION + 0.1)
    assert a._pending_scene is not None, "Startanimation blieb haengen"

    a._pending_scene = None
    sp2 = SplashScene(a)
    sp2.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)])
    assert a._pending_scene is not None, "Ueberspringen hat nicht funktioniert"


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
