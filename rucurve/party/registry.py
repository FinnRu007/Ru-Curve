"""Liste aller Minispiele des Turniers."""

from __future__ import annotations

from .games.curve_game import CurveGame
from .games.race import RaceGame
from .games.quizzes import AreaQuiz, EstimateQuiz, MathQuiz, OddOneQuiz
from .games.reflex import (
    MashGame,
    ReactionGame,
    SequenceGame,
    StopBarGame,
    TimeSenseGame,
)

ALL_GAMES = [
    ReactionGame,
    SequenceGame,
    MathQuiz,
    AreaQuiz,
    EstimateQuiz,
    OddOneQuiz,
    MashGame,
    StopBarGame,
    TimeSenseGame,
    RaceGame,
    CurveGame,
]

GAME_BY_ID = {g.id: g for g in ALL_GAMES}
GAME_IDS = [g.id for g in ALL_GAMES]


def game_name(gid: str) -> str:
    g = GAME_BY_ID.get(gid)
    return g.name if g else gid


def game_rules(gid: str) -> str:
    g = GAME_BY_ID.get(gid)
    return g.rules if g else ""
