"""Grundlage fuer Echtzeit-Minispiele in einer Arena.

Achtung die Kurve und das Ru-Rennen haben gezeigt, wo der Spass herkommt:
alle sind gleichzeitig unterwegs und kommen sich gegenseitig in die Quere.
Genau das soll nicht jedes Mal neu gebaut werden - hier steckt alles, was
solche Spiele gemeinsam haben:

  * **Bewegung mit drei Tasten.** Wie ueberall im Spiel: links/rechts dreht,
    die Aktionstaste gibt einen kurzen Schub (Vorrat, der sich auffuellt).
    Man faehrt immer vorwaerts - das ist leicht zu lernen und macht die
    Steuerung in jedem Arenaspiel gleich.
  * **Zusammenstoesse.** Spieler schieben sich auseinander; wie stark das
    weh tut, entscheidet das jeweilige Spiel ueber `on_contact`.
  * **Netzwerk.** Der Host rechnet, die Clients zeigen an und schicken nur
    ihre Tasten. Unterklassen sagen ueber `player_wire`/`world_wire`, was
    zusaetzlich uebertragen werden muss.
  * **Bots.** Die Unterklasse nennt nur ein Ziel (`bot_target`), das Lenken
    dorthin macht die Basis.

Gerechnet wird in einem festen Logikraum (LOGIC_W x LOGIC_H) und erst beim
Zeichnen skaliert - so sehen alle Rechner dasselbe, unabhaengig von der
Fenstergroesse.
"""

from __future__ import annotations

import math
import random

import pygame

from ..ui.widgets import draw_text
from . import ui as U
from .base import MiniGame, Result

LOGIC_W, LOGIC_H = 1600.0, 900.0
TICK = 1.0 / 60.0


