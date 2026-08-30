"""Powerups: Metadaten, Standardwerte und Aktivierungslogik.

Jedes Powerup bringt seine eigenen Standardwerte mit (Dauer, Staerke, Ladungen,
Abklingzeit). Die Einstellungsseite baut daraus automatisch je einen
aufklappbaren Block; die Werte landen in GameSettings.powerups[<id>].

Feld `strength_range` = (min, max, schritt, nachkommastellen).
`duration = None`  -> Sofort-Effekt ohne Wirkdauer.
`strength = None`  -> Powerup hat keinen Staerke-Regler.
"""

from __future__ import annotations

POWERUPS: list[dict] = [
    {
        "id": "speed",
        "label": "Speed-Schub",
        "desc": "Du wirst fuer kurze Zeit deutlich schneller.",
        "duration": 2.0, "charges": 3, "cooldown": 6.0,
        "strength": 1.9, "strength_label": "Tempo-Faktor",
        "strength_range": (1.05, 4.0, 0.05, 2), "strength_suffix": " x",
    },
    {
        "id": "agile",
        "label": "Wendig",
        "desc": "Du lenkst kurzzeitig viel enger - gut zum Ausbrechen.",
        "duration": 2.5, "charges": 3, "cooldown": 6.0,
        "strength": 2.2, "strength_label": "Lenk-Faktor",
        "strength_range": (1.1, 5.0, 0.1, 1), "strength_suffix": " x",
    },
    {
        "id": "thin",
        "label": "Duenne Linie",
        "desc": "Deine eigene Linie wird kurzzeitig viel schmaler.",
        "duration": 3.0, "charges": 3, "cooldown": 6.0,
        "strength": 0.45, "strength_label": "Breiten-Faktor",
        "strength_range": (0.15, 0.95, 0.05, 2), "strength_suffix": " x",
    },
    {
        "id": "ghost",
        "label": "Geist",
        "desc": "Du fliegst kurz durch alle Linien hindurch und ziehst keine Spur.",
        "duration": 1.6, "charges": 2, "cooldown": 8.0,
        "strength": None,
    },
    {
        "id": "shield",
        "label": "Schutzschild",
        "desc": "Ein Crash wird abgefangen - danach bist du kurz unverwundbar.",
        "duration": 12.0, "charges": 2, "cooldown": 8.0,
        "strength": 1.0, "strength_label": "Freie Sekunden nach dem Treffer",
        "strength_range": (0.3, 4.0, 0.1, 1), "strength_suffix": " s",
    },
    {
        "id": "teleport",
        "label": "Sprung",
        "desc": "Du springst sofort ein Stueck nach vorne - ohne Spur dazwischen.",
        "duration": None, "charges": 2, "cooldown": 7.0,
        "strength": 150.0, "strength_label": "Sprungweite",
        "strength_range": (40, 600, 10, 0), "strength_suffix": " px",
    },
    {
        "id": "extra_gap",
        "label": "Extra-Luecke",
        "desc": "Reisst sofort eine grosse Luecke in deine Spur.",
        "duration": None, "charges": 3, "cooldown": 5.0,
        "strength": 140.0, "strength_label": "Luecken-Laenge",
        "strength_range": (40, 600, 10, 0), "strength_suffix": " px",
    },
    {
        "id": "square",
        "label": "Eckig",
        "desc": "Nur noch 90-Grad-Ecken: jeder Tastendruck knickt die Linie ab.",
        "duration": 5.0, "charges": 2, "cooldown": 8.0,
        "strength": None,
    },
    {
        "id": "slow_others",
        "label": "Gegner bremsen",
        "desc": "Alle anderen werden kurzzeitig langsamer.",
        "duration": 2.5, "charges": 2, "cooldown": 8.0,
        "strength": 0.55, "strength_label": "Tempo-Faktor der Gegner",
        "strength_range": (0.2, 0.95, 0.05, 2), "strength_suffix": " x",
    },
    {
        "id": "fat_others",
        "label": "Gegner-Linien dick",
        "desc": "Die Linien aller anderen werden kurzzeitig viel breiter.",
        "duration": 3.0, "charges": 2, "cooldown": 8.0,
        "strength": 2.4, "strength_label": "Breiten-Faktor der Gegner",
        "strength_range": (1.2, 5.0, 0.1, 1), "strength_suffix": " x",
    },
    {
        "id": "reverse_others",
        "label": "Gegner verdrehen",
        "desc": "Vertauscht bei allen anderen kurz links und rechts.",
        "duration": 2.5, "charges": 2, "cooldown": 9.0,
        "strength": None,
    },
    {
        "id": "invert",
        "label": "Farben umkehren",
        "desc": "Kehrt fuer alle die Bildschirmfarben um - sehr verwirrend.",
        "duration": 3.0, "charges": 2, "cooldown": 9.0,
        "strength": None,
    },
    {
        "id": "fog",
        "label": "Nebel",
        "desc": "Verdunkelt das Feld fuer alle - man sieht nur noch um sich herum.",
        "duration": 3.5, "charges": 2, "cooldown": 9.0,
        "strength": 150.0, "strength_label": "Sichtweite",
        "strength_range": (50, 500, 10, 0), "strength_suffix": " px",
    },
    {
        "id": "clear",
        "label": "Radiergummi",
        "desc": "Loescht alle bisherigen Linien auf dem Feld.",
        "duration": None, "charges": 1, "cooldown": 15.0,
        "strength": None,
    },
]

