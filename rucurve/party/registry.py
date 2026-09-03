"""Liste aller Minispiele des Turniers.

Die Reihenfolge hier ist auch die Reihenfolge in der Auswahl und in den
Einstellungen. Grob sortiert: erst die ruhigen Kopfspiele, dann die
Echtzeitspiele, in denen man sich gegenseitig in die Quere kommt.

Bewusst NICHT mehr dabei: "Stopp!" (Zeiger anhalten) und "Zeitgefuehl"
(druecken, wenn die Zeit um ist). Beide waren reine Einzelpraezision - man
haette sie genauso gut allein spielen koennen, und genau das soll das
Turnier nicht sein.
"""

from __future__ import annotations

from .games.curve_game import CurveGame
from .games.harvest import HarvestGame
from .games.quizzes import AreaQuiz, EstimateQuiz, MathQuiz, OddOneQuiz
from .games.race import RaceGame
from .games.reflex import MashGame, ReactionGame, SequenceGame
from .games.sumo import SumoGame
from .games.tag import TagGame

ALL_GAMES = [
    ReactionGame,
    SequenceGame,
    MathQuiz,
    AreaQuiz,
    EstimateQuiz,
    OddOneQuiz,
    MashGame,
    HarvestGame,
    TagGame,
    SumoGame,
    RaceGame,
    CurveGame,
]

# Spiele, in denen man direkt aufeinander einwirkt (der Host rechnet fuer alle)
INTERACTIVE_IDS = [g.id for g in ALL_GAMES if g.authoritative]

GAME_BY_ID = {g.id: g for g in ALL_GAMES}
GAME_IDS = [g.id for g in ALL_GAMES]


def game_name(gid: str) -> str:
    g = GAME_BY_ID.get(gid)
    return g.name if g else gid


def game_rules(gid: str) -> str:
    g = GAME_BY_ID.get(gid)
    return g.rules if g else ""
