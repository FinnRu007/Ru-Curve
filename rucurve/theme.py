"""Design-Tokens - abgeleitet aus dem Ru-Design-System (DESIGN.md).

Weisser Hintergrund, EIN Akzent (#2A4CE0), Manrope (Display) + Inter (Text),
Pill-Buttons, weiche Radien 10 / 16 / 24 / 999.
"""

from __future__ import annotations

import os

import pygame

# --- Farben -----------------------------------------------------------------
BG = (255, 255, 255)
SURFACE = (247, 248, 251)
SURFACE_ALT = (238, 240, 246)
BORDER = (223, 226, 234)
TEXT = (22, 26, 37)
TEXT_MUTED = (108, 116, 133)
ACCENT = (42, 76, 224)
ACCENT_DARK = (32, 58, 178)
ACCENT_SOFT = (231, 236, 253)
DANGER = (214, 64, 64)
OK = (40, 168, 112)
WARN = (214, 154, 48)

# Spielfeld (dunkel, damit die Farben leuchten)
ARENA_BG = (18, 20, 28)
ARENA_BORDER = (60, 66, 86)

# --- Radien ----------------------------------------------------------------
R_SM = 10
R_MD = 16
R_LG = 24
R_PILL = 999

# --- Spacing (4px-Raster) ------------------------------------------------
SP = 4

_ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_FONT_DIR = os.path.join(_ASSET_DIR, "fonts")


def asset_path(*parts: str) -> str:
    return os.path.join(_ASSET_DIR, *parts)


class FontBook:
    """Laedt Manrope/Inter falls vorhanden, sonst System-Fallback (Segoe UI)."""

    def __init__(self) -> None:
        self._display = self._find(("Manrope-Bold.ttf", "Manrope-SemiBold.ttf"))
        self._body = self._find(("Inter-Regular.ttf", "Inter.ttf"))
        self._body_bold = self._find(("Inter-SemiBold.ttf", "Inter-Bold.ttf"))
        self._cache: dict[tuple[str, int], pygame.font.Font] = {}

    @staticmethod
    def _find(names: tuple[str, ...]) -> str | None:
        for n in names:
            p = os.path.join(_FONT_DIR, n)
            if os.path.isfile(p):
                return p
        return None

    def _load(self, kind: str, size: int) -> pygame.font.Font:
        key = (kind, size)
        f = self._cache.get(key)
        if f is not None:
            return f
        path = {"display": self._display, "body": self._body, "body_bold": self._body_bold}[kind]
        if path:
            f = pygame.font.Font(path, size)
        else:
            sysname = "Segoe UI" if kind == "body" else "Segoe UI Semibold,Segoe UI"
            f = pygame.font.SysFont(sysname, size, bold=(kind != "body"))
        self._cache[key] = f
        return f

    def display(self, size: int) -> pygame.font.Font:
        return self._load("display", size)

    def body(self, size: int) -> pygame.font.Font:
        return self._load("body", size)

    def body_bold(self, size: int) -> pygame.font.Font:
        return self._load("body_bold", size)
