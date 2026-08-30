"""GameScene: laeuft beim lokalen Spiel UND beim Host. Besitzt die World,
liest lokale Tasten + Bot-KI + (im Host-Fall) Netzwerk-Eingaben und broadcastet
Snapshots an die Clients."""

from __future__ import annotations

from dataclasses import asdict

import pygame

from .. import theme as T
from ..game import bots
from ..game.world import TICK
from ..ui.widgets import Button, draw_text
from .arena_render import ArenaView


class GameScene:
    def __init__(self, app, session) -> None:
        self.app = app
        self.session = session
        self.settings = session.settings
        self.world = session.new_round(app.screen.get_size())
        self.view = ArenaView(self.world.s, app.screen.get_size())
        self.color_map = {c.id: c.color for c in self.world.curves}
        self._acc = 0.0
        self._snap_acc = 0.0
        self.paused = False
        self._end_delay = 0.0          # kurze Sperre, damit kein Klick verschluckt wird
        self._await_click = False      # Runde vorbei -> auf Klick/Taste warten
        self._banner: str | None = None
        self._pause_widgets: list = []
        self._last_input: dict[int, tuple] = {}
        self._bot_frame = 0

        # lokale Slots -> Curve
        self.local_curves = [c for c in self.world.curves if c.is_local]
        self.bot_curves = [c for c in self.world.curves if c.is_bot]

    # ------------------------------------------------------------------ #
    def on_enter(self) -> None:
        self.app.audio.music("game")
        if self.session.host:
            self._broadcast_round_start()

    def on_exit(self) -> None:
        pass

    def resize(self) -> None:
        old = self.view
        self.view = ArenaView(self.world.s, self.app.screen.get_size())
        try:
            pygame.transform.smoothscale(old.surf, self.view.surf.get_size(), self.view.surf)
        except (pygame.error, ValueError):
            pass
        if self.paused:
            self._build_pause()

    def _broadcast_round_start(self) -> None:
        self.session.host.broadcast({
            "type": "round_start",
            "round_no": self.session.round_no,
            "players": [
                {"pid": c.id, "name": c.name, "color_index": c.color_index,
                 "client_id": c.client_id}
                for c in self.world.curves
            ],
            "settings": asdict(self.world.s),
        })

    # ------------------------------------------------------------------ #
    def handle_events(self, events) -> None:
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.paused = not self.paused
                if self.paused:
                    self._build_pause()
                continue
            if self.paused:
                for w in self._pause_widgets:
                    w.handle_event(e)
                continue
            # Runde vorbei: das Spielfeld bleibt stehen, bis jemand weiterklickt
            if self._await_click and (
                (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1)
                or (e.type == pygame.KEYDOWN and e.key in (
                    pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE))
            ):
                self._go_scoreboard()
                return

    def _build_pause(self) -> None:
        w, h = self.app.screen.get_size()
        cx = w // 2
        self._pause_widgets = [
            Button((cx - 150, h // 2 - 30, 300, 48), "Weiter", self._resume, "primary"),
            Button((cx - 150, h // 2 + 30, 300, 48), "Zum Hauptmenue", self._to_menu, "ghost"),
        ]

    def _resume(self) -> None:
        self.paused = False

    def _to_menu(self) -> None:
        from .menu import MenuScene

        self.session.shutdown()
        self.app.set_scene(MenuScene(self.app))

    # ------------------------------------------------------------------ #
    def update(self, dt: float) -> None:
        if self.paused:
            return

        self._pump_network()

        if self.world.phase in ("countdown", "running"):
            self._read_bot_input()          # einmal pro Frame reicht (spart Rechenzeit)
            self._acc += dt
            steps = 0
            while self._acc >= TICK and steps < 6:
                self._read_local_input()
                self.world.step()
                self._acc -= TICK
                steps += 1
                self._after_step()
            if self.world.phase == "finished":
                self._on_round_finished()
        elif self.world.phase == "finished" and not self._await_click:
            self._end_delay -= dt
            if self._end_delay <= 0:
                self._await_click = True

    def _after_step(self) -> None:
        seg = self.world.drain_segments()
        self.view.apply_segments(seg, self.color_map)
        events = self.world.drain_events()
        for ev in events:
            kind = ev[0]
            if kind == "death":
                self.app.audio.play("crash")
                if len(ev) >= 4:
                    c = self.world._by_id(ev[1])
                    self.view.add_flash(ev[2], ev[3], c.color if c else (255, 255, 255))
            elif kind == "shield":
                self.app.audio.play("powerup")
                if len(ev) >= 4:
                    self.view.add_flash(ev[2], ev[3], (255, 255, 255))
            elif kind == "clear":
                self.view.reset()
            elif kind == "pu_use":
                self.app.audio.play("powerup")
            elif kind == "go":
                self.app.audio.play("go")
        if self.session.host:
            self._pending_seg = getattr(self, "_pending_seg", [])
            self._pending_seg += seg
            self._pending_ev = getattr(self, "_pending_ev", [])
            self._pending_ev += [list(e) for e in events]

    def _read_local_input(self) -> None:
        keys = pygame.key.get_pressed()
        slots = self.app.config.slots
        for c in self.local_curves:
            if not c.alive or c.slot_index < 0 or c.slot_index >= len(slots):
                continue
            s = slots[c.slot_index]
            self.world.set_input(c.id, keys[s.left], keys[s.right], keys[s.powerup])

    def _read_bot_input(self) -> None:
        """Bot-Entscheidungen gestaffelt: jeder Bot denkt nur jeden n-ten Frame.

        20 Entscheidungen pro Sekunde reichen voellig (Menschen reagieren
        langsamer) und die Frames bleiben gleichmaessig belastet."""
        if self.world.phase != "running":
            return
        alive = [c for c in self.bot_curves if c.alive]
        if not alive:
            return
        stride = 3 if len(alive) > 3 else 2
        self._bot_frame += 1
        diff = self.settings.bot_difficulty
        for i, c in enumerate(alive):
            if (self._bot_frame + i) % stride:
                continue                       # behaelt die letzte Eingabe bei
            left, right, pu = bots.control_bot(self.world, c, diff)
            self.world.set_input(c.id, left, right, pu)

    # ------------------------------------------------------------------ #
    def _pump_network(self) -> None:
        host = self.session.host
        if not host:
            return
        for cid, msg in host.poll():
            mtype = msg.get("type")
            if mtype == "input":
                for row in msg.get("in", []):
                    try:
                        pid, lft, rgt, pu = row
                    except (ValueError, TypeError):
                        continue
                    self.world.set_input(int(pid), bool(lft), bool(rgt), bool(pu))
            elif mtype == "__disconnect__":
                for c in self.world.curves:
                    if c.client_id == cid and c.alive:
                        self.world._kill(c)

        # Snapshots ~30 Hz
        self._snap_acc += 1
        if self._snap_acc >= 2:
            self._snap_acc = 0
            snap = self.world.snapshot()
            snap["type"] = "snapshot"
            snap["seg"] = getattr(self, "_pending_seg", [])
            snap["ev"] = getattr(self, "_pending_ev", [])
            self._pending_seg = []
            self._pending_ev = []
            host.broadcast(snap)

    # ------------------------------------------------------------------ #
    def _on_round_finished(self) -> None:
        self._end_delay = 0.6
        winner = self.world.round_standings[0]["name"] if self.world.round_standings else "-"
        self._banner = f"{winner} gewinnt die Runde!"
        if self.session.host:
            # letzte Segmente + Rundenergebnis
            self.session.host.broadcast({
                "type": "round_over",
                "standings": self.world.round_standings,
                "seg": getattr(self, "_pending_seg", []),
            })
            self._pending_seg = []

    def _go_scoreboard(self) -> None:
        from .scoreboard import ScoreboardScene

        self.app.set_scene(ScoreboardScene(self.app, self.session))

    # ------------------------------------------------------------------ #
    def draw(self, surf) -> None:
        rcs = []
        for c in self.world.curves:
            rcs.append({
                "id": c.id, "x": c.x, "y": c.y, "h": c.heading,
                "alive": c.alive, "color": c.color, "name": c.name,
                "score": c.score, "pu": c.pu.charges, "cd": c.pu.cooldown_left,
                "boost": c.mods().speed > 1.01,
                "square": c.mods().square,
                "ghost": c.mods().ghost,
                "shield": c.mods().shield,
                "width": self.world.s.line_width * c.mods().width,
            })
        self.view.draw(
            surf, rcs, self.app.fonts,
            countdown=self.world.countdown,
            round_no=self.session.round_no,
            phase=self.world.phase,
            banner=self._banner if self.world.phase == "finished" else None,
            inverted=self.world.screen_inverted() and self.world.phase == "running",
            fog=self.world.fog_radius() if self.world.phase == "running" else 0.0,
            hint="Klicken oder Leertaste fuer den Zwischenstand" if self._await_click else None,
        )
        if self.paused:
            self._draw_pause(surf)

    def _draw_pause(self, surf) -> None:
        w, h = surf.get_size()
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((255, 255, 255, 220))
        surf.blit(veil, (0, 0))
        draw_text(surf, self.app.fonts.display(40), "Pause", T.TEXT, (w // 2, h // 2 - 110), center=True)
        for wd in self._pause_widgets:
            wd.draw(surf, self.app.fonts)