POWERUP_BY_ID: dict[str, dict] = {p["id"]: p for p in POWERUPS}
POWERUP_IDS: list[str] = [p["id"] for p in POWERUPS]
DEFAULT_POWERUP = "speed"

# Pseudo-Auswahl: wird zu Beginn JEDER Runde neu ausgewuerfelt.
RANDOM_ID = "random"
RANDOM_LABEL = "Zufaellig"

# Auswahlliste fuer alle Dropdowns (Lobby, Steuerung, Client-Lobby)
PICKER_OPTIONS: list[tuple[str, str]] = (
    [(RANDOM_ID, RANDOM_LABEL)] + [(p["id"], p["label"]) for p in POWERUPS]
)


def powerup_label(pid: str) -> str:
    if pid == RANDOM_ID:
        return RANDOM_LABEL
    return POWERUP_BY_ID.get(pid, {"label": pid})["label"]


def powerup_desc(pid: str) -> str:
    if pid == RANDOM_ID:
        return "Zu Beginn jeder Runde wird ein Powerup ausgewuerfelt."
    return POWERUP_BY_ID.get(pid, {}).get("desc", "")


def resolve(kind: str, settings, rng=None) -> str:
    """Loest 'Zufaellig' zu einem konkreten, aktivierten Powerup auf."""
    if kind != RANDOM_ID and kind in POWERUP_BY_ID:
        return kind
    choices = settings.enabled_powerups()
    if rng is not None:
        return rng.choice(choices)
    import random as _r

    return _r.choice(choices)


# --------------------------------------------------------------------------- #
class PowerupState:
    __slots__ = ("kind", "charges", "cooldown_left", "cooldown")

    def __init__(self, kind: str, charges: int, cooldown: float = 6.0) -> None:
        self.kind = kind if kind in POWERUP_BY_ID else DEFAULT_POWERUP
        self.charges = int(charges)
        self.cooldown = float(cooldown)
        self.cooldown_left = 0.0

    def can_use(self) -> bool:
        return self.charges > 0 and self.cooldown_left <= 1e-6

    def tick(self, dt: float) -> None:
        if self.cooldown_left > 0:
            self.cooldown_left = max(0.0, self.cooldown_left - dt)


# --------------------------------------------------------------------------- #
def activate(world, curve) -> None:
    """Wird gerufen, wenn die Powerup-Taste (Flanke) gedrueckt wurde."""
    st = curve.pu
    meta = POWERUP_BY_ID.get(st.kind)
    if meta is None:
        return
    cfg = world.s.powerup_cfg(st.kind)
    if not cfg.enabled:
        world.events.append(("pu_off", curve.id, st.kind))
        return
    if not st.can_use():
        world.events.append(("pu_fail", curve.id, st.kind))
        return

    st.charges -= 1
    st.cooldown_left = cfg.cooldown
    dur = cfg.duration
    mag = cfg.strength

    kind = st.kind
    if kind == "speed":
        curve.effects.append(["speed", dur, mag])
    elif kind == "agile":
        curve.effects.append(["agile", dur, mag])
    elif kind == "thin":
        curve.effects.append(["width", dur, mag])
    elif kind == "ghost":
        curve.effects.append(["ghost", dur, 1.0])
    elif kind == "shield":
        curve.effects.append(["shield", dur, mag])
    elif kind == "square":
        _snap_square(curve)
        curve.effects.append(["square", dur, 1.0])
    elif kind == "invert":
        curve.effects.append(["invert", dur, 1.0])
    elif kind == "fog":
        curve.effects.append(["fog", dur, mag])
    elif kind == "extra_gap":
        curve.gap_left = max(curve.gap_left, mag)
    elif kind == "teleport":
        _teleport(world, curve, mag)
    elif kind == "clear":
        world.clear_trails()
    elif kind == "slow_others":
        for other in world.curves:
            if other.alive and other.id != curve.id:
                other.effects.append(["speed", dur, mag])
    elif kind == "fat_others":
        for other in world.curves:
            if other.alive and other.id != curve.id:
                other.effects.append(["width", dur, mag])
    elif kind == "reverse_others":
        for other in world.curves:
            if other.alive and other.id != curve.id:
                other.effects.append(["reverse", dur, 1.0])

    world.events.append(("pu_use", curve.id, kind))


def _snap_square(curve) -> None:
    import math

    q = math.pi / 2
    curve.heading = round(curve.heading / q) * q
    curve._sq_prev_turn = 0
    curve._sq_lock = 0.0


def _teleport(world, curve, distance: float) -> None:
    """Springt nach vorne auf die weiteste freie Stelle bis `distance`."""
    import math

    cx, sy = math.cos(curve.heading), math.sin(curve.heading)
    r = max(1.0, world.s.line_width * 0.5)
    best = 0.0
    d = 12.0
    while d <= distance:
        if not world.grid.hits(curve.x + cx * d, curve.y + sy * d, r):
            best = d
        d += 8.0
    if best <= 0:
        return
    nx, ny = curve.x + cx * best, curve.y + sy * best
    # Kein Strich zwischen Start und Ziel: als Luecken-Segment melden
    world.segments.append((curve.id, curve.x, curve.y, nx, ny, r * 2, True))
    curve.x, curve.y = nx, ny
    curve.pending.clear()
