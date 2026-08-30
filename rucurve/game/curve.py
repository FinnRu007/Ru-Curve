"""Eine Kurve (ein Spieler oder Bot) im Spiel."""

from __future__ import annotations

from collections import deque

from .powerups import DEFAULT_POWERUP, PowerupState


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

        self.dist_since_gap = 0.0
        self.next_gap_at = 1e9
        self.gap_left = 0.0
        self.dist_travelled = 0.0
        self.pending: deque = deque()     # noch nicht ins Raster uebernommene Stamps
        self.effects: list[list] = []     # [kind, t_left, magnitude]
        self.pu = PowerupState(powerup_kind, 0)

    # ------------------------------------------------------------------ #
    def reset_runtime(self, powerup_charges: int) -> None:
        self.alive = True
        self.place = 0
        self.turn = 0
        self.powerup_pressed = False
        self._pu_edge = False
        self.dist_since_gap = 0.0
        self.gap_left = 0.0
        self.dist_travelled = 0.0
        self.pending.clear()
        self.effects.clear()
        self.pu = PowerupState(self.powerup_kind, powerup_charges)

    # ------------------------------------------------------------------ #
    def effect_mods(self) -> tuple[float, float, bool]:
        """(speed_mult, width_mult, ghost) aus den aktiven Effekten."""
        sm = wm = 1.0
        ghost = False
        for kind, _t, mag in self.effects:
            if kind in ("speed", "slow"):
                sm *= mag
            elif kind == "thin":
                wm *= mag
            elif kind == "ghost":
                ghost = True
        return sm, wm, ghost

    def tick_effects(self, dt: float) -> None:
        for e in self.effects:
            e[1] -= dt
        if self.effects:
            self.effects = [e for e in self.effects if e[1] > 0]
        self.pu.tick(dt)
