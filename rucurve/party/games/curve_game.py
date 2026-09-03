"""Achtung die Kurve als Turnier-Minispiel.

Das einzige Minispiel, bei dem der Host fuer alle rechnet: die Simulation
(rucurve.game.world.World) laeuft auf dem Host, Clients schicken nur ihre
Tasten und zeigen die Schnappschuesse an. Wiederverwendet World, ArenaView
und die Bot-KI unveraendert.
"""

from __future__ import annotations

import dataclasses
import random

import pygame

from ...colors import color_for
from ...game import bots as bot_ai
from ...game.curve import Curve
from ...game.world import TICK, World
from ...scenes.arena_render import ArenaView
from ...ui.widgets import draw_text
from .. import ui as U
from ..base import MiniGame, Result


class CurveGame(MiniGame):
    goal = ("Du ziehst eine Linie hinter dir her. Beruehre keine Linie und "
            "keinen Rand - auch nicht deine eigene. Ab und zu entsteht eine "
            "Luecke, durch die man schluepfen kann.")
    key_help = ("nach links lenken", "Powerup einsetzen", "nach rechts lenken")
    scoring_help = "nach ueberlebter Zeit. Wer zuletzt faehrt, gewinnt."
    id = "curve"
    name = "Achtung die Kurve"
    rules = "Lenke mit links und rechts, weiche allen Linien aus. Wer am laengsten lebt, gewinnt."
    input_mode = "curve"
    scoring = "high"                 # ueberlebte Sekunden
    live_unit = " s"
    authoritative = True
    intro_seconds = 6.5
    max_seconds = 95.0

    @staticmethod
    def make_config(rng, players, area=None, settings=None):
        """Die Spielfeldmasse legt der HOST fest und schickt sie mit.

        Sonst rechnet jeder Rechner sie aus seinem eigenen Fenster aus - dann
        stimmen Waende und Koordinaten nicht ueberein, und der Mitspieler
        sieht eine ganz andere Karte.
        """
        cfg = {"seed": rng.randrange(1 << 30)}
        if area is not None and settings is not None:
            aw, ah = settings.arena_dims(max(320, area.w), max(240, area.h))
            cfg["aw"], cfg["ah"] = int(aw), int(ah)
        return cfg

    # ------------------------------------------------------------------ #
    def __init__(self, ctx):
        super().__init__(ctx)
        self.settings = self._round_settings()
        self.curves: list[Curve] = []
        self.world: World | None = None
        self.view: ArenaView | None = None
        self.color_map: dict[int, tuple] = {}
        self._acc = 0.0
        self._snap = 0
        self._bot_frame = 0
        self._pending_seg: list = []
        self._death_time: dict[int, float] = {}
        self._death_order: list[int] = []      # in dieser Reihenfolge raus
        self._remote_input: dict[int, tuple] = {}
        self._last_sent = None
        self.sim_time = 0.0
        self.alive_flags: dict[int, bool] = {}
        self.render_curves: list[dict] = []
        self._phase = "countdown"

        if ctx.is_host:
            self._build_world()
        self._build_view()

    # Im Turnier soll eine Runde flott sein. Die normale Einstellung ist auf
    # ein ganzes Match ausgelegt; hier zaehlt eine einzelne Runde, und bei
    # gemuetlichem Tempo passiert zu lange nichts.
    SPEED_BOOST = 1.6

    def _round_settings(self):
        """Einstellungen fuer diese Runde.

        Die Spielfeldmasse kommen aus der Konfiguration des Hosts, wenn sie
        dort stehen. Nur wenn nichts mitgeschickt wurde (alte Fassung),
        werden sie aus dem eigenen Fenster gerechnet.
        """
        s = self.ctx.app.config.settings
        w = int(self.cfg.get("aw", 0))
        h = int(self.cfg.get("ah", 0))
        if w < 320 or h < 240:
            area = self.ctx.area
            w, h = s.arena_dims(max(320, area.w), max(240, area.h))
        # Lenkradius mitziehen: turn_rate = speed / turn_radius. Ohne das
        # waere das Auto zwar schneller, aber genauso traege zu lenken.
        return dataclasses.replace(
            s, arena_width=w, arena_height=h, countdown_seconds=0.0,
            speed=s.speed * self.SPEED_BOOST,
            turn_radius=s.turn_radius * self.SPEED_BOOST)

    def _build_world(self):
        self.curves = []
        for p in self.ctx.players:
            c = Curve(p.pid, p.name, color_for(p.color_index),
                      is_bot=p.is_bot, is_local=p.is_local,
                      slot_index=p.slot_index, client_id=p.client_id,
                      powerup_kind="random", color_index=p.color_index)
            self.curves.append(c)
        seed = int(self.cfg.get("seed", 1))
        self.world = World(self.settings, self.curves, rng=random.Random(seed))
        self.world.phase = "running"
        self.color_map = {c.id: c.color for c in self.curves}
        self.alive_flags = {c.id: True for c in self.curves}

    def _build_view(self):
        n = len(self.ctx.players)
        area = self.ctx.area
        self.view = ArenaView(self.settings, (area.w, area.h), n, hud=False)
        # ArenaView rechnet mit einem eigenen Fenster - wir zeichnen auf eine
        # Extraflaeche und blitten sie in unseren Bereich.
        self._canvas = pygame.Surface((area.w, area.h)).convert()

    def on_resize(self, area):
        old = self.view
        self._build_view()
        if old is not None and self.view is not None:
            try:
                pygame.transform.smoothscale(old.surf, self.view.surf.get_size(),
                                             self.view.surf)
            except (pygame.error, ValueError):
                pass

    # ------------------------------------------------------------------ #
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
        rows = [[pid, l, r, p] for pid, (l, r, p) in self._read_local().items()]
        if rows == self._last_sent:
            return None
        self._last_sent = [row[:] for row in rows]
        return {"in": rows}

    def apply_input(self, client_id, data):
        for row in data.get("in", []):
            try:
                pid, l, r, p = row
            except (TypeError, ValueError):
                continue
            self._remote_input[int(pid)] = (bool(l), bool(r), bool(p))

    # ------------------------------------------------------------------ #
    def update(self, dt):
        self.elapsed += dt
        if self.finished:
            return
        if not self.ctx.is_host:
            if self.elapsed >= self.max_seconds:
                self.finish()
            return

        w = self.world
        if w is None:
            self.finish()
            return

        self._bot_frame += 1
        self._drive_bots()
        for pid, (l, r, p) in self._read_local().items():
            w.set_input(pid, l, r, p)
        for pid, (l, r, p) in self._remote_input.items():
            w.set_input(pid, l, r, p)

        self._acc += dt
        steps = 0
        while self._acc >= TICK and steps < 6:
            w.step()
            self._acc -= TICK
            steps += 1
            self.sim_time = w.time
            self._collect()
        if w.phase == "finished" or self.elapsed >= self.max_seconds:
            self.finish()

    def _drive_bots(self):
        w = self.world
        alive_bots = [c for c in self.curves if c.is_bot and c.alive]
        if not alive_bots:
            return
        stride = 3 if len(alive_bots) > 3 else 2
        diff = self.settings.bot_difficulty
        for i, c in enumerate(alive_bots):
            if (self._bot_frame + i) % stride:
                continue
            l, r, p = bot_ai.control_bot(w, c, diff)
            w.set_input(c.id, l, r, p)

    def _collect(self):
        w = self.world
        seg = w.drain_segments()
        self._pending_seg += seg
        if self.view:
            self.view.apply_segments(seg, self.color_map)
        for ev in w.drain_events():
            if ev[0] == "death":
                if ev[1] not in self._death_time:
                    self._death_order.append(ev[1])
                self._death_time.setdefault(ev[1], w.time)
                self.alive_flags[ev[1]] = False
                self.ctx.play("crash")
                if len(ev) >= 4 and self.view:
                    c = w._by_id(ev[1])
                    self.view.add_flash(ev[2], ev[3], c.color if c else (255, 255, 255))
            elif ev[0] == "pu_use":
                self.ctx.play("powerup")
            elif ev[0] == "clear" and self.view:
                self.view.reset()

    # ------------------------------------------------------------------ #
    def net_state(self):
        w = self.world
        if w is None:
            return None
        self._snap += 1
        snap = {
            "t": round(w.time, 2),
            "phase": w.phase,
            "inv": w.screen_inverted(),
            "fog": round(w.fog_radius(), 1),
            "seg": self._pending_seg,
            "c": [[c.id, round(c.x, 1), round(c.y, 1), round(c.heading, 3),
                   1 if c.alive else 0, c.pu.charges,
                   1 if c.mods().ghost else 0, 1 if c.mods().shield else 0]
                  for c in self.curves],
        }
        self._pending_seg = []
        return snap

    def apply_state(self, d):
        self.sim_time = float(d.get("t", self.sim_time))
        self._phase = d.get("phase", "running")
        self._inv = bool(d.get("inv", False))
        self._fog = float(d.get("fog", 0.0))
        if self.view:
            self.view.apply_segments(
                [(r[0], r[1], r[2], r[3], r[4], r[5], bool(r[6]))
                 for r in d.get("seg", [])],
                self.color_map or {p.pid: p.color for p in self.ctx.players})
        rows = []
        for c in d.get("c", []):
            pid = c[0]
            self.alive_flags[pid] = bool(c[4])
            if not c[4]:
                self._death_time.setdefault(pid, self.sim_time)
            rows.append({"id": pid, "x": c[1], "y": c[2], "h": c[3],
                         "alive": bool(c[4]), "pu": c[5],
                         "ghost": bool(c[6]), "shield": bool(c[7])})
        self._client_rows = rows
        if self._phase == "finished":
            self.finish()

    # ------------------------------------------------------------------ #
    def finish(self):
        if self.ctx.is_host and self.world is not None:
            end = self.world.time
            # Der Ueberlebende und der zuletzt Ausgeschiedene haben denselben
            # Zeitwert - die Runde endet ja in dem Moment, in dem der vorletzte
            # stirbt. Ohne zweiten Massstab bekamen Platz 1 und 2 immer gleich
            # viele Punkte. Die Reihenfolge des Ausscheidens entscheidet:
            # wer spaeter raus ist (oder ueberlebt), steht vorn.
            order = list(self._death_order)
            for c in self.curves:
                surv = self._death_time.get(c.id, end)
                if c.id in order:
                    rank = len(order) - order.index(c.id)      # frueh raus = gross
                else:
                    rank = 0                                    # ueberlebt
                self.results_map[c.id] = Result(
                    raw=round(surv, 3), time=float(rank),
                    detail="%.1f s" % surv, done=True)
        super().finish()

    def host_results(self):
        return self.results_map

    def live_rows(self):
        return {pid: round(self._death_time.get(pid, self.sim_time), 1)
                for pid in self.alive_flags}

    # ------------------------------------------------------------------ #
    def _render_rows(self):
        if self.ctx.is_host and self.world is not None:
            out = []
            for c in self.curves:
                m = c.mods()
                out.append({"id": c.id, "x": c.x, "y": c.y, "h": c.heading,
                            "alive": c.alive, "color": c.color, "name": c.name,
                            "score": int(self._death_time.get(c.id, self.sim_time)),
                            "pu": c.pu.charges, "cd": c.pu.cooldown_left,
                            "boost": m.speed > 1.01, "square": m.square,
                            "ghost": m.ghost, "shield": m.shield,
                            "pu_label": "", "width": self.settings.line_width * m.width})
            return out
        rows = []
        for r in getattr(self, "_client_rows", []):
            p = self.ctx.player(r["id"])
            rows.append({**r, "color": p.color if p else (200, 200, 200),
                         "name": p.name if p else "?",
                         "score": int(self._death_time.get(r["id"], self.sim_time)),
                         "cd": 0, "boost": False, "square": False,
                         "pu_label": "", "width": self.settings.line_width})
        return rows

    def draw(self, surf):
        if self.view is None:
            return
        area = self.ctx.area
        self._canvas.fill(U.BG)
        self.view.draw(self._canvas, self._render_rows(), self.ctx.fonts,
                       countdown=0.0, round_no=1, phase="running",
                       inverted=getattr(self, "_inv", False) if not self.ctx.is_host
                       else (self.world.screen_inverted() if self.world else False),
                       fog=getattr(self, "_fog", 0.0) if not self.ctx.is_host
                       else (self.world.fog_radius() if self.world else 0.0),
                       bg=U.BG)
        surf.blit(self._canvas, area.topleft)
        draw_text(surf, self.ctx.fonts.display(22), "%.1f s" % self.sim_time,
                  U.TEXT, (area.x + 12, area.y + 6))
