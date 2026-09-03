"""Drei schnelle Geschicklichkeitsspiele - alle nur mit den drei Spielertasten.

Reaktion, Merken (Simon) und Haemmern. Fuer das direkte Gegeneinander sind
die Arenaspiele in `sumo.py`, `tag.py`, `harvest.py`, `race.py` und
`curve_game.py` zustaendig.
"""

from __future__ import annotations

import math
import random

import pygame

from ...ui.widgets import draw_text, key_name
from .. import ui as U
from ..base import MiniGame


def _keycaps(game, surf, area, highlight=None, pressed=None):
    """Zeigt fuer jeden lokalen Spieler seine drei echten Tasten."""
    fonts = game.ctx.fonts
    locals_ = [p for p in game.ctx.local_players if not p.is_bot]
    if not locals_:
        return
    n = len(locals_)
    cw = max(84, min(230, (area.w - 20 - 12 * (n - 1)) // n))
    x = area.centerx - (cw * n + 12 * (n - 1)) // 2
    y = area.bottom - 104
    for p in locals_:
        binding = game.ctx.bindings.get(p.pid, (0, 0, 0))
        draw_text(surf, fonts.body_bold(14),
                  U.fit(fonts.body_bold(14), p.name, cw), p.color, (x, y - 22))
        kw = (cw - 16) // 3
        for i in range(3):
            r = pygame.Rect(x + i * (kw + 8), y, kw, 52)
            hot = highlight is not None and i == highlight
            down = pressed is not None and (p.pid, i) in pressed
            U.key_cap(surf, fonts, r, key_name(binding[i]),
                      color=(p.color if hot else U.PANEL_HI),
                      text_color=(10, 12, 20) if hot else U.TEXT,
                      pressed=down, glow=p.color if hot else None)
        x += cw + 12


# =========================================================================== #
class ReactionGame(MiniGame):
    id = "reaction"
    name = "Reaktion"
    rules = "Sobald eine Taste aufleuchtet: druecke genau diese! Zu frueh zaehlt als Fehler."
    input_mode = "keys"
    scoring = "low"                  # weniger Sekunden ist besser
    rounds = 6
    penalty = 1.6

    @staticmethod
    def make_config(rng, players):
        return {
            "rounds": [
                {"delay": round(rng.uniform(1.1, 3.0), 2), "btn": rng.randrange(3)}
                for _ in range(ReactionGame.rounds)
            ],
            "bot_seed": rng.randrange(1 << 30),
        }

    def __init__(self, ctx):
        super().__init__(ctx)
        self.rounds_cfg = self.cfg.get("rounds", [])
        self.max_seconds = sum(r["delay"] for r in self.rounds_cfg) + 3.0 * len(self.rounds_cfg) + 2
        self.idx = 0
        self.t = 0.0
        self.times: dict[int, list] = {pid: [] for pid in ctx.local_pids}
        self.done_round: dict[int, float] = {}
        self.pressed = set()
        rng = random.Random(self.cfg.get("bot_seed", 7))
        self._bot_rt = {
            p.pid: [max(0.13, rng.gauss(0.55 - 0.32 * p.difficulty, 0.09))
                    for _ in self.rounds_cfg]
            for p in ctx.local_players if p.is_bot
        }

    @property
    def round_cfg(self):
        if 0 <= self.idx < len(self.rounds_cfg):
            return self.rounds_cfg[self.idx]
        return None

    @property
    def signal_on(self):
        rc = self.round_cfg
        return rc is not None and self.t >= rc["delay"]

    def handle_events(self, events):
        rc = self.round_cfg
        if rc is None:
            return
        for e in events:
            if e.type == pygame.KEYDOWN:
                for pid, btn in self.pressed_buttons(e.key):
                    self._press(pid, btn)
            elif e.type == pygame.KEYUP:
                for pid, btn in self.pressed_buttons(e.key):
                    self.pressed.discard((pid, btn))

    def _press(self, pid, btn):
        rc = self.round_cfg
        if rc is None or pid in self.done_round:
            return
        self.pressed.add((pid, btn))
        if not self.signal_on or btn != rc["btn"]:
            self.done_round[pid] = self.penalty          # Fehlstart / falsche Taste
            self.ctx.play("wrong")
        else:
            self.done_round[pid] = max(0.0, self.t - rc["delay"])
            self.ctx.play("correct")

    def update(self, dt):
        super().update(dt)
        if self.finished:
            return
        rc = self.round_cfg
        if rc is None:
            self.finish()
            return
        self.t += dt

        if self.signal_on:
            since = self.t - rc["delay"]
            for pid, rts in self._bot_rt.items():
                if pid not in self.done_round and since >= rts[self.idx]:
                    self._press(pid, rc["btn"])

        everyone = all(pid in self.done_round for pid in self.ctx.local_pids)
        timeout = self.signal_on and (self.t - rc["delay"]) > 2.2
        if (everyone and self.ctx.local_pids) or timeout:
            for pid in self.ctx.local_pids:
                self.times[pid].append(self.done_round.get(pid, self.penalty))
            self.done_round.clear()
            self.pressed.clear()
            self.idx += 1
            self.t = 0.0
            if self.idx >= len(self.rounds_cfg):
                self.finish()

    def finish(self):
        for pid in self.ctx.local_pids:
            vals = self.times.get(pid) or [self.penalty]
            avg = sum(vals) / len(vals)
            r = self.results_map[pid]
            r.raw = round(avg, 4)
            r.time = round(avg, 4)
            r.detail = "%.2f s" % avg
        super().finish()

    def live_rows(self):
        out = {}
        for pid in self.ctx.local_pids:
            vals = self.times.get(pid) or []
            out[pid] = round(sum(vals) / len(vals), 3) if vals else 0.0
        return out

    def draw(self, surf):
        area = self.ctx.area
        fonts = self.ctx.fonts
        rc = self.round_cfg
        draw_text(surf, fonts.body(16), "Runde %d von %d" % (self.idx + 1, len(self.rounds_cfg)),
                  U.MUTED, (area.x + 4, area.y))
        cy = area.y + area.h // 2 - 90
        if rc is None:
            return
        if not self.signal_on:
            U.title(surf, fonts, "Achtung ...", cy - 30, size=52, color=U.MUTED, center_x=area.centerx)
            U.subtitle(surf, fonts, "noch nicht druecken", cy + 34, center_x=area.centerx)
        else:
            label = U.BTN_LABEL[rc["btn"]]
            U.title(surf, fonts, "JETZT!", cy - 40, size=68, color=U.OK, center_x=area.centerx)
            U.subtitle(surf, fonts, label, cy + 36, size=24, color=U.TEXT, center_x=area.centerx)
        _keycaps(self, surf, area, highlight=rc["btn"] if self.signal_on else None,
                 pressed=self.pressed)


# =========================================================================== #
class SequenceGame(MiniGame):
    id = "sequence"
    name = "Merken"
    rules = "Merke dir die Reihenfolge der Tasten und druecke sie nach. Es wird immer laenger."
    input_mode = "keys"
    scoring = "high"
    max_level = 8

    @staticmethod
    def make_config(rng, players):
        return {"seq": [rng.randrange(3) for _ in range(SequenceGame.max_level)],
                "bot_seed": rng.randrange(1 << 30)}

    SHOW_STEP = 0.62
    PAUSE = 0.55

    def __init__(self, ctx):
        super().__init__(ctx)
        self.seq = list(self.cfg.get("seq", [0, 1, 2]))
        self.level = 1
        self.phase = "show"
        self.t = 0.0
        self.input_pos: dict[int, int] = {}
        self.alive = {pid: True for pid in ctx.local_pids}
        self.reached = {pid: 0 for pid in ctx.local_pids}
        self.spent = {pid: 0.0 for pid in ctx.local_pids}
        self.pressed = set()
        self.max_seconds = 120.0
        rng = random.Random(self.cfg.get("bot_seed", 3))
        self._bot_fail = {
            p.pid: max(2, int(round(rng.gauss(2.5 + 5.0 * p.difficulty, 1.2))))
            for p in ctx.local_players if p.is_bot
        }
        self._bot_delay = {p.pid: rng.uniform(0.18, 0.5) for p in ctx.local_players if p.is_bot}
        self._bot_t = {}

    @property
    def show_len(self):
        return self.level * self.SHOW_STEP + self.PAUSE

    @property
    def input_len(self):
        return 1.0 + 0.6 * self.level

    def _shown_index(self):
        if self.phase != "show":
            return None
        i = int(self.t / self.SHOW_STEP)
        if i >= self.level:
            return None
        return i if (self.t % self.SHOW_STEP) < self.SHOW_STEP * 0.65 else None

    def handle_events(self, events):
        if self.phase != "input":
            return
        for e in events:
            if e.type == pygame.KEYDOWN:
                for pid, btn in self.pressed_buttons(e.key):
                    self._press(pid, btn)
            elif e.type == pygame.KEYUP:
                for pid, btn in self.pressed_buttons(e.key):
                    self.pressed.discard((pid, btn))

    def _press(self, pid, btn):
        if not self.alive.get(pid) or self.input_pos.get(pid, 0) >= self.level:
            return
        self.pressed.add((pid, btn))
        pos = self.input_pos.get(pid, 0)
        if self.seq[pos] == btn:
            self.input_pos[pid] = pos + 1
            self.ctx.play("click")
            if self.input_pos[pid] >= self.level:
                self.reached[pid] = self.level
                self.spent[pid] += self.t
        else:
            self.alive[pid] = False
            self.ctx.play("wrong")

    def update(self, dt):
        super().update(dt)
        if self.finished:
            return
        self.t += dt

        if self.phase == "show":
            if self.t >= self.show_len:
                self.phase = "input"
                self.t = 0.0
                self.input_pos = {pid: 0 for pid in self.ctx.local_pids}
                self._bot_t = {}
            return

        # Bots tippen die Folge nach, bis zu ihrem Koennens-Level
        for pid, fail_at in self._bot_fail.items():
            if not self.alive.get(pid) or self.input_pos.get(pid, 0) >= self.level:
                continue
            nxt = self._bot_t.get(pid, self._bot_delay[pid])
            if self.t >= nxt:
                pos = self.input_pos.get(pid, 0)
                right = self.level <= fail_at
                btn = self.seq[pos] if right else (self.seq[pos] + 1) % 3
                self._press(pid, btn)
                self._bot_t[pid] = self.t + self._bot_delay[pid]

        done = all(not self.alive.get(pid) or self.input_pos.get(pid, 0) >= self.level
                   for pid in self.ctx.local_pids)
        if (done and self.ctx.local_pids) or self.t >= self.input_len:
            for pid in self.ctx.local_pids:
                if self.alive.get(pid) and self.input_pos.get(pid, 0) < self.level:
                    self.alive[pid] = False
            self.level += 1
            self.phase = "show"
            self.t = 0.0
            self.pressed.clear()
            if self.level > min(self.max_level, len(self.seq)) or not any(self.alive.values()):
                self.finish()

    def finish(self):
        for pid in self.ctx.local_pids:
            r = self.results_map[pid]
            r.raw = self.reached.get(pid, 0)
            r.time = round(self.spent.get(pid, 0.0), 3)
            r.detail = "Stufe %d" % r.raw
        super().finish()

    def live_rows(self):
        return {pid: self.reached.get(pid, 0) for pid in self.ctx.local_pids}

    def draw(self, surf):
        area = self.ctx.area
        fonts = self.ctx.fonts
        draw_text(surf, fonts.body(16), "Stufe %d" % self.level, U.MUTED, (area.x + 4, area.y))
        cy = area.y + area.h // 2 - 110
        if self.phase == "show":
            U.title(surf, fonts, "Merken", cy - 20, size=46, color=U.MUTED, center_x=area.centerx)
            shown = self._shown_index()
            boxes = min(self.level, 12)
            bw = 54
            x0 = area.centerx - (boxes * bw + (boxes - 1) * 10) // 2
            for i in range(boxes):
                r = pygame.Rect(x0 + i * (bw + 10), cy + 48, bw, 54)
                on = shown == i
                U.panel(surf, r, color=U.ACCENT if on else U.PANEL_HI,
                        border=U.TEXT if on else U.LINE, radius=12)
                if on:
                    img = fonts.display(26).render(U.BTN_SHORT[self.seq[i]], True, U.TEXT)
                    surf.blit(img, img.get_rect(center=r.center))
            _keycaps(self, surf, area,
                     highlight=self.seq[shown] if shown is not None else None)
        else:
            U.title(surf, fonts, "Nachdruecken!", cy - 20, size=46, color=U.OK, center_x=area.centerx)
            U.timer_bar(surf, (area.centerx - 180, cy + 44, 360, 10),
                        1.0 - self.t / self.input_len)
            _keycaps(self, surf, area, pressed=self.pressed)


# =========================================================================== #
class MashGame(MiniGame):
    id = "mash"
    name = "Haemmern"
    rules = "Haemmere so schnell du kannst auf deine drei Tasten!"
    input_mode = "keys"
    scoring = "high"
    play_seconds = 8.0

    @staticmethod
    def make_config(rng, players):
        return {"seconds": MashGame.play_seconds, "bot_seed": rng.randrange(1 << 30)}

    def __init__(self, ctx):
        super().__init__(ctx)
        self.seconds = float(self.cfg.get("seconds", self.play_seconds))
        self.max_seconds = self.seconds + 0.2
        self.count = {pid: 0 for pid in ctx.local_pids}
        self.bump = {pid: 0.0 for pid in ctx.local_pids}
        rng = random.Random(self.cfg.get("bot_seed", 5))
        self._bot_rate = {p.pid: 3.2 + 5.6 * p.difficulty + rng.uniform(-0.6, 0.6)
                          for p in ctx.local_players if p.is_bot}
        self._bot_acc = {pid: 0.0 for pid in self._bot_rate}

    def handle_events(self, events):
        for e in events:
            if e.type != pygame.KEYDOWN:
                continue
            for pid, _btn in self.pressed_buttons(e.key):
                self.count[pid] = self.count.get(pid, 0) + 1
                self.bump[pid] = 0.18

    def update(self, dt):
        super().update(dt)
        if self.finished:
            return
        for pid, rate in self._bot_rate.items():
            self._bot_acc[pid] += dt * rate
            while self._bot_acc[pid] >= 1.0:
                self._bot_acc[pid] -= 1.0
                self.count[pid] = self.count.get(pid, 0) + 1
                self.bump[pid] = 0.15
        for pid in list(self.bump):
            self.bump[pid] = max(0.0, self.bump[pid] - dt)
        if self.elapsed >= self.seconds:
            self.finish()

    def finish(self):
        for pid in self.ctx.local_pids:
            r = self.results_map[pid]
            r.raw = self.count.get(pid, 0)
            r.time = 0.0
            r.detail = "%d Schlaege" % r.raw
        super().finish()

    def live_rows(self):
        return dict(self.count)

    def draw(self, surf):
        area = self.ctx.area
        fonts = self.ctx.fonts
        left = max(0.0, self.seconds - self.elapsed)
        U.title(surf, fonts, "%.1f s" % left, area.y + 6, size=44,
                color=U.BAD if left < 3 else U.TEXT, center_x=area.centerx)
        U.timer_bar(surf, (area.centerx - 220, area.y + 66, 440, 12),
                    left / self.seconds)

        locals_ = self.ctx.local_players
        if not locals_:
            return
        n = len(locals_)
        bw = min(150, max(80, (area.w - 20 * (n - 1)) // n))
        x = area.centerx - (bw * n + 18 * (n - 1)) // 2
        base_y = area.bottom - 90
        top = area.y + 110
        best = max([self.count.get(p.pid, 0) for p in locals_] + [1])
        for p in locals_:
            c = self.count.get(p.pid, 0)
            h = int((base_y - top) * min(1.0, c / max(best, 1)))
            bar = pygame.Rect(x, base_y - h, bw, max(4, h))
            pygame.draw.rect(surf, p.color, bar, border_radius=10)
            scale = 1.0 + self.bump.get(p.pid, 0.0)
            img = fonts.display(int(30 * scale)).render(str(c), True, U.TEXT)
            surf.blit(img, img.get_rect(midbottom=(bar.centerx, bar.y - 6)))
            draw_text(surf, fonts.body_bold(14),
                      U.fit(fonts.body_bold(14), p.name, bw), U.MUTED,
                      (bar.centerx - fonts.body_bold(14).size(U.fit(fonts.body_bold(14), p.name, bw))[0] // 2,
                       base_y + 10))
            x += bw + 18
