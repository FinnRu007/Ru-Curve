"""Lobby fuer 'An einem PC spielen' (local) und 'Uber LAN hosten' (host)."""

from __future__ import annotations

import socket
from dataclasses import asdict

import pygame

from .. import theme as T
from ..colors import PLAYER_COLORS, color_for
from ..config import DEFAULT_GAME_PORT
from ..game.powerups import PICKER_OPTIONS, RANDOM_ID, powerup_label
from ..net.discovery import Beacon, local_ip
from ..net.internet import PublicIP
from ..net.upnp import PortMapper
from ..net.host import GameHost
from ..session import GameSession, PlayerDef
from ..ui.widgets import Button, Dropdown, TextInput, draw_text, wrap_text
from .common import BaseMenuScene

_PU_OPTIONS = PICKER_OPTIONS


class LobbyScene(BaseMenuScene):
    def __init__(self, app, mode: str = "local") -> None:
        super().__init__(app)
        self.mode = mode
        self.title = ("Lobby - an einem PC" if mode == "local"
                      else "Lobby - du bist Gastgeber")
        self.players: list[PlayerDef] = []
        self.host: GameHost | None = None
        self.beacon: Beacon | None = None
        self.session: GameSession | None = None
        self._adopted = False
        self._next_pid = 0
        self._client_players: dict[int, list[int]] = {}   # cid -> [pid,...]
        self._dropdowns: list[Dropdown] = []
        self.host_error: tuple | None = None
        self.mapper: PortMapper | None = None      # Portfreigabe im Router
        self.public: PublicIP | None = None
        # Overlay "einzelnes Spiel starten" - bewusst als Overlay und nicht als
        # eigene Szene, damit der Host waehrenddessen weiter am Netz bleibt.
        self.picker_open = False
        self._picker_widgets: list = []
        self._copy_note = ""            # Rueckmeldung zum Kopieren
        self._copy_note_t = 0.0

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
                    from ..net.errors import host_problem

                    self.host_error = host_problem(exc)
                    print(f"[lobby] Host-Start fehlgeschlagen: {exc}")
                    self.host = None
                if self.host:
                    self.beacon = Beacon(self._beacon_info)
                    self.beacon.start()
                    # Fuer Spielen uebers Internet: Port im Router oeffnen
                    # und die oeffentliche Adresse ermitteln - beides im
                    # Hintergrund, das Menue bleibt bedienbar.
                    self.mapper = PortMapper(self.host.port)
                    self.mapper.start()
                    self.public = PublicIP()
                    self.public.start()
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
            self.players.append(PlayerDef(pid, f"Bot {b + 1}", ci, self._random_powerup(),
                                          is_bot=True,
                                          difficulty=self.app.config.settings.bot_difficulty))
            pid += 1
        self._next_pid = pid

    def _unique_name(self, name: str, skip=None) -> str:
        """Gleiche Namen sind in der Rangliste nicht auseinanderzuhalten."""
        taken = {p.name for p in self.players if p is not skip}
        if name not in taken:
            return name
        for n in range(2, 20):
            cand = "%s %d" % (name[:12], n)
            if cand not in taken:
                return cand
        return name

    def _random_powerup(self) -> str:
        """Bots spielen auf 'Zufaellig' - dann wuerfeln sie jede Runde neu."""
        return RANDOM_ID

    @staticmethod
    def _free_color(used: set[int]) -> int:
        for i in range(len(PLAYER_COLORS)):
            if i not in used:
                return i
        return len(used) % len(PLAYER_COLORS)

    def _beacon_info(self) -> dict:
        return {
            "name": f"{socket.gethostname()}",
            "port": self.host.port if self.host else DEFAULT_GAME_PORT,
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

        self.widgets.append(Button((w - 220, h - 78, 172, 50), "Kurve starten",
                                   self._start, "ghost"))
        self.widgets.append(Button((w - 410, h - 78, 182, 50), "TURNIER",
                                   self._start_tournament, "primary"))
        self.widgets.append(Button((w - 618, h - 78, 196, 50), "Einzelnes Spiel",
                                   self._open_picker, "ghost"))
        self.widgets.append(Button((w - 220, by, 172, 40), "Zurueck", self._back, "ghost"))

    def _draw_picker(self, surf) -> None:
        w, h = self.size
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        veil.fill((10, 12, 20, 170))
        surf.blit(veil, (0, 0))
        panel, heads, _cells = self._picker_layout()
        pygame.draw.rect(surf, T.SURFACE, panel, border_radius=T.R_LG)
        pygame.draw.rect(surf, T.BORDER, panel, width=1, border_radius=T.R_LG)
        fonts = self.app.fonts
        draw_text(surf, fonts.display(24), "Einzelnes Spiel starten", T.TEXT,
                  (panel.x + 24, panel.y + 18))
        draw_text(surf, fonts.body(14),
                  "Ein Durchgang, danach zurueck in die Lobby - alle "
                  "Mitspieler sind dabei.",
                  T.TEXT_MUTED, (panel.x + 24, panel.y + 48))
        for title, y in heads:
            draw_text(surf, fonts.body_bold(13), title, T.ACCENT,
                      (panel.x + 24, y))
        for wgt in self._picker_widgets:
            wgt.draw(surf, fonts)

    def share_address(self) -> str:
        """Die Adresse, die man weitergibt - Internet bevorzugt."""
        if self.mode != "host" or not self.host:
            return ""
        ip = self.public.ip if self.public else ""
        if not ip and self.mapper:
            ip = self.mapper.external_ip
        if not ip:
            ip = local_ip()
        return "%s:%d" % (ip, self.host.port)

    def copy_address(self) -> bool:
        """Adresse in die Zwischenablage. Sagt ehrlich, ob es geklappt hat."""
        from ..ui.clipboard import put_text

        addr = self.share_address()
        if not addr:
            return False
        ok = put_text(addr)
        self._copy_note = ("%s kopiert" % addr if ok else
                           "Kopieren ging nicht - Adresse bitte abtippen")
        self._copy_note_t = 4.0
        self.app.audio.play("click" if ok else "wrong")
        return ok

    def _draw_net_box(self, surf, w) -> None:
        """Zeigt beide Adressen: im WLAN und uebers Internet."""
        fonts = self.app.fonts
        box = pygame.Rect(w - 452, 22, 404, 108)
        if self.mode != "host":
            if self.mode == "local":
                draw_text(surf, fonts.body(13),
                          "Nur an diesem PC. Fuer Mitspieler woanders: zurueck "
                          "und 'Spiel eroeffnen' waehlen",
                          T.TEXT_MUTED, (box.x + 40, 60))
            return
        if not self.host:
            pygame.draw.rect(surf, (253, 238, 238), box, border_radius=T.R_SM)
            pygame.draw.rect(surf, T.DANGER, box, width=2, border_radius=T.R_SM)
            head, tip = self.host_error or ("Host konnte nicht starten", "")
            draw_text(surf, fonts.body_bold(15), head, T.DANGER, (box.x + 14, box.y + 10))
            for i, line in enumerate(wrap_text(fonts.body(12), tip, box.w - 28)):
                draw_text(surf, fonts.body(12), line, T.TEXT_MUTED,
                          (box.x + 14, box.y + 32 + i * 16))
            return

        pygame.draw.rect(surf, T.SURFACE, box, border_radius=T.R_SM)
        pygame.draw.rect(surf, T.OK, (box.x, box.y, 5, box.h), border_radius=2)

        n = self.host.client_count
        draw_text(surf, fonts.body(12),
                  "%d verbunden" % n if n else "warte auf Mitspieler ...",
                  T.OK if n else T.TEXT_MUTED, (box.right - 132, box.y + 8))

        draw_text(surf, fonts.body(11), "Im gleichen WLAN:", T.TEXT_MUTED,
                  (box.x + 14, box.y + 8))
        draw_text(surf, fonts.display(22), "%s:%d" % (local_ip(), self.host.port),
                  T.TEXT, (box.x + 14, box.y + 22))

        draw_text(surf, fonts.body(11), "Uebers Internet:", T.TEXT_MUTED,
                  (box.x + 14, box.y + 54))
        ip = self.public.ip if self.public else ""
        if not ip and self.mapper:
            ip = self.mapper.external_ip
        if ip:
            state = self.mapper.status if self.mapper else "idle"
            col = T.OK if state == "ok" else (T.WARN if state == "fehlgeschlagen" else T.TEXT_MUTED)
            draw_text(surf, fonts.display(22), "%s:%d" % (ip, self.host.port),
                      T.TEXT, (box.x + 14, box.y + 68))
            mark = {"ok": "Port offen", "suchen": "oeffne Port ...",
                    "fehlgeschlagen": "Port pruefen!"}.get(state, "")
            if mark:
                draw_text(surf, fonts.body(11), mark, col, (box.right - 132, box.y + 74))
        else:
            draw_text(surf, fonts.body(14), "wird ermittelt ...", T.TEXT_MUTED,
                      (box.x + 14, box.y + 70))

        if self._copy_note:
            draw_text(surf, fonts.body_bold(12), self._copy_note, T.OK,
                      (box.x + 14, box.bottom + 4))
        else:
            draw_text(surf, fonts.body(12), "Strg+C kopiert die Adresse",
                      T.TEXT_MUTED, (box.x + 14, box.bottom + 4))

    def _draw_net_hint(self, surf, w, h) -> None:
        """Unter der Spielerliste: was tun, wenn das Internet-Spiel klemmt."""
        if self.mode != "host" or not self.host or not self.mapper:
            return
        fonts = self.app.fonts
        if self.mapper.status == "ok":
            draw_text(surf, fonts.body(13),
                      "Internet: Router-Port automatisch geoeffnet - die obere "
                      "Adresse funktioniert auch von ausserhalb.",
                      T.OK, (48, h - 196))
            return
        if self.mapper.status == "suchen":
            draw_text(surf, fonts.body(13), "Internet: frage den Router nach der "
                      "Portfreigabe ...", T.TEXT_MUTED, (48, h - 196))
            return
        if self.mapper.status == "fehlgeschlagen":
            draw_text(surf, fonts.body_bold(13),
                      "Internet-Spiel: Port muss von Hand freigegeben werden",
                      T.WARN, (48, h - 200))
            for i, line in enumerate(wrap_text(fonts.body(12), self.mapper.message,
                                               min(820, w - 100), max_lines=2)):
                draw_text(surf, fonts.body(12), line, T.TEXT_MUTED,
                          (48, h - 182 + i * 16))

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
        self.players.append(PlayerDef(self._next_pid, f"Bot {n}", ci, self._random_powerup(),
                                      is_bot=True,
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
        if self.mapper:
            self.mapper.close()
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

    # -- Einzelnes Minispiel -------------------------------------------
    # Die Auswahl ist in zwei Gruppen geteilt: oben die Spiele, in denen man
    # sich direkt in die Quere kommt, unten die, bei denen jeder fuer sich
    # antritt. Beim Suchen ist das der Unterschied, der zaehlt.
    def _picker_groups(self):
        from ..party.registry import ALL_GAMES

        gegen = [g for g in ALL_GAMES if g.authoritative]
        einzeln = [g for g in ALL_GAMES if not g.authoritative]
        return (("Gegeneinander - alle gleichzeitig in einer Arena", gegen),
                ("Jeder fuer sich - Kopf, Reflex, Merken", einzeln))

    def _picker_layout(self):
        """(Panel, [(Kopfzeile, y)], [(Spiel, Rechteck)]) - einmal gerechnet."""
        w, h = self.size
        pw = min(820, w - 80)
        cols = 3 if pw >= 700 else 2
        bw = (pw - 48 - 14 * (cols - 1)) // cols
        bh = 50
        heads, cells = [], []
        y = 78
        for title, games in self._picker_groups():
            heads.append((title, y))
            y += 26
            for i, game in enumerate(games):
                cells.append((game, pygame.Rect(24 + (i % cols) * (bw + 14),
                                                y + (i // cols) * (bh + 8),
                                                bw, bh)))
            y += ((len(games) + cols - 1) // cols) * (bh + 8) + 14
        ph = min(h - 40, y + 62)
        panel = pygame.Rect((w - pw) // 2, (h - ph) // 2, pw, ph)
        heads = [(t, panel.y + oy) for t, oy in heads]
        cells = [(g, r.move(panel.x, panel.y)) for g, r in cells]
        return panel, heads, cells

    def _open_picker(self) -> None:
        self.picker_open = True
        self._picker_widgets = []
        panel, _heads, cells = self._picker_layout()
        for game, rect in cells:
            self._picker_widgets.append(
                Button(rect, game.name,
                       (lambda gid=game.id: self._start_single(gid)), "ghost"))
        self._picker_widgets.append(
            Button((panel.centerx - 80, panel.bottom - 54, 160, 42), "Abbrechen",
                   self._close_picker, "ghost"))

    def _picker_rect(self) -> pygame.Rect:
        return self._picker_layout()[0]

    def _close_picker(self) -> None:
        self.picker_open = False
        self._picker_widgets = []

    def _start_single(self, game_id: str) -> None:
        """Ein einzelnes Minispiel - laeuft ueber dieselbe Turnierlogik."""
        self._close_picker()
        self._start_tournament(order=[game_id])

    def _start_tournament(self, order: list | None = None) -> None:
        """Baut das Turnier, verteilt Reihenfolge + Spieler und startet es."""
        import random as _r

        from ..party.base import PartyPlayer
        from ..party.tournament import Tournament
        from .tournament import TournamentScene

        if not self.players:
            return
        for i, p in enumerate(self.players):
            p.pid = i
        self.app.config.save()
        st = self.app.config.settings
        if order is None:
            order = Tournament.build_order(_r.Random(), st.enabled_party_games(),
                                           st.party_games, st.party_shuffle)
        party = [
            PartyPlayer(pid=p.pid, name=p.name, color=color_for(p.color_index),
                        color_index=p.color_index, is_local=(p.client_id < 0),
                        is_bot=p.is_bot, slot_index=p.slot_index,
                        client_id=p.client_id, difficulty=st.bot_difficulty)
            for p in self.players
        ]
        if self.host:
            self.host.broadcast({
                "type": "pt_begin",
                "players": [p.to_wire() for p in party],
                "order": order,
                "points_top": st.party_points_top,
                "settings": asdict(st),
            })
        self.app.audio.play("click")
        self.app.set_scene(TournamentScene(
            self.app, party, host=self.host, beacon=self.beacon,
            order=order, points_top=st.party_points_top))

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
                    pd = PlayerDef(self._next_pid,
                                   self._unique_name(str(entry.get("name", "LAN"))[:14]),
                                   ci, entry.get("powerup", "speed"), client_id=cid)
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
                        want = str(msg.get("name", p.name))[:14].strip()
                        if want and want != p.name:
                            # gleiche Pruefung wie beim Beitreten, sonst
                            # heissen ploetzlich zwei Leute gleich
                            p.name = self._unique_name(want, skip=p)
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
        if self.picker_open:
            for e in events:
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    self._close_picker()
                    return
                for wgt in self._picker_widgets:
                    if wgt.handle_event(e):
                        break
            return
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self._back()
                return
            # Strg+C kopiert die Adresse - aber nur, wenn gerade kein
            # Textfeld den Fokus hat, sonst kopiert man dort die Auswahl.
            if (e.type == pygame.KEYDOWN and e.key == pygame.K_c
                    and (e.mod & pygame.KMOD_CTRL)
                    and not any(getattr(wd, "focused", False)
                                for wd in self.widgets)):
                self.copy_address()
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
        if self._copy_note_t > 0.0:
            self._copy_note_t -= dt
            if self._copy_note_t <= 0.0:
                self._copy_note = ""
        self._pump_host()
        for wgt in self.widgets:
            wgt.update(dt)

    def draw(self, surf) -> None:
        surf.fill(T.BG)
        w, h = self.size
        draw_text(surf, self.app.fonts.display(32), self.title, T.TEXT, (48, 40))
        sub = f"{len(self.players)} Spieler   -   Ziel: {self.app.config.settings.target_score} Punkte"
        draw_text(surf, self.app.fonts.body(16), sub, T.TEXT_MUTED, (50, 84))
        pygame.draw.line(surf, T.BORDER, (48, 116), (w - 48, 116), 1)
        self._draw_net_box(surf, w)
        self._draw_net_hint(surf, w, h)

        for wgt in self.widgets:
            wgt.draw(surf, self.app.fonts)
        for dd in self._dropdowns:
            if dd.open:
                dd.draw_overlay(surf, self.app.fonts)
        if self.picker_open:
            self._draw_picker(surf)


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
        from ..ui.widgets import hover_here

        hover = hover_here(self.rect)
        pygame.draw.rect(surf, color_for(self.p.color_index), self.rect, border_radius=8)
        pygame.draw.rect(surf, T.ACCENT if hover else T.BORDER, self.rect,
                         width=3 if hover else 1, border_radius=8)


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
