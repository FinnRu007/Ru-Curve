"""Client-Sicht des Spiels: rendert die Snapshots des Hosts, sendet Eingaben."""

from __future__ import annotations

import pygame

from .. import theme as T
from ..colors import color_for
from ..config import GameSettings, settings_from_dict
from ..game.powerups import powerup_label
from ..ui.widgets import Button, draw_text
from .arena_render import ArenaView


class ClientGameScene:
    def __init__(self, app, client, round_start_msg: dict, cid) -> None:
        self.app = app
        self.client = client
        self.cid = cid
        self._hb = 0.0
        self._last_sent = None
        self.banner: str | None = None
        self.standings: list[dict] | None = None
        self.match_winner: dict | None = None
        self._widgets: list = []
        self._load_round(round_start_msg)

    # ------------------------------------------------------------------ #
    def _load_round(self, msg: dict) -> None:
        self.settings = settings_from_dict(msg.get("settings", {})).clamped()
        self.players = msg.get("players", [])
        self.round_no = msg.get("round_no", 1)
        self.color_map = {p["pid"]: color_for(p.get("color_index", 0)) for p in self.players}
        self.names = {p["pid"]: p.get("name", "?") for p in self.players}
        self.pu_labels = {p["pid"]: powerup_label(p.get("pu", "speed")) for p in self.players}
        self.view = ArenaView(self.settings, self.app.screen.get_size())
        self.inverted = False
        self.fog = 0.0
        self.curves = {
            p["pid"]: {"x": 0.0, "y": 0.0, "h": 0.0, "alive": True, "pu": 0, "cd": 0, "score": 0,
                       "boost": False, "square": False, "ghost": False, "shield": False}
            for p in self.players
        }
        self.my_pids = [p["pid"] for p in self.players if p.get("client_id") == self.cid]
        self.enabled_slots = [s for s in self.app.config.slots if s.enabled] or [self.app.config.slots[0]]
        self.phase = "countdown"
        self.countdown = self.settings.countdown_seconds
        self.banner = None
        self.standings = None

    def on_enter(self) -> None:
        self.app.audio.music("game")

    def on_exit(self) -> None:
        pass

    def resize(self) -> None:
        old = self.view
        self.view = ArenaView(self.settings, self.app.screen.get_size())
        try:
            pygame.transform.smoothscale(old.surf, self.view.surf.get_size(), self.view.surf)
        except (pygame.error, ValueError):
            pass
        if self._widgets:
            w, h = self.app.screen.get_size()
            self._widgets = [Button((w // 2 - 150, h - 110, 300, 46), "Verlassen", self._leave, "primary")]

    # ------------------------------------------------------------------ #
    def handle_events(self, events) -> None:
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self._leave()
                return
            for w in self._widgets:
                w.handle_event(e)

    def _leave(self) -> None:
        self.client.close()
        from .menu import MenuScene

        self.app.set_scene(MenuScene(self.app))

    # ------------------------------------------------------------------ #
    def update(self, dt: float) -> None:
        for msg in self.client.poll():
            t = msg.get("type")
            if t == "snapshot":
                self._apply_snapshot(msg)
            elif t == "round_over":
                self.view.apply_segments(msg.get("seg", []), self.color_map)
                self.standings = msg.get("standings")
                self.phase = "finished"
                if self.standings:
                    self.banner = f"{self.standings[0]['name']} gewinnt die Runde!"
            elif t == "round_start":
                self._load_round(msg)
            elif t == "match_over":
                self.match_winner = msg.get("winner")
                self.standings = msg.get("standings")
                self.phase = "match_over"
                self.app.audio.play("win")
                w, h = self.app.screen.get_size()
                self._widgets = [Button((w // 2 - 150, h - 110, 300, 46), "Verlassen", self._leave, "primary")]
            elif t == "lobby":
                from .join import ClientLobbyScene

                scene = ClientLobbyScene(self.app, self.client)
                scene._sent_hello = True
                scene.remote_players = msg.get("players", [])
                scene.settings_wire = msg.get("settings", {})
                scene.cid = self.cid
                self.app.set_scene(scene)
                return
            elif t == "__disconnect__":
                self._leave()
                return

        self._send_input()

    def _apply_snapshot(self, msg: dict) -> None:
        self.phase = msg.get("phase", self.phase)
        self.countdown = msg.get("countdown", 0.0)
        self.inverted = bool(msg.get("inv", False))
        self.fog = float(msg.get("fog", 0.0))
        for cd in msg.get("curves", []):
            slot = self.curves.get(cd["id"])
            if slot is None:
                continue
            slot.update(x=cd["x"], y=cd["y"], h=cd["h"], alive=cd["alive"],
                        pu=cd.get("pu", 0), cd=cd.get("cd", 0), score=cd.get("score", 0),
                        boost=cd.get("boost", False), square=cd.get("square", False),
                        ghost=cd.get("ghost", False), shield=cd.get("shield", False))
        self.view.apply_segments(msg.get("seg", []), self.color_map)
        for ev in msg.get("ev", []):
            if not ev:
                continue
            if ev[0] == "death":
                self.app.audio.play("crash")
                if len(ev) >= 4:
                    self.view.add_flash(ev[2], ev[3], self.color_map.get(ev[1], (255, 255, 255)))
            elif ev[0] == "shield":
                self.app.audio.play("powerup")
                if len(ev) >= 4:
                    self.view.add_flash(ev[2], ev[3], (255, 255, 255))
            elif ev[0] == "clear":
                self.view.reset()
            elif ev[0] == "pu_use":
                self.app.audio.play("powerup")
                if len(ev) >= 3 and ev[1] in self.my_pids:
                    self.view.add_toast(powerup_label(ev[2]) + "!",
                                        self.color_map.get(ev[1], (255, 255, 255)))
            elif ev[0] == "pu_fail" and len(ev) >= 2 and ev[1] in self.my_pids:
                self.view.add_toast("Powerup noch nicht bereit")
            elif ev[0] == "go":
                self.app.audio.play("go")

    def _send_input(self) -> None:
        keys = pygame.key.get_pressed()
        rows = []
        for pid, slot in zip(self.my_pids, self.enabled_slots):
            rows.append([pid, bool(keys[slot.left]), bool(keys[slot.right]), bool(keys[slot.powerup])])
        self._hb += 1
        if rows != self._last_sent or self._hb >= 8:
            self._hb = 0
            self._last_sent = [r[:] for r in rows]
            self.client.send({"type": "input", "in": rows})

    # ------------------------------------------------------------------ #
    def draw(self, surf) -> None:
        rcs = []
        for pid, c in self.curves.items():
            rcs.append({
                "id": pid, "x": c["x"], "y": c["y"], "h": c["h"], "alive": c["alive"],
                "color": self.color_map.get(pid, (200, 200, 200)),
                "name": self.names.get(pid, "?"), "score": c["score"],
                "pu": c["pu"], "cd": c["cd"], "boost": c["boost"],
                "square": c.get("square", False), "ghost": c.get("ghost", False),
                "shield": c.get("shield", False),
                "pu_label": self.pu_labels.get(pid, ""),
                "width": self.settings.line_width,
            })
        self.view.draw(surf, rcs, self.app.fonts, countdown=self.countdown,
                       round_no=self.round_no, phase=self.phase if self.phase != "match_over" else "finished",
                       banner=self.banner if self.phase in ("finished", "match_over") else None,
                       inverted=self.inverted and self.phase == "running",
                       fog=self.fog if self.phase == "running" else 0.0)

        if self.phase == "match_over" and self.match_winner:
            w, h = surf.get_size()
            veil = pygame.Surface((w, h), pygame.SRCALPHA)
            veil.fill((255, 255, 255, 225))
            surf.blit(veil, (0, 0))
            draw_text(surf, self.app.fonts.display(40), "Match beendet", T.TEXT, (w // 2, h // 2 - 120), center=True)
            draw_text(surf, self.app.fonts.display(26), f"{self.match_winner['name']} gewinnt!",
                      color_for(self.match_winner.get("color_index", 0)), (w // 2, h // 2 - 60), center=True)
            for wd in self._widgets:
                wd.draw(surf, self.app.fonts)
