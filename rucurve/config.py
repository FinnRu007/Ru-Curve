"""Einstellungen + Tastenbelegung, inkl. Laden/Speichern als JSON.

Ablage: %APPDATA%/Ru-Curve/config.json  (Fallback: neben dem Programm).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields

import pygame

APP_NAME = "Ru-Curve"
DISCOVERY_PORT = 51737
DEFAULT_GAME_PORT = 51738


# --------------------------------------------------------------------------- #
#  Pfade
# --------------------------------------------------------------------------- #
def config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    try:
        os.makedirs(d, exist_ok=True)
        return d
    except OSError:
        return os.path.dirname(os.path.abspath(sys.argv[0] or "."))


def config_path() -> str:
    return os.path.join(config_dir(), "config.json")


# --------------------------------------------------------------------------- #
#  Gameplay-Parameter  (alles hiervon ist in der Einstellungsseite justierbar)
# --------------------------------------------------------------------------- #
@dataclass
class GameSettings:
    # Bewegung
    speed: float = 95.0              # Grundgeschwindigkeit in px/s
    turn_radius: float = 55.0        # Lenkradius in px  ->  turn_rate = speed / turn_radius
    line_width: float = 4.0          # Linienbreite in px

    # Luecken hinter sich
    gap_distance: float = 260.0      # mittlerer Abstand zwischen Luecken (px)
    gap_distance_jitter: float = 0.45  # +/- Anteil Zufall auf den Abstand
    gap_size: float = 42.0           # Laenge einer Luecke (px)

    # Powerup
    powerup_duration: float = 2.0    # Wirkdauer in s
    powerup_boost_factor: float = 1.9  # Geschwindigkeits-Faktor beim Speed-Powerup
    powerup_charges: int = 3         # Ladungen pro Runde
    powerup_cooldown: float = 6.0    # Sekunden zwischen zwei Aktivierungen

    # Punkte / Matchende
    points_per_opponent: int = 1     # Punkte je ueberlebtem Gegner
    target_score: int = 25           # Punkte zum Matchsieg

    # Runde
    countdown_seconds: float = 3.0
    self_collision: bool = True
    round_time_limit: float = 0.0    # 0 = kein Zeitlimit

    # Arena
    arena_width: int = 1500
    arena_height: int = 900

    # Bots
    bot_count: int = 0
    bot_difficulty: float = 0.5      # 0 (leicht) .. 1 (stark)

    # Audio
    sound_volume: float = 0.7
    music_volume: float = 0.35

    # Fenster
    fullscreen: bool = False
    window_width: int = 1600
    window_height: int = 960

    def turn_rate(self) -> float:
        """Winkelgeschwindigkeit in rad/s aus Geschwindigkeit und Lenkradius."""
        return self.speed / max(1.0, self.turn_radius)

    def clamped(self) -> "GameSettings":
        c = GameSettings(**asdict(self))
        c.speed = _clamp(c.speed, 30, 400)
        c.turn_radius = _clamp(c.turn_radius, 12, 400)
        c.line_width = _clamp(c.line_width, 1.5, 20)
        c.gap_distance = _clamp(c.gap_distance, 40, 1200)
        c.gap_distance_jitter = _clamp(c.gap_distance_jitter, 0.0, 0.9)
        c.gap_size = _clamp(c.gap_size, 6, 200)
        c.powerup_duration = _clamp(c.powerup_duration, 0.2, 10)
        c.powerup_boost_factor = _clamp(c.powerup_boost_factor, 1.05, 4.0)
        c.powerup_charges = int(_clamp(c.powerup_charges, 0, 50))
        c.powerup_cooldown = _clamp(c.powerup_cooldown, 0.0, 30)
        c.points_per_opponent = int(_clamp(c.points_per_opponent, 1, 10))
        c.target_score = int(_clamp(c.target_score, 1, 500))
        c.countdown_seconds = _clamp(c.countdown_seconds, 0.0, 10)
        c.round_time_limit = _clamp(c.round_time_limit, 0.0, 600)
        c.arena_width = int(_clamp(c.arena_width, 600, 4000))
        c.arena_height = int(_clamp(c.arena_height, 400, 4000))
        c.bot_count = int(_clamp(c.bot_count, 0, 11))
        c.bot_difficulty = _clamp(c.bot_difficulty, 0.0, 1.0)
        c.sound_volume = _clamp(c.sound_volume, 0.0, 1.0)
        c.music_volume = _clamp(c.music_volume, 0.0, 1.0)
        return c


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# --------------------------------------------------------------------------- #
#  Tastenbelegung pro lokalem Spieler-Slot
# --------------------------------------------------------------------------- #
@dataclass
class PlayerSlot:
    name: str = "Spieler"
    left: int = pygame.K_LEFT
    right: int = pygame.K_RIGHT
    powerup: int = pygame.K_DOWN
    powerup_kind: str = "speed"
    color_index: int = 0
    enabled: bool = True


def default_slots() -> list[PlayerSlot]:
    return [
        PlayerSlot("Blau", pygame.K_LEFT, pygame.K_RIGHT, pygame.K_DOWN, "speed", 0, True),
        PlayerSlot("Rot", pygame.K_y, pygame.K_x, pygame.K_c, "speed", 1, True),
        PlayerSlot("Gruen", pygame.K_v, pygame.K_b, pygame.K_n, "speed", 2, False),
        PlayerSlot("Orange", pygame.K_COMMA, pygame.K_PERIOD, pygame.K_SLASH, "speed", 3, False),
        PlayerSlot("Violett", pygame.K_KP4, pygame.K_KP6, pygame.K_KP5, "speed", 4, False),
        PlayerSlot("Tuerkis", pygame.K_HOME, pygame.K_PAGEUP, pygame.K_END, "speed", 5, False),
    ]


# --------------------------------------------------------------------------- #
#  Gesamt-Konfiguration
# --------------------------------------------------------------------------- #
@dataclass
class Config:
    settings: GameSettings = field(default_factory=GameSettings)
    slots: list[PlayerSlot] = field(default_factory=default_slots)
    last_player_name: str = "Host"

    # ------------------------------------------------------------------ #
    def save(self, path: str | None = None) -> None:
        path = path or config_path()
        data = {
            "settings": asdict(self.settings),
            "slots": [asdict(s) for s in self.slots],
            "last_player_name": self.last_player_name,
        }
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            os.replace(tmp, path)
        except OSError as exc:  # pragma: no cover - reiner Schutz
            print(f"[config] Speichern fehlgeschlagen: {exc}")

    # ------------------------------------------------------------------ #
    @classmethod
    def load(cls, path: str | None = None) -> "Config":
        path = path or config_path()
        if not os.path.isfile(path):
            return cls()
        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError) as exc:
            print(f"[config] Laden fehlgeschlagen ({exc}) - benutze Standardwerte.")
            return cls()

        settings = _from_dict(GameSettings, raw.get("settings", {}))
        slots_raw = raw.get("slots") or []
        slots = [_from_dict(PlayerSlot, s) for s in slots_raw] or default_slots()
        return cls(
            settings=settings.clamped(),
            slots=slots,
            last_player_name=str(raw.get("last_player_name", "Host")),
        )


def _from_dict(dc_type, data: dict):
    """Baut ein Dataclass nur aus bekannten Feldern - unbekannte Keys werden ignoriert."""
    known = {f.name for f in fields(dc_type)}
    kwargs = {k: v for k, v in (data or {}).items() if k in known}
    return dc_type(**kwargs)
