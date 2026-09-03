"""Grundgeruest fuer Minispiele.

Zentrale Entwurfsentscheidung: **jeder Spieler hat genau drei Tasten**
(Links / Aktion / Rechts - dieselben wie bei Achtung die Kurve). Alle
Tastatur-Minispiele kommen damit aus. Dadurch koennen beliebig viele Leute an
einer Tastatur spielen und dieselbe Logik laeuft unveraendert uebers LAN.

Ablauf eines Minispiels:
  * Der Host wuerfelt mit `make_config(rng, players, area)` die Aufgaben aus
    und schickt sie an alle. `area` ist der Spielbereich des HOSTS - wer
    daraus Spielfeldmasse ableitet, muss sie hier hineinschreiben, sonst
    rechnet jeder Rechner mit seinem eigenen Fenster und die Karte sieht
    ueberall anders aus. Jede Maschine baut daraus dasselbe Minispiel.
  * Jede Maschine spielt es fuer ihre *eigenen* Spieler und meldet am Ende
    `results()` an den Host.
  * Der Host vergibt Punkte und verteilt die Rangliste.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

# Die drei Tasten, die jedem Spieler zur Verfuegung stehen
BTN_LEFT, BTN_ACTION, BTN_RIGHT = 0, 1, 2
BTN_NAMES = ("Links", "Aktion", "Rechts")
BTN_SYMBOLS = ("<", "*", ">")


@dataclass
class PartyPlayer:
    """Ein Teilnehmer am Turnier - unabhaengig vom Minispiel."""

    pid: int
    name: str
    color: tuple
    color_index: int
    is_local: bool = False
    is_bot: bool = False
    slot_index: int = -1
    client_id: int = -1
    difficulty: float = 0.5

    def to_wire(self) -> dict:
        return {
            "pid": self.pid, "name": self.name, "color_index": self.color_index,
            "is_bot": self.is_bot, "client_id": self.client_id,
            "difficulty": self.difficulty,
        }

    @staticmethod
    def from_wire(d: dict, local_client_id: int | None = None) -> "PartyPlayer":
        from ..colors import color_for

        cid = int(d.get("client_id", -1))
        return PartyPlayer(
            pid=int(d["pid"]), name=str(d.get("name", "?")),
            color=color_for(int(d.get("color_index", 0))),
            color_index=int(d.get("color_index", 0)),
            is_bot=bool(d.get("is_bot", False)),
            client_id=cid,
            is_local=(local_client_id is not None and cid == local_client_id),
            difficulty=float(d.get("difficulty", 0.5)),
        )


@dataclass
class Result:
    """Ergebnis eines Spielers in einem Minispiel."""

    raw: float = 0.0        # Rohwert (Treffer, Presses, Sekunden ...)
    time: float = 0.0       # Zeit als Gleichstand-Entscheider (kleiner = besser)
    detail: str = ""        # kurze Anzeige, z.B. "7/10"
    done: bool = False

    def to_wire(self) -> dict:
        return {"raw": round(self.raw, 4), "time": round(self.time, 4),
                "detail": self.detail, "done": self.done}

    @staticmethod
    def from_wire(d: dict) -> "Result":
        return Result(float(d.get("raw", 0)), float(d.get("time", 0)),
                      str(d.get("detail", "")), bool(d.get("done", False)))


@dataclass
class GameContext:
    """Alles, was ein Minispiel zum Laufen braucht."""

    app: object
    players: list[PartyPlayer]
    local_pids: list[int]
    bindings: dict          # pid -> (key_left, key_action, key_right)
    config: dict = field(default_factory=dict)
    area: pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 800, 600))
    is_host: bool = True
    rng_seed: int = 0

    def player(self, pid: int) -> PartyPlayer | None:
        for p in self.players:
            if p.pid == pid:
                return p
        return None

    @property
    def local_players(self) -> list[PartyPlayer]:
        return [p for p in self.players if p.pid in self.local_pids]

    @property
    def fonts(self):
        return self.app.fonts

    def play(self, sound: str) -> None:
        self.app.audio.play(sound)


class MiniGame:
    """Basisklasse. Unterklassen ueberschreiben make_config/update/draw/..."""

    id = "base"
    name = "Minispiel"
    rules = ""
    # Fuer den Erklaerungsschirm vor dem Spiel. `key_help` beschreibt, was
    # die drei Tasten HIER tun - "Aktion" allein sagt niemandem etwas.
    goal = ""                    # worum geht es? (ein, zwei Saetze)
    key_help = ("", "", "")      # links / Aktion / rechts
    scoring_help = ""            # wofuer gibt es Punkte?
    input_mode = "keys"          # "keys" | "mouse" | "curve"
    hotseat = False              # true -> lokale Spieler nacheinander (Maus)
    intro_seconds = 6.0
    max_seconds = 60.0
    scoring = "high"             # "high" = mehr ist besser, "low" = weniger
    # authoritative: der Host rechnet fuer ALLE (z.B. Achtung die Kurve).
    # Sonst spielt jede Maschine ihre eigenen Leute und meldet nur das Ergebnis.
    authoritative = False

    # ------------------------------------------------------------------ #
    @staticmethod
    def make_config(rng, players: list[PartyPlayer], area=None,
                    settings=None) -> dict:
        """Wird NUR auf dem Host gerufen und an alle verteilt.

        `area` ist der Spielbereich auf dem Bildschirm des Hosts. Alles, was
        davon abhaengt, gehoert in die Rueckgabe - die Clients haben andere
        Fenstergroessen.
        """
        return {}

    def __init__(self, ctx: GameContext) -> None:
        self.ctx = ctx
        # Laufender Stand ALLER Spieler, auch der an anderen Rechnern.
        # Wird von der Turnier-Szene jeden Frame gesetzt.
        self.live_all: dict[int, float] = {}
        self.cfg = ctx.config
        self.results_map: dict[int, Result] = {
            pid: Result() for pid in ctx.local_pids
        }
        self.elapsed = 0.0
        self._finished = False

    # -- Ablauf ---------------------------------------------------------
    def start(self) -> None:
        """Nach dem Intro, wenn es wirklich losgeht."""

    def handle_events(self, events) -> None: ...

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.elapsed >= self.max_seconds:
            self.finish()

    def draw(self, surf) -> None: ...

    def on_resize(self, area) -> None:
        """Fenstergroesse geaendert - Standard: nichts zu tun."""

    # -- Ergebnis -------------------------------------------------------
    def finish(self) -> None:
        for r in self.results_map.values():
            r.done = True
        self._finished = True

    @property
    def finished(self) -> bool:
        return self._finished

    def results(self) -> dict[int, Result]:
        return self.results_map

    live_unit = ""               # Einheit hinter dem Live-Wert, z.B. " Pkt"

    def live_rows(self) -> dict[int, float]:
        """Zwischenstand fuer die Live-Rangliste (Rohwert je Spieler)."""
        return {pid: r.raw for pid, r in self.results_map.items()}

    def board_players(self, max_extra: int = 4) -> list:
        """Wen der Hauptbereich zeigen soll: eigene Leute zuerst, dann die
        besten echten Mitspieler von anderen Rechnern.

        Bots bleiben draussen - die stehen in der Rangliste rechts und wuerden
        den Platz wegnehmen, um den es hier geht.
        """
        own = [p for p in self.ctx.players if p.pid in self.ctx.local_pids]
        own_ids = {p.pid for p in own}
        remote = [p for p in self.ctx.players
                  if p.pid not in own_ids and not p.is_bot]
        remote.sort(key=lambda p: -float(self.live_all.get(p.pid, 0.0)))
        return own + remote[:max(0, max_extra)]

    def board_value(self, pid: int, own):
        """Wert eines Spielers fuers Hauptfeld - eigener Stand oder Live-Wert."""
        if pid in own:
            return own[pid]
        return self.live_all.get(pid)

    @classmethod
    def live_label(cls, value) -> str:
        """Live-Wert lesbar machen - ganze Zahlen ohne ".0"."""
        try:
            v = float(value)
        except (TypeError, ValueError):
            return str(value)
        text = "%d" % round(v) if abs(v - round(v)) < 0.05 else "%.1f" % v
        return text + cls.live_unit

    # -- Hilfen fuer Unterklassen --------------------------------------
    def button_of(self, pid: int, key: int) -> int | None:
        """Welche der drei Tasten dieses Spielers wurde gedrueckt?"""
        binding = self.ctx.bindings.get(pid)
        if not binding:
            return None
        for idx, code in enumerate(binding):
            if code == key:
                return idx
        return None

    # -- Netzwerk (nur fuer authoritative Spiele noetig) ----------------
    def net_state(self) -> dict | None:
        """Host -> Clients: Spielzustand (None = nichts zu senden)."""
        return None

    def apply_state(self, data: dict) -> None:
        """Client: Zustand vom Host uebernehmen."""

    def net_input(self) -> dict | None:
        """Client -> Host: Eingaben der eigenen Spieler."""
        return None

    def apply_input(self, client_id: int, data: dict) -> None:
        """Host: Eingaben eines Clients einspielen."""

    # -- Kleiner Zusatzkanal, der auf den Live-Nachrichten mitreist -----
    # Wird ~3x pro Sekunde gesendet und ist damit selbstheilend: geht ein
    # Paket verloren, ist der Stand einen Frame spaeter wieder richtig.
    def net_live_up(self) -> dict | None:
        """Client -> Host: was der Host von diesem Rechner wissen muss."""
        return None

    def apply_live_up(self, client_id: int, data: dict) -> None:
        """Host: Zusatzdaten eines Clients einspielen."""

    def net_live_down(self) -> dict | None:
        """Host -> Clients: Entscheidungen, die ueberall gleich gelten muessen."""
        return None

    def apply_live_down(self, data: dict) -> None:
        """Client: Entscheidung des Hosts uebernehmen."""

    def host_results(self) -> dict:
        """Nur bei authoritative: Ergebnis fuer ALLE Spieler."""
        return self.results_map

    def pressed_buttons(self, event_key: int) -> list[tuple[int, int]]:
        """(pid, button) fuer alle lokalen Spieler, die diese Taste haben."""
        out = []
        for pid in self.ctx.local_pids:
            btn = self.button_of(pid, event_key)
            if btn is not None:
                out.append((pid, btn))
        return out
