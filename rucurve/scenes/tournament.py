"""Turnier-Szene: spielt die Minispiele nacheinander und fuehrt die Rangliste.

Laeuft auf jeder Maschine. Der Host bestimmt Reihenfolge, Aufgaben und
Zeitpunkte und verteilt sie; jede Maschine spielt ihre eigenen Leute und meldet
das Ergebnis zurueck. Bei "authoritative" Spielen (Achtung die Kurve) rechnet
der Host fuer alle und schickt Schnappschuesse.
"""

from __future__ import annotations

import random
import time

import pygame

from ..party import ui as U
from ..party.base import GameContext, PartyPlayer, Result
from ..party.registry import GAME_BY_ID, game_name
from ..party.tournament import Tournament
from ..ui.widgets import Button, draw_text, key_name

HEADER_H = 74
SIDE_W = 300
PAD = 16

REPORT_TIMEOUT = 8.0


def build_bindings(app, players, local_pids):
    """pid -> (links, aktion, rechts). Bots bekommen keine Tasten."""
    slots = app.config.slots
    enabled = [i for i, s in enumerate(slots) if s.enabled] or [0]
    out = {}
    fallback = list(enabled)
    for pid in sorted(local_pids):
        p = next((q for q in players if q.pid == pid), None)
        if p is None or p.is_bot:
            continue
        idx = p.slot_index if 0 <= p.slot_index < len(slots) else None
        if idx is None:
            idx = fallback.pop(0) if fallback else enabled[0]
        s = slots[idx]
        out[pid] = (s.left, s.powerup, s.right)
    return out


