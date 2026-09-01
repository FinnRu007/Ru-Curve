"""LAN beitreten: Hosts finden / IP eingeben, dann Client-Lobby."""

from __future__ import annotations

from dataclasses import asdict

import pygame

from .. import theme as T
from ..colors import color_for
from ..config import DEFAULT_GAME_PORT, DISCOVERY_PORT
from ..game.powerups import PICKER_OPTIONS, powerup_label
from ..net.client import GameClient
from ..net.discovery import Listener, local_ip
from ..net.errors import friendly
from ..ui.widgets import Button, Dropdown, TextInput, draw_text, wrap_text
from .common import BaseMenuScene

_PU_OPTIONS = PICKER_OPTIONS


class JoinScene(BaseMenuScene):
    title = "Uber LAN beitreten"
    subtitle = "Gefundene Hosts im Netzwerk - oder IP-Adresse direkt eingeben"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.listener = Listener()
        self.manual_ip = "192.168."
        self.status = ("", "")

    def on_enter(self) -> None:
        self.app.audio.music("menu")
        self.listener.start()
        self.build()

    def on_exit(self) -> None:
        self.listener.stop()

    def build(self) -> None:
        w, h = self.size
        self.widgets = [
            TextInput((48, h - 150, 300, 40), self.manual_ip,
                      lambda t: setattr(self, "manual_ip", t), max_len=42,
                      placeholder="IP  oder  IP:Port"),
            Button((360, h - 150, 160, 40), "Verbinden", self._connect_manual, "primary"),
            Button((48, h - 90, 160, 40), "Zurueck", self._back, "ghost"),
        ]
        self._host_buttons: list[tuple[Button, dict]] = []

    # ------------------------------------------------------------------ #
    def _connect_manual(self) -> None:
        raw = self.manual_ip.strip()
        port = DEFAULT_GAME_PORT
        # "IP:Port" erlauben (fuer Portweiterleitung / Spiel uebers Internet)
        if raw.count(":") == 1 and "]" not in raw:
            host, _, p = raw.rpartition(":")
            if p.isdigit():
                raw, port = host, int(p)
        self._connect(raw, port)

    def _connect(self, ip: str, port: int) -> None:
        if not ip:
            self.status = ("Keine Adresse eingegeben", "")
            return
        self.status = ("Verbinde mit %s:%d ..." % (ip, port), "")
        client = GameClient()
        if client.connect(ip, port, timeout=8.0):
            self.app.audio.play("click")
            self.app.set_scene(ClientLobbyScene(self.app, client, self.listener))
        else:
            self.status = friendly(client.error, ip, port)

    def _back(self) -> None:
        from .menu import MenuScene

        self.app.set_scene(MenuScene(self.app))

    def on_escape(self) -> bool:
        self._back()
        return True

    # ------------------------------------------------------------------ #
    def handle_events(self, events) -> None:
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self._back()
                return
            for b, _info in getattr(self, "_host_buttons", []):
                if b.handle_event(e):
                    break
            for wgt in self.widgets:
                if wgt.handle_event(e):
                    break

    def update(self, dt: float) -> None:
        for wgt in self.widgets:
            wgt.update(dt)

    def draw(self, surf) -> None:
        surf.fill(T.BG)
        w, h = self.size
        draw_text(surf, self.app.fonts.display(32), self.title, T.TEXT, (48, 40))
        draw_text(surf, self.app.fonts.body(16), self.subtitle, T.TEXT_MUTED, (50, 84))
        pygame.draw.line(surf, T.BORDER, (48, 116), (w - 48, 116), 1)

        hosts = self.listener.hosts()
        self._host_buttons = []
        y = 150
        if not hosts:
            draw_text(surf, self.app.fonts.body(16), "Suche im Netzwerk ...", T.TEXT_MUTED, (50, y + 4))
        for hinfo in hosts:
            box = pygame.Rect(48, y, min(760, w - 96), 52)
            pygame.draw.rect(surf, T.SURFACE, box, border_radius=T.R_SM)
            draw_text(surf, self.app.fonts.body_bold(17), hinfo["name"], T.TEXT, (box.x + 16, box.y + 6))
            draw_text(surf, self.app.fonts.body(13),
                      f"{hinfo['ip']}:{hinfo['port']}   -   {hinfo['players']} Spieler",
                      T.TEXT_MUTED, (box.x + 16, box.y + 28))
            b = Button((box.right - 130, box.y + 8, 118, 36), "Beitreten",
                       (lambda hi=hinfo: self._connect(hi["ip"], hi["port"])), "primary")
            b.draw(surf, self.app.fonts)
            self._host_buttons.append((b, hinfo))
            y += 60

        self._draw_help(surf, w, h)
        for wgt in self.widgets:
            wgt.draw(surf, self.app.fonts)

    def _draw_help(self, surf, w, h) -> None:
        fonts = self.app.fonts
        head, tip = self.status if isinstance(self.status, tuple) else (self.status, "")
        if head:
            bw = min(760, w - 96)
            font = fonts.body(13)
            lines = wrap_text(font, tip, bw - 28) if tip else []
            box = pygame.Rect(48, h - 250, bw, 44 + 19 * len(lines))
            bad = not head.startswith("Verbinde ")
            pygame.draw.rect(surf, (253, 238, 238) if bad else T.SURFACE, box,
                             border_radius=T.R_SM)
            pygame.draw.rect(surf, T.DANGER if bad else T.BORDER, box, width=2,
                             border_radius=T.R_SM)
            draw_text(surf, fonts.body_bold(16), head,
                      T.DANGER if bad else T.TEXT, (box.x + 14, box.y + 9))
            for i, line in enumerate(lines):
                draw_text(surf, font, line, T.TEXT_MUTED,
                          (box.x + 14, box.y + 34 + i * 19))

        if self.listener.error:
            draw_text(surf, fonts.body(13),
                      "Hostsuche blockiert (Port %d). Firewall pruefen - "
                      "IP-Eingabe geht trotzdem." % DISCOVERY_PORT,
                      T.DANGER, (48, h - 246))

        draw_text(surf, fonts.body(13),
                  "Deine IP: %s   -   der Host zeigt seine Adresse in der Lobby oben rechts."
                  % local_ip(), T.TEXT_MUTED, (48, h - 44))


