"""Datenmodell fuer eine Spielrunde/ein Match (unabhaengig vom Rendering)."""

from __future__ import annotations

import dataclasses
import random
from dataclasses import dataclass, field

from .colors import color_for
from .game.curve import Curve
from .game.world import World


@dataclass
class PlayerDef:
    pid: int
    name: str
    color_index: int
    powerup_kind: str = "speed"
    is_bot: bool = False
    is_local: bool = False
    slot_index: int = -1        # lokaler Tasten-Slot (nur is_local)
    client_id: int = -1         # -1 = Host/lokal, sonst Netzwerk
    difficulty: float = 0.5
    ready: bool = True

    def to_wire(self) -> dict:
        return {
            "pid": self.pid,
            "name": self.name,
            "color_index": self.color_index,
            "powerup_kind": self.powerup_kind,
            "is_bot": self.is_bot,
            "client_id": self.client_id,
            "ready": self.ready,
        }


def curve_from_def(p: PlayerDef) -> Curve:
    return Curve(
        p.pid,
        p.name,
        color_for(p.color_index),
        is_bot=p.is_bot,
        is_local=p.is_local,
        slot_index=p.slot_index,
        client_id=p.client_id,
        powerup_kind=p.powerup_kind,
        color_index=p.color_index,
    )


@dataclass
class GameSession:
    settings: object
    players: list[PlayerDef]
    host: object | None = None            # net.host.GameHost oder None
    beacon: object | None = None
    curves: list[Curve] = field(default_factory=list)
    world: World | None = None
    round_no: int = 0

    def __post_init__(self) -> None:
        if not self.curves:
            self.curves = [curve_from_def(p) for p in self.players]

    def new_round(self, view_size: tuple[int, int] | None = None) -> World:
        self.round_no += 1
        ws = self.settings
        if view_size:
            w, h = self.settings.arena_dims(*view_size)
            ws = dataclasses.replace(self.settings, arena_width=w, arena_height=h)
        self.world = World(ws, self.curves, rng=random.Random())
        return self.world

    def match_winner(self) -> Curve | None:
        return self.world.match_winner() if self.world else None

    def standings(self) -> list[dict]:
        rows = sorted(self.curves, key=lambda c: -c.score)
        return [
            {"name": c.name, "color_index": c.color_index, "score": c.score, "pid": c.id}
            for c in rows
        ]

    def shutdown(self) -> None:
        if self.beacon:
            self.beacon.stop()
        if self.host:
            self.host.stop()
