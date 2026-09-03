"""Die Aufgaben passen sich an - aber alle sehen immer dieselbe.

Beides zusammen ist der heikle Teil: die Stufe haengt von der Trefferquote
ALLER Spieler ab, darf aber nie dazu fuehren, dass zwei Rechner gleichzeitig
verschiedene Aufgaben anzeigen.
"""

from __future__ import annotations

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
from rucurve.party.games.quizzes import (  # noqa: E402
    AreaQuiz,
    EstimateQuiz,
    MathQuiz,
    OddOneQuiz,
)

QUIZZES = (MathQuiz, AreaQuiz, EstimateQuiz, OddOneQuiz)

_app = None
AREA = pygame.Rect(0, 90, 1004, 520)


def app():
    global _app
    if _app is None:
        _app = App()
    return _app


def make(cls, n_players=2, seed=5, is_host=True, cfg=None, local=None):
    players = [PartyPlayer(pid=i, name="P%d" % i, color=color_for(i), color_index=i,
                           is_bot=False, is_local=True)
               for i in range(n_players)]
    cfg = cfg if cfg is not None else cls.make_config(random.Random(seed), players)
    pids = list(range(n_players)) if local is None else list(local)
    ctx = GameContext(app=app(), players=players, local_pids=pids, bindings={},
                      config=cfg, area=AREA, is_host=is_host)
    return cls(ctx)


def play(game, answer):
    """Spielt ein Quiz durch. `answer(pid, q, i)` -> Taste oder None."""
    guard = 0
    while not game.finished and guard < 5000:
        guard += 1
        q = game.question
        if q is not None:
            for pid in game.ctx.local_pids:
                btn = answer(pid, q, game.q_index)
                if btn is not None and pid not in game.answers:
                    game._answer(pid, btn)
        game.update(game.per_q)
    return game


# =========================================================================== #
def test_all_quizzes_offer_every_level():
    for cls in QUIZZES:
        cfg = cls.make_config(random.Random(1), [])
        assert len(cfg["ladder"]) == cls.n_questions
        for slot in cfg["ladder"]:
            assert len(slot) == cls.LEVELS, cls.name
            for q in slot:
                assert len(q["options"]) == 3, cls.name
                assert 0 <= q["correct"] <= 2, cls.name


def test_level_rises_when_everything_is_right():
    g = make(MathQuiz)
    play(g, lambda pid, q, i: q["correct"])
    assert g.levels[-1] == g.LEVELS - 1, (
        "alles richtig, aber Stufe blieb bei %s" % g.levels)


def test_level_falls_when_everything_is_wrong():
    g = make(MathQuiz)
    play(g, lambda pid, q, i: (q["correct"] + 1) % 3)
    assert g.levels[-1] == 0, "alles falsch, aber Stufe blieb bei %s" % g.levels


def test_level_holds_when_it_is_a_mixed_bag():
    """Halb richtig soll die Stufe stehen lassen, nicht hin- und herspringen."""
    g = make(MathQuiz, n_players=2)
    play(g, lambda pid, q, i: q["correct"] if pid == 0 else (q["correct"] + 1) % 3)
    assert set(g.levels) == {g.START_LEVEL}, "Stufe wanderte: %s" % g.levels


def test_level_never_changes_the_running_question():
    """Ein spaet eintreffender Stufenwechsel darf die laufende Aufgabe nie
    umstellen - sonst antwortet man auf eine andere Frage als man sieht."""
    g = make(MathQuiz, is_host=False)
    g.q_index = 3
    seen = g.question
    g.apply_live_down({"lv": [3] * g.n_slots})
    assert g.question == seen, "laufende Aufgabe wurde ausgetauscht"
    assert g.levels[4] == 3, "kommende Aufgaben wurden nicht umgestellt"


def test_host_counts_remote_players_too():
    """Die Trefferquote muss die Leute an anderen Rechnern einschliessen."""
    g = make(MathQuiz, n_players=1)
    g.hits[0] = "1"                       # eigener Spieler richtig
    g.apply_live_up(7, {"h": {"5": "0", "6": "0"}})   # zwei Gaeste falsch
    assert abs(g.hit_rate(0) - 1 / 3) < 1e-6, g.hit_rate(0)
    g.q_index = 1                         # Aufgabe 0 ist damit auswertbar
    g._decide_next_level()
    assert g.levels[2] < g.START_LEVEL, "schlechte Gesamtquote wirkte nicht"


def test_missing_answer_counts_as_wrong():
    g = make(MathQuiz, n_players=1)
    play(g, lambda pid, q, i: None)       # niemand antwortet
    assert g.hits[0] == "0" * g.n_slots
    assert g.levels[-1] == 0


def test_level_is_decided_a_full_question_ahead():
    """Der Vorlauf ist es, der den LAN-Fall rettet: die Stufe fuer Aufgabe i+1
    steht schon fest, waehrend Aufgabe i laeuft."""
    g = make(MathQuiz, n_players=1)
    g.update(0.1)
    assert g._decided_upto >= 1, "keine Entscheidung im Voraus getroffen"


def test_estimate_options_are_far_apart():
    """Beim Schaetzen muessen die Zahlen weit auseinanderliegen."""
    rng = random.Random(4)
    for level in range(EstimateQuiz.LEVELS):
        gaps = []
        for i in range(200):
            q = EstimateQuiz.make_question(rng, i, level)
            vals = sorted(int(o) for o in q["options"])
            right = int(q["options"][q["correct"]])
            gaps.append(min(abs(v - right) for v in vals if v != right) / right)
        worst = min(gaps)
        assert worst > 0.15, (
            "Stufe %d: naechste Antwort nur %.0f%% daneben" % (level, worst * 100))


def test_circles_only_show_up_at_the_hardest_level():
    """Pi war zu schwer - Kreise gibt es nur noch ganz oben, mit Hinweis."""
    rng = random.Random(8)
    for level in range(3):
        kinds = {AreaQuiz.make_question(rng, i, level)["kind"] for i in range(200)}
        assert "circle" not in kinds, "Stufe %d hat Kreise" % level
    top = [AreaQuiz.make_question(rng, i, 3) for i in range(200)]
    circles = [q for q in top if q["kind"] == "circle"]
    assert circles, "auf der hoechsten Stufe fehlen die Kreise"
    assert all(q["hint"] for q in circles), "Kreis ohne Formel-Hinweis"


def test_maths_gets_harder_with_the_level():
    rng = random.Random(3)
    med, mul = [], []
    for level in range(MathQuiz.LEVELS):
        qs = [MathQuiz.make_question(rng, i, level) for i in range(400)]
        med.append(statistics.median(int(q["options"][q["correct"]]) for q in qs))
        mul.append(sum(1 for q in qs if " x " in q["prompt"] or " : " in q["prompt"]))
    assert med[0] < med[1] < med[2] < med[3], "Ergebnisgroesse waechst nicht: %s" % med
    assert mul[0] < mul[3], "oben wird nicht mehr mal/geteilt gerechnet: %s" % mul


def test_easiest_level_stays_doable():
    """Stufe 0 ist der Rettungsanker - die muss wirklich leicht sein."""
    rng = random.Random(6)
    qs = [MathQuiz.make_question(rng, i, 0) for i in range(300)]
    for q in qs:
        val = int(q["options"][q["correct"]])
        assert 0 <= val <= 40, "zu schwer fuer Stufe 0: %s" % q["prompt"]
        assert "+" in q["prompt"] or "-" in q["prompt"] or " x " in q["prompt"]


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