# =========================================================================== #
class ClientLobbyScene(BaseMenuScene):
    title = "Lobby - beigetreten"

    def __init__(self, app, client: GameClient, listener: Listener | None = None) -> None:
        super().__init__(app)
        self.client = client
        self.listener = listener
        self.cid: int | None = None
        self.remote_players: list[dict] = []
        self.settings_wire: dict = {}
        self.host_name = "Host"
        self._sent_hello = False
        self._my_local = self._collect_local()
        self._dropdowns: list[Dropdown] = []
        self.status = "Verbunden. Warte auf Host ..."

    def _collect_local(self) -> list[dict]:
        out = []
        for i, slot in enumerate(self.app.config.slots):
            if slot.enabled:
                out.append({"slot_index": i, "name": slot.name,
                            "powerup": slot.powerup_kind, "color_index": slot.color_index})
        if not out:  # mindestens ein Spieler
            slot = self.app.config.slots[0]
            out.append({"slot_index": 0, "name": slot.name,
                        "powerup": slot.powerup_kind, "color_index": slot.color_index})
        return out

    def on_enter(self) -> None:
        self.build()

    def on_exit(self) -> None:
        pass

    def build(self) -> None:
        w, h = self.size
        self.widgets = [Button((48, h - 80, 160, 42), "Verlassen", self._leave, "ghost")]
        self._dropdowns = []
        y = 150
        for entry in self._my_local:
            dd = Dropdown((300, y, 220, 34), _PU_OPTIONS, entry["powerup"],
                          (lambda v, en=entry: self._change_powerup(en, v)))
            self.widgets.append(dd)
            self._dropdowns.append(dd)
            y += 46

    def _change_powerup(self, entry, v) -> None:
        entry["powerup"] = v
        # pid herausfinden
        mine = [p for p in self.remote_players if p.get("client_id") == self.cid]
        idx = self._my_local.index(entry)
        if idx < len(mine):
            self.client.send({"type": "set_powerup", "pid": mine[idx]["pid"], "kind": v})

    # ------------------------------------------------------------------ #
    def _leave(self) -> None:
        self.client.close()
        from .menu import MenuScene

        self.app.set_scene(MenuScene(self.app))

    def on_escape(self) -> bool:
        self._leave()
        return True

    def handle_events(self, events) -> None:
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self._leave()
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
        msgs = self.client.poll()
        for i, msg in enumerate(msgs):
            rest = msgs[i + 1:]
            t = msg.get("type")
            if t == "welcome":
                self.cid = msg.get("cid")
                if not self._sent_hello:
                    self.client.send({
                        "type": "hello",
                        "players": [
                            {"name": e["name"], "powerup": e["powerup"], "color_index": e["color_index"]}
                            for e in self._my_local
                        ],
                    })
                    self._sent_hello = True
            elif t == "lobby":
                self.remote_players = msg.get("players", [])
                self.settings_wire = msg.get("settings", {})
                self.host_name = msg.get("host", "Host")
                self.status = f"In der Lobby von {self.host_name}. Warte auf Start ..."
            elif t == "round_start":
                from .client_game import ClientGameScene

                self.app.set_scene(ClientGameScene(self.app, self.client, msg, self.cid))
                return
            elif t == "pt_begin":
                from ..party.base import PartyPlayer
                from .tournament import TournamentScene

                party = [PartyPlayer.from_wire(d, self.cid)
                         for d in msg.get("players", [])]
                scene = TournamentScene(
                    self.app, party, client=self.client, cid=self.cid,
                    order=msg.get("order") or [],
                    points_top=int(msg.get("points_top", 10)))
                # Wichtig: was im selben Paket kam (z.B. pt_game), mitgeben -
                # sonst ist es weg und der Mitspieler sieht nichts.
                scene._inbox = list(rest)
                self.app.set_scene(scene)
                return
            elif t == "pt_busy":
                self.status = ("Der Host spielt gerade ein Turnier (Spiel %s von %s). "
                               "Du bist beim naechsten dabei." %
                               (msg.get("i", "?"), msg.get("n", "?")))
            elif t == "__disconnect__":
                self.status = "Verbindung zum Host verloren."
                self.client.close()
        for wgt in self.widgets:
            wgt.update(dt)

    def draw(self, surf) -> None:
        surf.fill(T.BG)
        w, h = self.size
        draw_text(surf, self.app.fonts.display(32), self.title, T.TEXT, (48, 40))
        draw_text(surf, self.app.fonts.body(16), self.status, T.TEXT_MUTED, (50, 84))
        pygame.draw.line(surf, T.BORDER, (48, 116), (w - 48, 116), 1)

        y = 150
        for p in self.remote_players:
            box = pygame.Rect(48, y, min(680, w - 96), 40)
            pygame.draw.rect(surf, T.SURFACE, box, border_radius=T.R_SM)
            pygame.draw.rect(surf, color_for(p.get("color_index", 0)), (box.x, box.y, 6, box.h), border_radius=3)
            mine = " (du)" if p.get("client_id") == self.cid else ""
            draw_text(surf, self.app.fonts.body_bold(16), p.get("name", "?") + mine, T.TEXT, (box.x + 16, box.y + 4))
            draw_text(surf, self.app.fonts.body(13), powerup_label(p.get("powerup_kind", "speed")),
                      T.TEXT_MUTED, (box.x + 220, box.y + 6))
            y += 46

        if self.settings_wire:
            sw = self.settings_wire
            draw_text(surf, self.app.fonts.body(14),
                      f"Host-Einstellungen: Speed {sw.get('speed')} - Radius {sw.get('turn_radius')} - "
                      f"Ziel {sw.get('target_score')} Pkt",
                      T.TEXT_MUTED, (50, h - 130))
        draw_text(surf, self.app.fonts.body(14), "Deine Steuerung gilt wie in 'Steuerung' eingestellt.",
                  T.TEXT_MUTED, (50, h - 110))
        for wgt in self.widgets:
            wgt.draw(surf, self.app.fonts)
        for dd in self._dropdowns:
            if dd.open:
                dd.draw_overlay(surf, self.app.fonts)
