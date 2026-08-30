"""Spielerfarben - moeglichst gut unterscheidbar, auch bei Farbsehschwaeche."""

from __future__ import annotations

PLAYER_COLORS: list[tuple[int, int, int]] = [
    (54, 122, 246),   # Blau
    (232, 76, 61),    # Rot
    (46, 190, 129),   # Gruen
    (245, 176, 42),   # Orange
    (167, 99, 235),   # Violett
    (38, 202, 218),   # Tuerkis
    (240, 108, 184),  # Pink
    (166, 217, 64),   # Limette
    (255, 255, 255),  # Weiss
    (128, 142, 166),  # Grau
    (140, 94, 60),    # Braun
    (250, 232, 92),   # Gelb
]

PLAYER_COLOR_NAMES: list[str] = [
    "Blau", "Rot", "Gruen", "Orange", "Violett", "Tuerkis",
    "Pink", "Limette", "Weiss", "Grau", "Braun", "Gelb",
]


def color_for(index: int) -> tuple[int, int, int]:
    return PLAYER_COLORS[index % len(PLAYER_COLORS)]


def color_name(index: int) -> str:
    return PLAYER_COLOR_NAMES[index % len(PLAYER_COLOR_NAMES)]