class TournamentScene:
    """Phasen: intro -> play -> wait -> result -> (naechstes Spiel | over)."""

    def __init__(self, app, players, *, host=None, beacon=None, client=None,
                 cid=None, order=None, points_top=10) -> None:
        self.app = app
        self.host = host
        self.beacon = beacon
        self.client = client
        self.cid = cid
        self.is_host = client is None
        self.players: list[PartyPlayer] = players

        self.tour = Tournament(players=players, order=list(order or []),
                               points_top=points_top)
        self.local_pids = [p.pid for p in players if p.is_local]
        self.bindings = build_bindings(app, players, self.local_pids)

        self.phase = "intro"
        self.phase_t = 0.0
        self.game = None
        self.game_cls = None
        self.record = None
        self.live: dict[int, float] = {}
        self._reports: dict[int, dict] = {}     # client_id -> {pid: Result}
        self._reported_local = False
        self._wait_started = 0.0
        self._net_acc = 0.0
        self._live_acc = 0.0
        self.widgets: list = []
        self.message = ""
        self._tick_left = 99
        self._applause_t = 0.0
        # Nachrichten, die die Lobby beim Szenenwechsel schon abgeholt hat -
        # sie duerfen NICHT verlorengehen (sonst kommt pt_game nie an).
        self._inbox: list = []
        self._last_payload: dict | None = None
        self._resync_t = 0.0
        self._got_go = False

    # ================================================================== #
    #  Lebenszyklus
    # ================================================================== #
    def on_enter(self):
        self.app.audio.play("whistle")
        if self.is_host:
            self._start_game(0)

    def on_exit(self):
        pass

    def resize(self):
        if self.game is not None:
            self.game.ctx.area = self.play_rect()
            hook = getattr(self.game, "on_resize", None)
            if hook:
                hook(self.game.ctx.area)
        self._build_widgets()

    # -- Geometrie ------------------------------------------------------
    def play_rect(self):
        w, h = self.app.screen.get_size()
        side = SIDE_W if w >= 1000 else 0
        return pygame.Rect(PAD, HEADER_H + PAD, w - side - 3 * PAD if side else w - 2 * PAD,
                           h - HEADER_H - 2 * PAD)

    def side_rect(self):
        w, h = self.app.screen.get_size()
        if w < 1000:
            return None
        return pygame.Rect(w - SIDE_W - PAD, HEADER_H + PAD, SIDE_W, h - HEADER_H - 2 * PAD)

    # ================================================================== #
    #  Spielsteuerung (Host)
    # ================================================================== #
    def _start_game(self, index):
        self.tour.index = index - 1
        gid = self.tour.advance()
        if gid is None:
            self._finish_tournament()
            return
        cls = GAME_BY_ID.get(gid)
        if cls is None:
            self._start_game(index + 1)
            return
        seed = random.randrange(1 << 30)
        cfg = cls.make_config(random.Random(seed), self.players)
        payload = {"type": "pt_game", "i": self.tour.index, "game": gid,
                   "cfg": cfg, "seed": seed}
        self._last_payload = payload
        if self.host:
            self.host.broadcast(payload)
        self._build_game(gid, cfg, seed)

    def _build_game(self, gid, cfg, seed):
        cls = GAME_BY_ID.get(gid)
        if cls is None:
            return
        self.game_cls = cls
        ctx = GameContext(app=self.app, players=self.players,
                          local_pids=list(self.local_pids), bindings=self.bindings,
                          config=cfg, area=self.play_rect(),
                          is_host=self.is_host, rng_seed=seed)
        self.game = cls(ctx)
        self.phase = "intro"
        self.phase_t = 0.0
        self._tick_left = 99
        self.live = {}
        self._reports = {}
        self._reported_local = False
        self.message = ""
        self._build_widgets()

    def _begin_play(self):
        self.phase = "play"
        self.phase_t = 0.0
        if self.game:
            self.game.start()
        self.app.audio.play("go")

    def _finish_tournament(self):
        self.phase = "over"
        self.phase_t = 0.0
        self.app.audio.play("fanfare")
        self._applause_t = 0.9
        if self.host:
            self.host.broadcast({"type": "pt_over",
                                 "standings": self.tour.standings()})
        self._build_widgets()

    # ================================================================== #
    #  Ergebnisse einsammeln
    # ================================================================== #
    def _local_results(self):
        if self.game is None:
            return {}
        return self.game.results()

    def _send_report(self):
        if self._reported_local or self.game is None:
            return
        self._reported_local = True
        res = {str(pid): r.to_wire() for pid, r in self._local_results().items()}
        if self.is_host:
            self._reports[-1] = {int(k): Result.from_wire(v) for k, v in res.items()}
            self._wait_started = time.time()
        elif self.client:
            self.client.send({"type": "pt_report", "i": self.tour.index, "res": res})

    def _expected_clients(self):
        """Welche Client-IDs muessen noch melden?"""
        need = set()
        for p in self.players:
            if p.client_id >= 0:
                need.add(p.client_id)
        return need

    def _try_close_game(self):
        """Host: sobald alle gemeldet haben (oder die Zeit reisst), auswerten."""
        if not self.is_host or self.game is None:
            return
        if self.game.authoritative:
            merged = dict(self.game.host_results())
        else:
            need = self._expected_clients()
            have = {c for c in self._reports if c >= 0}
            waited = time.time() - self._wait_started
            if not need.issubset(have) and waited < REPORT_TIMEOUT:
                return
            merged = {}
            for rows in self._reports.values():
                merged.update(rows)
        rec = self.tour.apply_results(self.game_cls.id, self.game_cls.name,
                                      merged, self.game_cls.scoring)
        self.record = rec
        self.phase = "result"
        self.phase_t = 0.0
        self.app.audio.play("fanfare")
        if self.host:
            self.host.broadcast({"type": "pt_result", "i": self.tour.index,
                                 "rows": rec.rows, "totals": self.tour.to_wire()})
        self._build_widgets()

    # ================================================================== #
    #  Netzwerk
    # ================================================================== #
    def _pump_host(self):
        if not self.host:
            return
        for cid, msg in self.host.poll():
            t = msg.get("type")
            if t == "pt_report" and msg.get("i") == self.tour.index:
                self._reports[cid] = {int(k): Result.from_wire(v)
                                      for k, v in (msg.get("res") or {}).items()}
                if not self._wait_started:
                    self._wait_started = time.time()
            elif t == "pt_live" and msg.get("i") == self.tour.index:
                for k, v in (msg.get("rows") or {}).items():
                    self.live[int(k)] = v
            elif t == "pt_input" and self.game is not None:
                self.game.apply_input(cid, msg)
            elif t == "pt_need_game":
                # Der Client hat den Spielstart verpasst - nochmal schicken.
                if self._last_payload is not None:
                    again = dict(self._last_payload)
                    again["started"] = self.phase in ("play", "wait", "result")
                    self.host.send(cid, again)
            elif t == "__connect__":
                # Jemand verbindet sich, waehrend das Turnier schon laeuft
                self.host.send(cid, {"type": "pt_busy",
                                     "game": self.game_cls.name if self.game_cls else "",
                                     "i": self.tour.index + 1,
                                     "n": len(self.tour.order)})
            elif t == "__disconnect__":
                self._reports.pop(cid, None)

    def _pump_client(self):
        if not self.client:
            return
        msgs, self._inbox = self._inbox, []
        msgs = msgs + self.client.poll()
        for msg in msgs:
            t = msg.get("type")
            if t == "pt_game":
                same = (self.game is not None
                        and self.tour.index == int(msg.get("i", -1))
                        and self.game_cls is not None
                        and self.game_cls.id == msg.get("game"))
                if not same:
                    self.tour.index = int(msg.get("i", 0))
                    self._build_game(msg.get("game", ""), msg.get("cfg") or {},
                                     int(msg.get("seed", 0)))
                if msg.get("started") and self.phase == "intro":
                    self._begin_play()
            elif t == "pt_go":
                self._got_go = True
                if self.phase == "intro":
                    self._begin_play()
            elif t == "pt_state" and self.game is not None:
                self.game.apply_state(msg.get("s") or {})
            elif t == "pt_live":
                for k, v in (msg.get("rows") or {}).items():
                    self.live[int(k)] = v
            elif t == "pt_result":
                self.tour.load_wire(msg.get("totals") or {})
                from ..party.tournament import GameRecord

                self.record = GameRecord(
                    self.game_cls.id if self.game_cls else "",
                    self.game_cls.name if self.game_cls else "",
                    list(msg.get("rows") or []))
                self.phase = "result"
                self.phase_t = 0.0
                self.app.audio.play("fanfare")
                self._build_widgets()
            elif t == "pt_over":
                self.tour.totals = {int(r["pid"]): int(r["points"])
                                    for r in (msg.get("standings") or [])}
                self.phase = "over"
                self.app.audio.play("fanfare")
                self._applause_t = 0.9
                self._build_widgets()
            elif t == "__disconnect__":
                self.message = "Verbindung zum Host verloren."
                self._to_menu()
                return

    def _broadcast_live(self, dt):
        self._live_acc += dt
        if self._live_acc < 0.35 or self.game is None:
            return
        self._live_acc = 0.0
        rows = {str(k): v for k, v in self.game.live_rows().items()}
        if self.is_host:
            for k, v in rows.items():
                self.live[int(k)] = v
            if self.host:
                self.host.broadcast({"type": "pt_live", "i": self.tour.index,
                                     "rows": {str(k): v for k, v in self.live.items()}})
        elif self.client:
            self.client.send({"type": "pt_live", "i": self.tour.index, "rows": rows})

    def _sync_authoritative(self, dt):
        if self.game is None or not self.game.authoritative:
            return
        if self.is_host:
            self._net_acc += dt
            if self._net_acc >= 1 / 30.0 and self.host:
                self._net_acc = 0.0
                st = self.game.net_state()
                if st is not None:
                    self.host.broadcast({"type": "pt_state", "s": st})
        elif self.client:
            payload = self.game.net_input()
            if payload:
                payload["type"] = "pt_input"
                self.client.send(payload)

    # ================================================================== #
    #  Hauptschleife
    # ================================================================== #
    def handle_events(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self._to_menu()
                return
            if self.phase in ("result", "over"):
                for w in self.widgets:
                    if w.handle_event(e):
                        break
                if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._advance_from_result()
                    return
        if self.phase == "play" and self.game is not None:
            self.game.handle_events(events)

    def update(self, dt):
        self.phase_t += dt
        self._pump_host()
        self._pump_client()
        self._client_watchdog(dt)

        if self._applause_t > 0:
            self._applause_t -= dt
            if self._applause_t <= 0:
                self.app.audio.play("applause")

        if self.phase == "intro":
            if self.game is not None:
                left = int(max(0.0, self.game.intro_seconds - self.phase_t)) + 1
                if left != self._tick_left:
                    self._tick_left = left
                    self.app.audio.play("countdown")
            if self.is_host and self.game is not None:
                if self.phase_t >= self.game.intro_seconds:
                    if self.host:
                        self.host.broadcast({"type": "pt_go"})
                    self._begin_play()
        elif self.phase == "play" and self.game is not None:
            self.game.update(dt)
            self._sync_authoritative(dt)
            self._broadcast_live(dt)
            if self.game.finished:
                self.phase = "wait"
                self.phase_t = 0.0
                self._send_report()
                if self.is_host and not self._wait_started:
                    self._wait_started = time.time()
        elif self.phase == "wait":
            if self.is_host:
                self._try_close_game()
        elif self.phase == "result":
            if self.is_host and self.phase_t > 12.0:
                self._advance_from_result()

    def _client_watchdog(self, dt):
        """Client: nachfragen, wenn Spielansage oder Startschuss fehlen.

        Ohne das bleibt ein Mitspieler ewig vor einem leeren Bildschirm sitzen,
        falls eine Nachricht beim Szenenwechsel verlorenging.
        """
        if self.is_host or not self.client:
            return
        stuck = self.game is None
        if not stuck and self.phase == "intro" and self.game_cls is not None:
            stuck = self.phase_t > self.game_cls.intro_seconds + 2.5
        if not stuck:
            return
        self._resync_t -= dt
        if self._resync_t <= 0:
            self._resync_t = 1.2
            self.client.send({"type": "pt_need_game"})

    def _advance_from_result(self):
        if not self.is_host:
            return
        self.app.audio.play("click")
        if self.tour.index + 1 >= len(self.tour.order):
            self._finish_tournament()
        else:
            self._start_game(self.tour.index + 1)

    def _to_menu(self):
        from .menu import MenuScene

        if self.beacon:
            self.beacon.stop()
        if self.host:
            self.host.stop()
        if self.client:
            self.client.close()
        self.app.set_scene(MenuScene(self.app))

    # ================================================================== #
    #  Anzeige
    # ================================================================== #
    def _build_widgets(self):
        w, h = self.app.screen.get_size()
        self.widgets = []
        if self.phase == "result" and self.is_host:
            last = self.tour.index + 1 >= len(self.tour.order)
            self.widgets.append(Button((w // 2 - 150, h - 74, 300, 48),
                                       "Endstand" if last else "Weiter",
                                       self._advance_from_result, "primary"))
        elif self.phase == "over":
            self.widgets.append(Button((w // 2 - 150, h - 74, 300, 48),
                                       "Zum Hauptmenue", self._to_menu, "primary"))

    def draw(self, surf):
        U.backdrop(surf)
        self._draw_header(surf)
        side = self.side_rect()
        if side:
            U.leaderboard(surf, self.app.fonts, side, self._standing_rows(),
                          heading="Jetzt" if self.phase == "play" else "Gesamt",
                          compact=len(self.players) > 8)

        if self.phase == "intro" and self.game_cls is None:
            self._draw_waiting(surf)
        elif self.phase == "intro":
            self._draw_intro(surf)
        elif self.phase == "play" and self.game is not None:
            self.game.draw(surf)
        elif self.phase == "wait":
            self._draw_wait(surf)
        elif self.phase == "result":
            self._draw_result(surf)
        elif self.phase == "over":
            self._draw_over(surf)

        for wd in self.widgets:
            wd.draw(surf, self.app.fonts)

    def _standing_rows(self):
        rows = self.tour.standings()
        if self.phase != "play":
            return rows
        # Waehrend eines Minispiels nach dem LAUFENDEN Stand sortieren - man
        # soll jederzeit sehen, ob man gerade vorn liegt, nicht nur wie das
        # Turnier insgesamt steht.
        seen = False
        for r in rows:
            v = self.live.get(r["pid"])
            if v is not None:
                r["value"] = (self.game_cls.live_label(v)
                              if self.game_cls else str(v))
                seen = True
        if not seen:
            return rows
        scoring = self.game_cls.scoring if self.game_cls else "high"
        sign = -1.0 if scoring == "high" else 1.0
        rows.sort(key=lambda r: (self.live.get(r["pid"]) is None,
                                 sign * float(self.live.get(r["pid"], 0.0))))
        for i, r in enumerate(rows):
            r["place"] = i + 1
        return rows

    def _draw_header(self, surf):
        w, _h = surf.get_size()
        fonts = self.app.fonts
        pygame.draw.rect(surf, U.PANEL, (0, 0, w, HEADER_H))
        pygame.draw.line(surf, U.LINE, (0, HEADER_H), (w, HEADER_H), 2)
        name = self.game_cls.name if self.game_cls else "Turnier"
        draw_text(surf, fonts.display(26), name, U.TEXT, (PAD + 4, 12))
        total = max(1, len(self.tour.order))
        sub = "Spiel %d von %d" % (min(self.tour.index + 1, total), total)
        draw_text(surf, fonts.body(15), sub, U.MUTED, (PAD + 6, 46))
        # Fortschrittspunkte
        x = w // 2 - total * 9
        for i in range(total):
            col = U.ACCENT if i <= self.tour.index else U.LINE
            pygame.draw.circle(surf, col, (x + i * 18, HEADER_H // 2), 5)
        draw_text(surf, fonts.body(14), "ESC = beenden", U.MUTED, (w - 130, 28))

    def _draw_waiting(self, surf):
        area = self.play_rect()
        fonts = self.app.fonts
        U.title(surf, fonts, "Warte auf den Host ...", area.centery - 40,
                center_x=area.centerx)
        U.subtitle(surf, fonts, "Das naechste Minispiel wird gleich verteilt.",
                   area.centery + 20, center_x=area.centerx)

    def _draw_intro(self, surf):
        area = self.play_rect()
        fonts = self.app.fonts
        cls = self.game_cls
        if cls is None:
            return
        U.title(surf, fonts, cls.name, area.y + 40, size=54, center_x=area.centerx)
        U.subtitle(surf, fonts, cls.rules, area.y + 112, size=20, center_x=area.centerx)

        left = max(0.0, (cls.intro_seconds - self.phase_t))
        U.countdown_number(surf, fonts, max(1, int(left) + 1),
                           (area.centerx, area.y + 230))

        if cls.input_mode == "mouse":
            U.subtitle(surf, fonts, "Maus - jeder ist einzeln dran",
                       area.y + 320, size=18, center_x=area.centerx)
        else:
            self._draw_key_hint(surf, area, area.y + 316)

    def _draw_key_hint(self, surf, area, y):
        fonts = self.app.fonts
        locals_ = [p for p in self.players if p.is_local and not p.is_bot]
        if not locals_:
            return
        n = len(locals_)
        cw = min(240, max(150, (area.w - 16 * (n - 1)) // n))
        x = area.centerx - (cw * n + 14 * (n - 1)) // 2
        for p in locals_:
            b = self.bindings.get(p.pid)
            draw_text(surf, fonts.body_bold(15), U.fit(fonts.body_bold(15), p.name, cw),
                      p.color, (x, y))
            if b:
                kw = (cw - 16) // 3
                for i in range(3):
                    U.key_cap(surf, fonts, (x + i * (kw + 8), y + 24, kw, 46),
                              key_name(b[i]))
            x += cw + 14

    def _draw_wait(self, surf):
        area = self.play_rect()
        fonts = self.app.fonts
        U.title(surf, fonts, "Auswertung ...", area.centery - 40, center_x=area.centerx)
        U.subtitle(surf, fonts, "warte auf die anderen Spieler",
                   area.centery + 20, center_x=area.centerx)

    def _draw_result(self, surf):
        area = self.play_rect()
        fonts = self.app.fonts
        rec = self.record
        U.title(surf, fonts, "Ergebnis", area.y + 10, size=40, center_x=area.centerx)
        if rec is None:
            return
        U.subtitle(surf, fonts, rec.game_name, area.y + 62, center_x=area.centerx)

        rows = sorted(rec.rows, key=lambda r: r.get("place", 99))
        top = area.y + 104
        row_h = min(56, max(34, (area.bottom - top - 90) // max(1, len(rows))))
        wdt = min(560, area.w - 40)
        x = area.centerx - wdt // 2
        for i, r in enumerate(rows):
            box = pygame.Rect(x, top + i * (row_h + 4), wdt, row_h)
            if box.bottom > area.bottom - 80:
                break
            p = next((q for q in self.players if q.pid == r["pid"]), None)
            place = r.get("place", 0)
            U.panel(surf, box, color=U.PANEL_HI if place <= 3 else U.PANEL, radius=12)
            pc = U.PLACE_COLORS[place - 1] if 1 <= place <= 3 else U.MUTED
            draw_text(surf, fonts.display(20), str(place), pc, (box.x + 14, box.centery - 12))
            if p:
                pygame.draw.circle(surf, p.color, (box.x + 54, box.centery), 8)
                draw_text(surf, fonts.body_bold(17), U.fit(fonts.body_bold(17), p.name, 200),
                          U.TEXT, (box.x + 72, box.centery - 10))
            draw_text(surf, fonts.body(14), str(r.get("detail", "")), U.MUTED,
                      (box.x + 300, box.centery - 8))
            pts = fonts.display(20).render("+%d" % r.get("points", 0), True, U.OK)
            surf.blit(pts, pts.get_rect(midright=(box.right - 16, box.centery)))

    def _draw_over(self, surf):
        area = self.play_rect()
        fonts = self.app.fonts
        rows = self.tour.standings()
        U.title(surf, fonts, "Turnier beendet!", area.y + 20, size=50, center_x=area.centerx)
        if rows:
            win = rows[0]
            p = next((q for q in self.players if q.pid == win["pid"]), None)
            col = p.color if p else U.GOLD
            U.title(surf, fonts, "%s gewinnt mit %d Punkten" % (win["name"], win["points"]),
                    area.y + 90, size=28, color=col, center_x=area.centerx)
        board = pygame.Rect(area.centerx - 240, area.y + 150, 480,
                            min(area.h - 240, 60 + 44 * len(rows)))
        U.leaderboard(surf, fonts, board, rows, heading="Endstand")