class ArenaGame(MiniGame):
    authoritative = True
    input_mode = "keys"
    intro_seconds = 6.5

    # -- Fahrverhalten (Unterklassen duerfen alles davon aendern) -------
    RADIUS = 26.0             # Spielerradius im Logikraum
    SPEED = 300.0             # Grundtempo
    TURN_RATE = 3.6           # rad/s
    DASH_FACTOR = 1.9         # Tempo waehrend des Schubs
    DASH_TIME = 0.45          # wie lange ein Schub haelt
    DASH_REFILL = 0.35        # Vorrat pro Sekunde
    DASH_MAX = 1.2            # Vorrat in Sekunden
    WALLS = "bounce"          # "bounce" | "wrap" | "none"
    BOUNCE_KEEP = 0.85        # Tempoanteil nach einem Wandstoss

    @staticmethod
    def make_config(rng, players, area=None, settings=None):
        return {"seed": rng.randrange(1 << 30)}

    # ------------------------------------------------------------------ #
    def __init__(self, ctx):
        super().__init__(ctx)
        self.seed = int(self.cfg.get("seed", 1))
        self.rng = random.Random(self.seed)
        self.sim_time = 0.0
        self.units: dict[int, dict] = {}
        self._acc = 0.0
        self._remote_input: dict[int, tuple] = {}
        self._last_sent = None
        self._scale = 1.0
        self._off = (0.0, 0.0)
        self._spawn_all()
        self.setup()
        self._layout(ctx.area)

    # -- Von Unterklassen zu fuellen ------------------------------------
    def setup(self) -> None:
        """Nach dem Aufstellen der Spieler: Welt vorbereiten."""

    def step_world(self, dt: float) -> None:
        """Alles, was nicht Bewegung ist (Sammelzeug, Ring, Rollen ...)."""

    def on_contact(self, a: dict, b: dict, closing: float) -> None:
        """Zwei Spieler beruehren sich. `closing` = Annaeherungstempo."""

    def bot_target(self, unit: dict):
        """(x, y), wohin dieser Bot will - oder None fuer geradeaus."""
        return None

    def draw_world(self, surf) -> None:
        """Hintergrund/Spielobjekte, bevor die Spieler gezeichnet werden."""

    def player_wire(self, unit: dict) -> list:
        """Zusatzwerte je Spieler fuer das Netz (Zahlen)."""
        return []

    def apply_player_wire(self, unit: dict, extra: list) -> None:
        """Zusatzwerte je Spieler uebernehmen."""

    def world_wire(self) -> dict:
        """Zustand der Welt fuer das Netz."""
        return {}

    def apply_world_wire(self, data: dict) -> None:
        """Zustand der Welt uebernehmen."""

    # -- Aufstellung ----------------------------------------------------
    def spawn_pose(self, index: int, total: int):
        """Standard: gleichmaessig im Kreis, Blick zur Mitte."""
        cx, cy = LOGIC_W / 2, LOGIC_H / 2
        r = min(LOGIC_W, LOGIC_H) * 0.32
        a = -math.pi / 2 + index / max(1, total) * math.tau
        return cx + math.cos(a) * r, cy + math.sin(a) * r, a + math.pi

    def _spawn_all(self):
        total = len(self.ctx.players)
        for i, p in enumerate(self.ctx.players):
            x, y, head = self.spawn_pose(i, total)
            self.units[p.pid] = {
                "pid": p.pid, "x": x, "y": y, "h": head, "v": self.SPEED,
                "dash": self.DASH_MAX, "dash_left": 0.0, "alive": True,
                "hit": 0.0, "score": 0.0, "slow": 1.0,
                "knock": 0.0, "kh": 0.0, "kv": 0.0,
                "skill": 0.55 + 0.45 * max(0.0, min(1.0, p.difficulty))
                if p.is_bot else 1.0,
            }

    # -- Eingaben -------------------------------------------------------
    def handle_events(self, events):
        pass                       # Tasten werden pro Tick abgefragt

    def _read_local(self):
        keys = pygame.key.get_pressed()
        out = {}
        for pid in self.ctx.local_pids:
            b = self.ctx.bindings.get(pid)
            if not b:
                continue
            out[pid] = (bool(keys[b[0]]), bool(keys[b[2]]), bool(keys[b[1]]))
        return out

    def net_input(self):
        rows = [[pid, l, r, a] for pid, (l, r, a) in self._read_local().items()]
        if rows == self._last_sent:
            return None
        self._last_sent = [row[:] for row in rows]
        return {"in": rows}

    def apply_input(self, client_id, data):
        for row in data.get("in", []):
            try:
                pid, l, r, a = row
            except (TypeError, ValueError):
                continue
            self._remote_input[int(pid)] = (bool(l), bool(r), bool(a))

    # -- Simulation -----------------------------------------------------
    def update(self, dt):
        self.elapsed += dt
        if self.finished:
            return
        if not self.ctx.is_host:
            if self.elapsed >= self.max_seconds:
                self.finish()
            return

        inputs = dict(self._remote_input)
        inputs.update(self._read_local())
        self._acc += dt
        steps = 0
        while self._acc >= TICK and steps < 6:
            self._step(TICK, inputs)
            self._acc -= TICK
            steps += 1
        if self.elapsed >= self.max_seconds:
            self.finish()

    def _step(self, dt, inputs):
        self.sim_time += dt
        for pid, u in self.units.items():
            if not u["alive"]:
                continue
            p = self.ctx.player(pid)
            if p is not None and p.is_bot:
                l, r, a = self._bot_input(u)
            else:
                l, r, a = inputs.get(pid, (False, False, False))
            self._drive(u, dt, l, r, a)
            self._move(u, dt)
        self._collide()
        self.step_world(dt)

    def _drive(self, u, dt, left, right, action):
        if action and u["dash_left"] <= 0.0 and u["dash"] >= self.DASH_TIME:
            u["dash_left"] = self.DASH_TIME
            u["dash"] -= self.DASH_TIME
            self._on_dash(u)
        if u["dash_left"] > 0.0:
            u["dash_left"] = max(0.0, u["dash_left"] - dt)
        else:
            u["dash"] = min(self.DASH_MAX, u["dash"] + self.DASH_REFILL * dt)

        boost = self.DASH_FACTOR if u["dash_left"] > 0.0 else 1.0
        want = self.SPEED * boost * u.get("skill", 1.0) * u.get("slow", 1.0)
        # sanft nachziehen, damit ein Stoss kurz nachwirkt
        u["v"] += (want - u["v"]) * min(1.0, dt * 6.0)
        turn = (1 if right else 0) - (1 if left else 0)
        u["h"] += turn * self.TURN_RATE * dt
        u["hit"] = max(0.0, u["hit"] - dt)

    def _on_dash(self, u) -> None:
        """Haken fuer Unterklassen (Ton, Effekt)."""

    def knockback(self, u, heading: float, speed: float, seconds: float = 0.5):
        """Stoss, der eine Weile nachwirkt - unabhaengig von der Lenkung.

        Ohne das waere jeder Rempler sofort wieder ausgeglichen, weil die
        Fahrt ja stur nach vorn geht.
        """
        u["knock"] = max(u["knock"], seconds)
        u["kh"] = heading
        u["kv"] = max(u["kv"], speed)
        u["hit"] = 0.3

    def _move(self, u, dt):
        if u["knock"] > 0.0:
            u["knock"] = max(0.0, u["knock"] - dt)
            u["x"] += math.cos(u["kh"]) * u["kv"] * dt
            u["y"] += math.sin(u["kh"]) * u["kv"] * dt
            u["kv"] *= 0.93
        u["x"] += math.cos(u["h"]) * u["v"] * dt
        u["y"] += math.sin(u["h"]) * u["v"] * dt
        if self.WALLS == "wrap":
            u["x"] %= LOGIC_W
            u["y"] %= LOGIC_H
        elif self.WALLS == "bounce":
            r = self.RADIUS
            if u["x"] < r or u["x"] > LOGIC_W - r:
                u["x"] = max(r, min(LOGIC_W - r, u["x"]))
                u["h"] = math.pi - u["h"]
                u["v"] *= self.BOUNCE_KEEP
            if u["y"] < r or u["y"] > LOGIC_H - r:
                u["y"] = max(r, min(LOGIC_H - r, u["y"]))
                u["h"] = -u["h"]
                u["v"] *= self.BOUNCE_KEEP

    def _collide(self):
        pids = [pid for pid, u in self.units.items() if u["alive"]]
        for i in range(len(pids)):
            a = self.units[pids[i]]
            for j in range(i + 1, len(pids)):
                b = self.units[pids[j]]
                dx, dy = b["x"] - a["x"], b["y"] - a["y"]
                d = math.hypot(dx, dy)
                if d >= self.RADIUS * 2 or d < 1e-6:
                    continue
                ux, uy = dx / d, dy / d
                push = (self.RADIUS * 2 - d) / 2.0
                a["x"] -= ux * push
                a["y"] -= uy * push
                b["x"] += ux * push
                b["y"] += uy * push
                avx, avy = math.cos(a["h"]) * a["v"], math.sin(a["h"]) * a["v"]
                bvx, bvy = math.cos(b["h"]) * b["v"], math.sin(b["h"]) * b["v"]
                closing = (avx - bvx) * ux + (avy - bvy) * uy
                self.on_contact(a, b, closing)

    # -- Bots -----------------------------------------------------------
    def _bot_input(self, u):
        target = self.bot_target(u)
        if target is None:
            return False, False, False
        tx, ty, dash = target if len(target) == 3 else (target[0], target[1], False)
        diff = (math.atan2(ty - u["y"], tx - u["x"]) - u["h"] + math.pi) % math.tau
        diff -= math.pi
        dead = 0.10 + 0.25 * (1.0 - u.get("skill", 1.0))
        return diff < -dead, diff > dead, bool(dash)

    def push_away_target(self, u, ox, oy):
        """Hilfe fuer Bots: Punkt, der von (ox, oy) wegzeigt."""
        dx, dy = u["x"] - ox, u["y"] - oy
        d = math.hypot(dx, dy) or 1.0
        return u["x"] + dx / d * 400.0, u["y"] + dy / d * 400.0

    # -- Netzwerk -------------------------------------------------------
    def net_state(self):
        return {
            "t": round(self.sim_time, 2),
            "u": [[pid, round(u["x"], 1), round(u["y"], 1), round(u["h"], 3),
                   round(u["v"], 1), 1 if u["alive"] else 0,
                   round(u["dash"], 2), round(u["dash_left"], 2),
                   round(u["score"], 2), self.player_wire(u)]
                  for pid, u in self.units.items()],
            "w": self.world_wire(),
        }

    def apply_state(self, d):
        self.sim_time = float(d.get("t", self.sim_time))
        for row in d.get("u", []):
            u = self.units.get(int(row[0]))
            if u is None:
                continue
            u["x"], u["y"], u["h"], u["v"] = row[1], row[2], row[3], row[4]
            u["alive"] = bool(row[5])
            u["dash"], u["dash_left"] = row[6], row[7]
            u["score"] = row[8]
            if len(row) > 9:
                self.apply_player_wire(u, row[9] or [])
        self.apply_world_wire(d.get("w") or {})

    # -- Ergebnis (Standard: Punktestand des Spiels) --------------------
    scoring = "high"

    def score_detail(self, u) -> str:
        return "%d" % round(u["score"])

    def finish(self):
        if self.ctx.is_host:
            for pid, u in self.units.items():
                self.results_map[pid] = Result(
                    raw=round(u["score"], 3), time=0.0,
                    detail=self.score_detail(u), done=True)
        super().finish()

    def host_results(self):
        return self.results_map

    def live_rows(self):
        return {pid: round(u["score"], 2) for pid, u in self.units.items()}

    def alive_units(self) -> list:
        return [u for u in self.units.values() if u["alive"]]

    def nearest_other(self, u, only_alive=True):
        best, best_d = None, 1e18
        for other in self.units.values():
            if other is u or (only_alive and not other["alive"]):
                continue
            d = (other["x"] - u["x"]) ** 2 + (other["y"] - u["y"]) ** 2
            if d < best_d:
                best_d, best = d, other
        return best

    # -- Anzeige --------------------------------------------------------
    def _layout(self, area):
        self._scale = min(area.w / LOGIC_W, area.h / LOGIC_H)
        vw, vh = LOGIC_W * self._scale, LOGIC_H * self._scale
        self._off = (area.x + (area.w - vw) / 2, area.y + (area.h - vh) / 2)

    def on_resize(self, area):
        self._layout(area)

    def to_screen(self, x, y):
        return (self._off[0] + x * self._scale, self._off[1] + y * self._scale)

    def px(self, v):
        return max(1, int(v * self._scale))

    @property
    def view_rect(self) -> pygame.Rect:
        return pygame.Rect(int(self._off[0]), int(self._off[1]),
                           int(LOGIC_W * self._scale), int(LOGIC_H * self._scale))

    def draw(self, surf):
        area = self.ctx.area
        surf.fill(U.BG, area)
        self.draw_world(surf)
        for pid, u in self.units.items():
            if u["alive"]:
                self.draw_unit(surf, u)
        self.draw_hud(surf, area)

    def unit_color(self, u):
        p = self.ctx.player(u["pid"])
        return p.color if p else (210, 210, 210)

    def unit_name(self, u):
        p = self.ctx.player(u["pid"])
        return p.name if p else "?"

    def draw_unit(self, surf, u, radius=None, ring=None):
        x, y = self.to_screen(u["x"], u["y"])
        r = self.px(radius if radius is not None else self.RADIUS)
        col = self.unit_color(u)
        if u["dash_left"] > 0.0:                     # Schubschweif
            tx, ty = self.to_screen(u["x"] - math.cos(u["h"]) * self.RADIUS * 1.6,
                                    u["y"] - math.sin(u["h"]) * self.RADIUS * 1.6)
            pygame.draw.line(surf, (255, 210, 120), (tx, ty), (x, y), max(2, r // 3))
        pygame.draw.circle(surf, col, (int(x), int(y)), r)
        pygame.draw.circle(surf, (12, 14, 22), (int(x), int(y)), r, max(1, r // 8))
        # Blickrichtung
        nx = x + math.cos(u["h"]) * r * 0.75
        ny = y + math.sin(u["h"]) * r * 0.75
        pygame.draw.circle(surf, (14, 16, 26), (int(nx), int(ny)), max(2, r // 4))
        if ring:
            pygame.draw.circle(surf, ring, (int(x), int(y)), r + max(3, r // 3), 3)
        if u["hit"] > 0:
            pygame.draw.circle(surf, (255, 255, 255), (int(x), int(y)), r + 5, 2)
        img = self.ctx.fonts.body_bold(12).render(self.unit_name(u), True, U.TEXT)
        surf.blit(img, img.get_rect(midbottom=(x, y - r - 4)))

    # -- Standard-HUD: Rangliste links, eigene Karten unten -------------
    HUD_TITLE = "Stand"

    def hud_rows(self):
        """[(pid, Textwert)] fuer die kleine Liste oben links."""
        rows = sorted(self.units.values(), key=lambda u: -u["score"])
        return [(u["pid"], "%d" % round(u["score"])) for u in rows]

    def hud_own(self, u) -> str:
        return ""

    def draw_hud(self, surf, area):
        fonts = self.ctx.fonts
        rows = self.hud_rows()
        if rows:
            box = pygame.Rect(area.x + 8, area.y + 6, 210,
                              30 + 22 * min(8, len(rows)))
            U.panel(surf, box, color=U.PANEL, border=U.LINE, radius=12, alpha=215)
            draw_text(surf, fonts.body_bold(13), self.HUD_TITLE, U.MUTED,
                      (box.x + 12, box.y + 7))
            y = box.y + 28
            for i, (pid, value) in enumerate(rows[:8]):
                p = self.ctx.player(pid)
                col = U.PLACE_COLORS[i] if i < 3 else U.TEXT
                pygame.draw.rect(surf, p.color if p else U.MUTED,
                                 (box.x + 10, y + 5, 6, 10), border_radius=2)
                draw_text(surf, fonts.body_bold(13), "%d." % (i + 1), col,
                          (box.x + 22, y))
                draw_text(surf, fonts.body(13),
                          U.fit(fonts.body(13), p.name if p else "?", 100), U.TEXT,
                          (box.x + 44, y))
                draw_text(surf, fonts.body_bold(12), value, U.TEXT,
                          (box.right - 46, y + 1))
                y += 22

        locals_ = [p for p in self.ctx.local_players if p.pid in self.units]
        if not locals_:
            return
        n = len(locals_)
        cw = min(190, max(120, (area.w - 12 * (n - 1)) // n))
        x = area.centerx - (cw * n + 10 * (n - 1)) // 2
        y = area.bottom - 60
        for p in locals_:
            u = self.units[p.pid]
            r = pygame.Rect(x, y, cw, 48)
            U.panel(surf, r, color=U.PANEL,
                    border=p.color if u["alive"] else U.BAD, radius=12, alpha=225)
            draw_text(surf, fonts.body_bold(13),
                      U.fit(fonts.body_bold(13), p.name, cw - 60), U.TEXT,
                      (r.x + 10, r.y + 4))
            note = self.hud_own(u) or ("draussen" if not u["alive"] else "")
            draw_text(surf, fonts.body(12), note, U.MUTED, (r.x + 10, r.y + 29))
            # Schubvorrat
            U.timer_bar(surf, (r.x + 10, r.y + 23, cw - 20, 4),
                        u["dash"] / self.DASH_MAX,
                        color=U.GOLD if u["dash"] >= self.DASH_TIME else U.LINE)
            x += cw + 10

    def draw_key_help(self, surf, area, action_label):
        """Kurze Erinnerung, was die Aktionstaste hier tut."""
        img = self.ctx.fonts.body(13).render(
            "links/rechts lenken   -   Aktionstaste: %s" % action_label,
            True, U.MUTED)
        surf.blit(img, img.get_rect(midtop=(area.centerx, area.y + 6)))
