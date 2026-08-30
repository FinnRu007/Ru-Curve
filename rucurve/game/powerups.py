"""Powerups: Metadaten + Aktivierungslogik.

Voll umgesetzt: speed, thin, ghost, slow_others.
Vorbereitet ("bald"): square, extra_gap - waehlbar, Aktivierung zeigt nur einen Hinweis.
"""

from __future__ import annotations

POWERUPS: list[dict] = [
    {
        "id": "speed",
        "label": "Speed-Schub",
        "desc": "Du wirst fuer kurze Zeit deutlich schneller.",
        "implemented": True,
    },
    {
        "id": "thin",
        "label": "Duenne Linie",
        "desc": "Deine Linie wird kurzzeitig halb so breit.",
        "implemented": True,
    },
    {
        "id": "ghost",
        "label": "Geist",
        "desc": "Du fliegst kurz durch alle Linien hindurch (ziehst keine Spur).",
        "implemented": True,
    },
    {
        "id": "slow_others",
        "label": "Gegner bremsen",
        "desc": "Alle anderen werden kurz langsamer.",
        "implemented": True,
    },
    {
        "id": "square",
        "label": "Eckig",
        "desc": "Kurze Zeit nur 90-Grad-Ecken statt runder Kurven.",
        "implemented": True,
    },
    {
        "id": "extra_gap",
        "label": "Extra-Luecke",
        "desc": "Erzeugt sofort eine grosse Luecke in deiner Spur.",
        "implemented": True,
    },
    {
        "id": "invert",
        "label": "Farben umkehren",
        "desc": "Kehrt fuer alle die Bildschirmfarben um - verwirrt die Gegner.",
        "implemented": True,
    },
]

POWERUP_BY_ID: dict[str, dict] = {p["id"]: p for p in POWERUPS}
DEFAULT_POWERUP = "speed"


def powerup_label(pid: str) -> str:
    return POWERUP_BY_ID.get(pid, {"label": pid})["label"]


class PowerupState:
    __slots__ = ("kind", "charges", "cooldown_left")

    def __init__(self, kind: str, charges: int) -> None:
        self.kind = kind if kind in POWERUP_BY_ID else DEFAULT_POWERUP
        self.charges = int(charges)
        self.cooldown_left = 0.0

    def can_use(self) -> bool:
        return self.charges > 0 and self.cooldown_left <= 1e-6

    def tick(self, dt: float) -> None:
        if self.cooldown_left > 0:
            self.cooldown_left = max(0.0, self.cooldown_left - dt)


def activate(world, curve) -> None:
    """Wird gerufen, wenn die Powerup-Taste (Flanke) gedrueckt wurde."""
    st = curve.pu
    meta = POWERUP_BY_ID.get(st.kind)
    if meta is None or not meta["implemented"]:
        world.events.append(("pu_soon", curve.id, st.kind))
        return
    if not st.can_use():
        world.events.append(("pu_fail", curve.id, st.kind))
        return

    st.charges -= 1
    st.cooldown_left = world.s.powerup_cooldown
    dur = world.s.powerup_duration

    if st.kind == "speed":
        curve.effects.append(["speed", dur, world.s.powerup_boost_factor])
    elif st.kind == "thin":
        curve.effects.append(["thin", dur, 0.5])
    elif st.kind == "ghost":
        curve.effects.append(["ghost", dur, 1.0])
    elif st.kind == "slow_others":
        for other in world.curves:
            if other.alive and other.id != curve.id:
                other.effects.append(["slow", dur, 0.55])
    elif st.kind == "square":
        import math

        q = math.pi / 2
        curve.heading = round(curve.heading / q) * q
        curve._sq_prev_turn = 0
        curve._sq_lock = 0.0
        curve.effects.append(["square", dur, 1.0])
    elif st.kind == "invert":
        curve.effects.append(["invert", dur, 1.0])
    elif st.kind == "extra_gap":
        curve.gap_left = max(world.s.gap_size * 3.0, 130.0)

    world.events.append(("pu_use", curve.id, st.kind))
