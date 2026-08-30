"""Lobby fuer 'An einem PC spielen' (local) und 'Uber LAN hosten' (host)."""

from __future__ import annotations

import socket
from dataclasses import asdict

import pygame

from .. import theme as T
from ..colors import PLAYER_COLORS, color_for
from ..config import DEFAULT_GAME_PORT
from ..game.powerups import POWERUPS, powerup_label
from ..net.discovery import Beacon, local_ip
from ..net.host import GameHost
from ..session import GameSession, PlayerDef
from ..ui.widgets import Button, Dropdown, TextInput, draw_text
from .common import BaseMenuScene

_PU_OPTIONS = [(p["id"], p["label"]) for p in POWERUPS]


class LobbyScene(BaseMenuScene):
    def __init__(self, app, mode: str = "local") -> None:
        super().__init__(app)
        self.mode = mode
        self.title = "Lobby - lokal" if mode == "local" else "Lobby - LAN-Host"
        self.players: list[PlayerDef] = []
        self.host: GameHost | None = None
        self.beacon: Beacon | None = None
        self.session: GameSession | None = None
        self._adopted = False
        self._next_pid = 0
        self._client_players: dict[int, list[int]] = {}   # cid -> [pid,...]
        self._dropdowns: list[Dropdown] = []

    # ------------------------------------------------------------------ #
    def adopt(self, session: GameSession) -> None:
        self.session = session
        self.host = session.host
        self.beacon = session.beacon
        self.players = session.players
        self._adopted = True
        self._next_pid = max((p.pid for p in self.players), default=-1) + 1
        for p in self.players:
            if p.client_id >= 0:
                self._client_players.setdefault(p.client_id, []).append(p.pid)

    def on_enter(self) -> None:
        self.app.audio.music("menu")
        if not self._adopted:
            self._init_players()
            if self.mode == "host":
                self.host = GameHost(DEFAULT_GAME_PORT)
                try:
                    self.host.start()
                except OSError as exc:
                    print(f"[lobby] Host-Start fehlgeschlagen: {exc}")
                    self.host = None
                if self.host:
                    self.beacon = Beacon(self._beacon_info)
                    self.beacon.start()
        self.build()

    def on_exit(self) -> None:
        pass

    # ------------------------------------------------------------------ #
    def _init_players(self) -> None:
        self.players = []
        pid = 0
        used_colors: set[int] = set()
        for i, slot in enumerate(self.app.config.slots):
            if slot.enabled:
                self.players.append(PlayerDef(pid, slot.name, slot.color_index, slot.powerup_kind,
                                              is_local=True, slot_index=i))
                used_colors.add(slot.color_index)
                pid += 1
        for b in range(self.app.config.settings.bot_count):
            ci = self._free_color(used_colors)
            used_colors.add(ci)
            self.players.append(PlayerDef(pid, f"Bot {b + 1}", ci, "speed", is_bot=True,
                                          difficulty=self.app.config.settings.bot_difficulty))
            pid += 1
        self._next_pid = pid

    @staticmethod
    def _free_color(used: set[int]) -> int:
        for i in range(len(PLAYER_COLORS)):
            if i not in used:
                return i
        return len(used) % len(PLAYER_COLORS)

    def _beacon_info(self) -> dict:
        return {
            "name": f"{socket.gethostname()}",
            "port": DEFAULT_GAME_PORT,
            "players": len(self.players),
            "max": 12,
        }

    # ------------------------------------------------------------------ #
    def build(self) -> None:
        w, h = self.size
        self.widgets = []
        self._dropdowns = []
        area_x = 48
        y = 150
        row_h = 58
        for p in self.players:
            self._build_row(area_x, y, w, p)
            y += row_h

        by = h - 150
        self.widgets.append(Button((area_x, by, 150, 42), "+ Spieler", self._add_local, "ghost"))
        self.widgets.append(Button((area_x + 162, by, 120, 42), "+ Bot", self._add_bot, "ghost"))
        self.widgets.append(Button((area_x + 294, by, 150, 42), "Einstellungen", self._settings, "ghost"))
        self.widgets.append(Button((area_x + 456, by, 130, 42), "Steuerung", self._controls, "ghost"))

        self.widgets.append(Button((w - 220, h - 78, 172, 50), "Start", self._start, "primary"))
        self.widgets.append(Button((w - 220, by, 172, 40), "Zurueck", self._back, "ghost"))

    def _build_row(self, x, y, w, p: PlayerDef) -> None:
        self.widgets.append(_Swatch((x, y, 34, 34), p, self))
        editable = not (p.client_id >= 0)
        if editable:
            ti = TextInput((x + 46, y, 190, 34), p.name,
                           lambda t, pl=p: self._rename(pl, t), max_len=14)
            self.widgets.append(ti)
        else:
            self.widgets.append(_Static((x + 46, y + 6, 190, 24), p.name + "  (LAN)"))

        dd = Dropdown((x + 250, y, 200, 34), _PU_OPTIONS, p.powerup_kind,
                      lambda v, pl=p: self._set_powerup(pl, v))
        dd.enabled = editable or p.is_bot
        self.widgets.append(dd)
        self._dropdowns.append(dd)

        tag = "Bot" if p.is_bot else ("LAN" if p.client_id >= 0 else "Tastatur")
        self.widgets.append(_Static((x + 466, y + 6, 90, 24), tag))

        if p.is_local:
            slot = self.app.config.slots[p.slot_index]
            from ..ui.widgets import key_name

            keys = f"{key_name(slot.left)} / {key_name(slot.right)}  +  {key_name(slot.powerup)}"
            self.widgets.append(_Static((x + 560, y + 6, 260, 24), keys, color=T.TEXT_MUTED))

        if p.is_bot or p.client_id >= 0 or self._local_count() > 1:
            self.widgets.append(Button((x + 820, y, 34, 34), "x", lambda pl=p: self._remove(pl), "ghost"))

    # ------------------------------------------------------------------ #
    def _local_count(self) -> int:
        return sum(1 for p in self.players if p.is_local)

    def _rename(self, p: PlayerDef, t: str) -> None:
        p.name = t
        if p.is_local and 0 <= p.slot_index < len(self.app.config.slots):
            self.app.config.slots[p.slot_index].name = t

    def _set_powerup(self, p: PlayerDef, v: str) -> None:
        p.powerup_kind = v
        if p.is_local and 0 <= p.slot_index < len(self.app.config.slots):
            self.app.config.slots[p.slot_index].powerup_kind = v
        self._broadcast_lobby()

    def _add_local(self) -> None:
        for i, slot in enumerate(self.app.config.slots):
            if not slot.enabled:
                slot.enabled = True
                used = {p.color_index for p in self.players}
                self.players.append(PlayerDef(self._next_pid, slot.name, slot.color_index,
                                              slot.powerup_kind, is_local=True, slot_index=i))
                self._next_pid += 1
                self.build()
                self._broadcast_lobby()
                return

    def _add_bot(self) -> None:
        used = {p.color_index for p in self.players}
        ci = self._free_color(used)
        n = sum(1 for p in self.players if p.is_bot) + 1
        self.players.append(PlayerDef(self._next_pid, f"Bot {n}", ci, "speed", is_bot=True,
                                      difficulty=self.app.config.settings.bot_difficulty))
        self._next_pid += 1
        self.build()
        self._broadcast_lobby()

    def _remove(self, p: PlayerDef) -> None:
        if p.is_local and 0 <= p.slot_index < len(self.app.config.slots):
            self.app.config.slots[p.slot_index].enabled = False
        self.players = [q for q in self.players if q is not p]
        for cid, pids in self._client_players.items():
            if p.pid in pids:
                pids.remove(p.pid)
        self.build()
        self._broadcast_lobby()

    def _settings(self) -> None:
        from .settings_scene import SettingsScene

        self.app.config.save()
        self.app.set_scene(SettingsScene(self.app, back=lambda: self._return_self()))

    def _controls(self) -> None:
        from .controls import ControlsScene

        self.app.set_scene(ControlsScene(self.app, back=lambda: self._return_self()))

    def _return_self(self):
        scene = LobbyScene(self.app, mode=self.mode)
        if self.host or self.session:
            sess = self.session or GameSession(self.app.config.settings, self.players,
                                               host=self.host, beacon=self.beacon)
            sess.players = self.players
            scene.adopt(sess)
        return scene

    def _back(self) -> None:
        from .menu import MenuScene

        if self.beacon:
            self.beacon.stop()
        if self.host:
            self.host.stop()
        for slot in self.app.config.slots:
            pass
        self.app.config.save()
        self.app.set_scene(MenuScene(self.app))

    def _start(self) -> None:
        if len(self.players) < 1:
            return
        for i, p in enumerate(self.players):
            p.pid = i
        self.app.config.save()
        session = GameSession(self.app.config.settings, self.players, host=self.host, beacon=self.beacon)
        session.players = self.players
        self.session = session
        from .game import GameScene

        self.app.audio.play("click")
        self.app.set_scene(GameScene(self.app, session))

    # ------------------------------------------------------------------ #
    #  Netzwerk (Host)
    # ------------------------------------------------------------------ #
    def _broadcast_lobby(self) -> None:
        if not self.host:
            return
        self.host.broadcast({
            "type": "lobby",
            "players": [p.to_wire() for p in self.players],
            "settings": asdict(self.app.config.settings),
            "host": socket.gethostname(),
        })

    def _pump_host(self) -> None:
        if not self.host:
            return
        dirty = False
        for cid, msg in self.host.poll():
            mtype = msg.get("type")
            if mtype == "__connect__":
                self.host.send(cid, {"type": "welcome", "cid": cid})
                self.host.send(cid, {
                    "type": "lobby",
                    "players": [p.to_wire() for p in self.players],
                    "settings": asdict(self.app.config.settings),
                    "host": socket.gethostname(),
                })
            elif mtype == "hello":
                self._client_players.setdefault(cid, [])
                used = {p.color_index for p in self.players}
                for entry in msg.get("players", [])[:6]:
                    ci = entry.get("color_index", 0)
                    if ci in used:
                        ci = self._free_color(used)
                    used.add(ci)
                    pd = PlayerDef(self._next_pid, str(entry.get("name", "LAN"))[:14], ci,
                                   entry.get("powerup", "speed"), client_id=cid)
                    self.players.append(pd)
                    self._client_players[cid].append(pd.pid)
                    self._next_pid += 1
                dirty = True
            elif mtype == "set_powerup":
                for p in self.players:
                    if p.pid == msg.get("pid") and p.client_id == cid:
                        p.powerup_kind = msg.get("kind", "speed")
                dirty = True
            elif mtype == "set_name":
                for p in self.players:
                    if p.pid == msg.get("pid") and p.client_id == cid:
                        p.name = str(msg.get("name", p.name))[:14]
                dirty = True
            elif mtype == "__disconnect__":
                pids = self._client_players.pop(cid, [])
                self.players = [p for p in self.players if p.pid not in pids]
                dirty = True
        if dirty:
            self.build()
            self._broadcast_lobby()

    # ------------------------------------------------------------------ #
    def handle_events(self, events) -> None:
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self._back()
                return
            used = False
            for dd in self._dropdowns:
                if dd.open and dd.handle_event(e):
                    used = True
                    break
            if used:
                continue
            for wgt in self.widgets:
                if wgt.handle_event(e):
                    break

    def update(self, dt: float) -> None:
        self._pump_host()
        for wgt in self.widgets:
            wgt.update(dt)

    def draw(self, surf) -> None:
        surf.fill(T.BG)
        w, h = self.size
        draw_text(surf, self.app.fonts.display(32), self.title, T.TEXT, (48, 40))
        sub = f"{len(self.players)} Spieler   -   Ziel: {self.app.config.settings.target_score} Punkte"
        if self.mode == "host" and self.host:
            sub += f"   -   deine IP: {local_ip()}:{DEFAULT_GAME_PORT}   ({self.host.client_count} verbunden)"
        elif self.mode == "host":
            sub += "   -   HOST-START FEHLGESCHLAGEN (Port belegt?)"
        draw_text(surf, self.app.fonts.body(16), sub, T.TEXT_MUTED, (50, 84))
        pygame.draw.line(surf, T.BORDER, (48, 116), (w - 48, 116), 1)

        for wgt in self.widgets:
            wgt.draw(surf, self.app.fonts)
        for dd in self._dropdowns:
            if dd.open:
                dd.draw_overlay(surf, self.app.fonts)


class _Swatch:
    def __init__(self, rect, pdef, scene):
        self.rect = pygame.Rect(rect)
        self.p = pdef
        self.scene = scene

    def handle_event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3) and self.rect.collidepoint(e.pos):
            step = 1 if e.button == 1 else -1
            self.p.color_index = (self.p.color_index + step) % len(PLAYER_COLORS)
            if self.p.is_local and 0 <= self.p.slot_index < len(self.scene.app.config.slots):
                self.scene.app.config.slots[self.p.slot_index].color_index = self.p.color_index
            self.scene._broadcast_lobby()
            return True
        return False

    def update(self, dt):
        pass

    def draw(self, surf, fonts):
        pygame.draw.rect(surf, color_for(self.p.color_index), self.rect, border_radius=8)
        pygame.draw.rect(surf, T.BORDER, self.rect, width=1, border_radius=8)


class _Static:
    def __init__(self, rect, text, color=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.color = color or T.TEXT

    def handle_event(self, e):
        return False

    def update(self, dt):
        pass

    def draw(self, surf, fonts):
        draw_text(surf, fonts.body(15), self.text, self.color, (self.rect.x, self.rect.y))
