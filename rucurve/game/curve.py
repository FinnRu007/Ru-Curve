"""Eine Kurve (ein Spieler oder Bot) im Spiel."""

from __future__ import annotations

from collections import deque
from typing import NamedTuple

from . import powerups as _pu
from .powerups import DEFAULT_POWERUP, PowerupState


class Mods(NamedTuple):
    """Aktuell wirksame Modifikatoren aus allen laufenden Effekten."""

    speed: float = 1.0
    width: float = 1.0
    ghost: bool = False
    turn: float = 1.0
    reverse: bool = False
    shield: bool = False
    fog: float = 0.0
    square: bool = False


class Curve:
    def __init__(
        self,
        cid: int,
        name: str,
        color: tuple[int, int, int],
        *,
        is_bot: bool = False,
        is_local: bool = False,
        slot_index: int = -1,
        client_id: int = -1,
        powerup_kind: str = DEFAULT_POWERUP,
        color_index: int = 0,
    ) -> None:
        self.id = cid
        self.name = name
        self.color = color
        self.color_index = color_index
        self.is_bot = is_bot
        self.is_local = is_local
        self.slot_index = slot_index      # welcher lokale Tasten-Slot steuert diese Kurve
        self.client_id = client_id        # -1 = Host/lokal, sonst Netzwerk-Client
        self.powerup_kind = powerup_kind

        # Match-Punkte (ueber Runden hinweg)
        self.score = 0

        # Laufzeit (pro Runde zuruecksetzen)
        self.x = 0.0
        self.y = 0.0
        self.heading = 0.0
        self.alive = True
        self.place = 0                    # Platz beim Ausscheiden (1 = Rundensieg)
        self.turn = 0                     # -1 links, 0, +1 rechts
        self.powerup_pressed = False
        self._pu_edge = False
        self._sq_prev_turn = 0            # fuer das "Eckig"-Powerup
        self._sq_lock = 0.0
        self._bot_turn = 0                # letzte Bot-Entscheidung (Traegheit)

        self.dist_since_gap = 0.0
        self.next_gap_at = 1e9
        self.gap_left = 0.0
        self.dist_travelled = 0.0
        self.pending: deque = deque()     # noch nicht ins Raster uebernommene Stamps
        self.effects: list[list] = []     # [kind, t_left, magnitude]
        self.pu = PowerupState(powerup_kind, 0)

    # ------------------------------------------------------------------ #
    def reset_runtime(self, settings, rng=None) -> None:
        self.alive = True
        self.place = 0
        self.turn = 0
        self.powerup_pressed = False
        self._pu_edge = False
        self._sq_prev_turn = 0
        self._sq_lock = 0.0
        self._bot_turn = 0
        self.dist_since_gap = 0.0
        self.gap_left = 0.0
        self.dist_travelled = 0.0
        self.pending.clear()
        self.effects.clear()
        kind = _pu.resolve(self.powerup_kind, settings, rng)
        cfg = settings.powerup_cfg(kind)
        charges = cfg.charges if cfg.enabled else 0
        self.pu = PowerupState(kind, charges, cfg.cooldown)

    # ------------------------------------------------------------------ #
    def mods(self) -> Mods:
        sm = wm = tm = 1.0
        ghost = reverse = shield = square = False
        fog = 0.0
        for kind, _t, mag in self.effects:
            if kind == "speed":
                sm *= mag
            elif kind == "width":
                wm *= mag
            elif kind == "agile":
                tm *= mag
            elif kind == "ghost":
                ghost = True
            elif kind == "reverse":
                reverse = True
            elif kind == "shield":
                shield = True
            elif kind == "square":
                square = True
            elif kind == "fog":
                fog = max(fog, mag)
        return Mods(sm, wm, ghost, tm, reverse, shield, fog, square)

    def has_effect(self, kind: str) -> bool:
        return any(e[0] == kind for e in self.effects)

    def drop_effect(self, kind: str) -> None:
        self.effects = [e for e in self.effects if e[0] != kind]

    def tick_effects(self, dt: float) -> None:
        for e in self.effects:
            e[1] -= dt
        if self.effects:
            self.effects = [e for e in self.effects if e[1] > 0]
        self.pu.tick(dt)
