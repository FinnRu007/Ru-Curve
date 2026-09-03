"""Turnier-Zustand: Spielreihenfolge, Punktevergabe, Gesamtrangliste."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .base import PartyPlayer, Result


def points_for_place(place: int, n_players: int, top: int = 10) -> int:
    """Platz 1 bekommt `top` Punkte, der letzte Platz 1 - linear dazwischen.

    **Kein Platz darf so viele Punkte bekommen wie der davor.** Mit festem
    `top` ging das schief, sobald mehr Leute mitspielen als es Punkte gibt:
    bei 10 Punkten und 20 Spielern bekamen Platz 1 und 2 beide zehn, weil
    zwischen den Plaetzen nur noch ein halber Punkt lag und gerundet wurde.
    Darum ist die Spanne mindestens so gross wie das Feld - bei vielen
    Spielern waechst die Punktzahl fuer Platz 1 also mit.
    """
    if n_players <= 1:
        return top
    span = max(1, top - 1, n_players - 1)
    return int(1 + round(span * (n_players - place) / (n_players - 1)))


def rank_results(results: dict[int, Result], scoring: str = "high") -> list[dict]:
    """Sortiert Ergebnisse zu Plaetzen. Gleichstand -> die schnellere Zeit vorn.

    Wer gar nicht mitgespielt hat (done=False), landet hinten.
    """
    rows = []
    for pid, r in results.items():
        rows.append({"pid": pid, "raw": r.raw, "time": r.time,
                     "detail": r.detail, "done": r.done})
    sign = -1.0 if scoring == "high" else 1.0
    rows.sort(key=lambda r: (not r["done"], sign * r["raw"], r["time"]))

    place = 0
    prev_key = None
    for i, row in enumerate(rows):
        key = (row["done"], row["raw"], round(row["time"], 3))
        if key != prev_key:
            place = i + 1
            prev_key = key
        row["place"] = place
    return rows


@dataclass
class GameRecord:
    game_id: str
    game_name: str
    rows: list[dict] = field(default_factory=list)   # pid, raw, time, place, points


@dataclass
class Tournament:
    players: list[PartyPlayer]
    order: list[str] = field(default_factory=list)
    index: int = -1                       # aktuell laufendes Minispiel
    totals: dict[int, int] = field(default_factory=dict)
    history: list[GameRecord] = field(default_factory=list)
    points_top: int = 10

    def __post_init__(self) -> None:
        for p in self.players:
            self.totals.setdefault(p.pid, 0)

    # ------------------------------------------------------------------ #
    @staticmethod
    def build_order(rng: random.Random, game_ids: list[str], count: int,
                    shuffle: bool = True) -> list[str]:
        """Reihenfolge der Minispiele: erst jedes einmal, dann wiederholen."""
        if not game_ids:
            return []
        pool = list(game_ids)
        order: list[str] = []
        while len(order) < count:
            chunk = list(pool)
            if shuffle:
                rng.shuffle(chunk)
            order.extend(chunk)
        return order[:count]

    # ------------------------------------------------------------------ #
    @property
    def current_id(self) -> str | None:
        if 0 <= self.index < len(self.order):
            return self.order[self.index]
        return None

    @property
    def total_games(self) -> int:
        return len(self.order)

    @property
    def done(self) -> bool:
        return self.index >= len(self.order) - 1 and bool(self.history)

    def advance(self) -> str | None:
        self.index += 1
        return self.current_id

    # ------------------------------------------------------------------ #
    def apply_results(self, game_id: str, game_name: str,
                      results: dict[int, Result], scoring: str = "high") -> GameRecord:
        """Punkte vergeben und in die Gesamtwertung uebernehmen."""
        full = {p.pid: results.get(p.pid, Result()) for p in self.players}
        rows = rank_results(full, scoring)
        n = len(self.players)
        for row in rows:
            pts = points_for_place(row["place"], n, self.points_top) if row["done"] else 0
            row["points"] = pts
            if not row["done"] and not row["detail"]:
                # Sonst steht in der Ergebnisliste eine leere Zeile mit 0
                # Punkten und niemand weiss, warum.
                row["detail"] = "nicht mitgespielt"
            self.totals[row["pid"]] = self.totals.get(row["pid"], 0) + pts
        rec = GameRecord(game_id, game_name, rows)
        self.history.append(rec)
        return rec

    # ------------------------------------------------------------------ #
    def standings(self) -> list[dict]:
        """Gesamtrangliste, bester zuerst."""
        rows = []
        for p in self.players:
            rows.append({"pid": p.pid, "name": p.name, "color_index": p.color_index,
                         "points": self.totals.get(p.pid, 0)})
        rows.sort(key=lambda r: (-r["points"], r["name"].lower()))
        place = 0
        prev = None
        for i, r in enumerate(rows):
            if r["points"] != prev:
                place = i + 1
                prev = r["points"]
            r["place"] = place
        return rows

    def winner(self) -> dict | None:
        st = self.standings()
        return st[0] if st else None

    def to_wire(self) -> dict:
        return {
            "order": self.order, "index": self.index,
            "totals": {str(k): v for k, v in self.totals.items()},
            "points_top": self.points_top,
        }

    def load_wire(self, d: dict) -> None:
        self.order = list(d.get("order", self.order))
        self.index = int(d.get("index", self.index))
        self.points_top = int(d.get("points_top", self.points_top))
        for k, v in (d.get("totals") or {}).items():
            self.totals[int(k)] = int(v)
