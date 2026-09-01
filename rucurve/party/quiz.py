"""Gemeinsame Basis fuer alle Multiple-Choice-Minispiele.

Jede Frage hat genau DREI Antworten - passend zu den drei Tasten jedes Spielers
(Links / Aktion / Rechts). Jede Frage laeuft feste `per_question` Sekunden, auf
jeder Maschine exakt gleich lang; wer frueher antwortet, sammelt Zeitvorteil
fuer den Gleichstand.
"""

from __future__ import annotations

import random

import pygame

from ..ui.widgets import draw_text
from . import ui as U
from .base import MiniGame


class QuizGame(MiniGame):
    input_mode = "keys"
    scoring = "high"
    per_question = 5.0
    n_questions = 10

    # -- von Unterklassen zu fuellen ------------------------------------
    @staticmethod
    def make_question(rng, index):
        """Liefert dict mit prompt, options (3 Strings), correct (0..2)."""
        raise NotImplementedError

    def draw_question(self, surf, area, q):
        """Optional ueberschreiben: grafische Darstellung der Frage."""
        img = self.ctx.fonts.display(46).render(str(q["prompt"]), True, U.TEXT)
        surf.blit(img, img.get_rect(center=(area.centerx, area.centery)))

    # ------------------------------------------------------------------ #
    @classmethod
    def make_config(cls, rng, players):
        return {
            "per_question": cls.per_question,
            "questions": [cls.make_question(rng, i) for i in range(cls.n_questions)],
            "bot_seed": rng.randrange(1 << 30),
        }

    def __init__(self, ctx):
        super().__init__(ctx)
        self.questions = list(self.cfg.get("questions", []))
        self.per_q = float(self.cfg.get("per_question", self.per_question))
        self.max_seconds = self.per_q * len(self.questions) + 1.0
        self.q_index = 0
        self.q_time = 0.0
        self.answers: dict[int, int] = {}
        self.correct: dict[int, int] = {pid: 0 for pid in ctx.local_pids}
        self.spent: dict[int, float] = {pid: 0.0 for pid in ctx.local_pids}
        self.flash: dict[int, list] = {}
        self._bot_plan = self._plan_bots()

    # -- Bots -----------------------------------------------------------
    def _plan_bots(self):
        rng = random.Random(self.cfg.get("bot_seed", 1))
        plan = {}
        for p in self.ctx.local_players:
            if not p.is_bot:
                continue
            d = max(0.0, min(1.0, p.difficulty))
            plan[p.pid] = [
                (rng.uniform(0.6, 0.9 + 2.6 * (1 - d)), rng.random() < 0.25 + 0.7 * d)
                for _ in self.questions
            ]
        return plan

    def _bot_update(self):
        for pid, plan in self._bot_plan.items():
            if pid in self.answers or self.q_index >= len(plan):
                continue
            delay, right = plan[self.q_index]
            if self.q_time >= min(delay, self.per_q - 0.15):
                q = self.questions[self.q_index]
                pick = q["correct"] if right else (q["correct"] + 1 + pid % 2) % 3
                self._answer(pid, pick)

    # -- Ablauf ---------------------------------------------------------
    @property
    def question(self):
        if 0 <= self.q_index < len(self.questions):
            return self.questions[self.q_index]
        return None

    def handle_events(self, events):
        if self.question is None:
            return
        for e in events:
            if e.type != pygame.KEYDOWN:
                continue
            for pid, btn in self.pressed_buttons(e.key):
                if pid not in self.answers:
                    self._answer(pid, btn)

    def _answer(self, pid, btn):
        q = self.question
        if q is None:
            return
        self.answers[pid] = btn
        self.spent[pid] = self.spent.get(pid, 0.0) + self.q_time
        hit = btn == q["correct"]
        if hit:
            self.correct[pid] = self.correct.get(pid, 0) + 1
        self.flash[pid] = [U.OK if hit else U.BAD, 0.45]
        p = self.ctx.player(pid)
        if p is not None and not p.is_bot:
            self.ctx.play("correct" if hit else "wrong")

    def update(self, dt):
        super().update(dt)
        if self.finished:
            return
        self.q_time += dt
        self._bot_update()
        for pid in list(self.flash):
            self.flash[pid][1] -= dt
            if self.flash[pid][1] <= 0:
                del self.flash[pid]

        if self.q_time >= self.per_q:
            for pid in self.ctx.local_pids:
                if pid not in self.answers:
                    self.spent[pid] = self.spent.get(pid, 0.0) + self.per_q
            self.answers.clear()
            self.q_index += 1
            self.q_time = 0.0
            if self.q_index >= len(self.questions):
                self.finish()

    def finish(self):
        for pid in self.ctx.local_pids:
            r = self.results_map[pid]
            r.raw = self.correct.get(pid, 0)
            r.time = round(self.spent.get(pid, 0.0), 3)
            r.detail = "%d/%d" % (r.raw, len(self.questions))
        super().finish()

    def live_rows(self):
        return {pid: self.correct.get(pid, 0) for pid in self.ctx.local_pids}

    # -- Anzeige --------------------------------------------------------
    def draw(self, surf):
        area = self.ctx.area
        fonts = self.ctx.fonts
        q = self.question
        if q is None:
            return

        draw_text(surf, fonts.body(16),
                  "Frage %d von %d" % (self.q_index + 1, len(self.questions)),
                  U.MUTED, (area.x + 4, area.y))
        U.timer_bar(surf, (area.x, area.y + 26, area.w, 10),
                    1.0 - self.q_time / self.per_q)

        qarea = pygame.Rect(area.x, area.y + 52, area.w, area.h - 232)
        self.draw_question(surf, qarea, q)
        self._draw_options(surf, area, q)
        draw_local_strip(self, surf, area)

    def _draw_options(self, surf, area, q):
        fonts = self.ctx.fonts
        gap = 16
        w = min(250, (area.w - 2 * gap) // 3)
        total = 3 * w + 2 * gap
        x0 = area.centerx - total // 2
        y = area.bottom - 172
        for i, opt in enumerate(q["options"]):
            box = pygame.Rect(x0 + i * (w + gap), y, w, 78)
            U.panel(surf, box, color=U.PANEL_HI, border=U.LINE, radius=14)
            img = fonts.display(30).render(str(opt), True, U.TEXT)
            surf.blit(img, img.get_rect(center=(box.centerx, box.centery - 7)))
            lbl = U.BTN_LABEL[i]
            tw = fonts.body(12).size(lbl)[0]
            draw_text(surf, fonts.body(12), lbl, U.MUTED,
                      (box.centerx - tw // 2, box.bottom - 24))


def draw_local_strip(game, surf, area, value_fn=None, sub_fn=None):
    """Kartenreihe der Spieler an DIESEM Rechner - unten im Spielbereich."""
    fonts = game.ctx.fonts
    locals_ = game.ctx.local_players
    if not locals_:
        draw_text(surf, fonts.body(15), "Du schaust zu", U.MUTED,
                  (area.centerx - 50, area.bottom - 40))
        return
    n = len(locals_)
    cw = min(200, max(112, (area.w - 12 * (n - 1)) // n))
    x = area.centerx - (cw * n + 10 * (n - 1)) // 2
    y = area.bottom - 76
    for p in locals_:
        box = pygame.Rect(x, y, cw, 50)
        answered = p.pid in getattr(game, "answers", {})
        flash = game.flash.get(p.pid) if hasattr(game, "flash") else None
        border = flash[0] if flash else (p.color if answered else None)
        U.panel(surf, box, color=U.PANEL_HI if answered or flash else U.PANEL,
                border=border, radius=12)
        pygame.draw.rect(surf, p.color, (box.x, box.y + 6, 4, box.h - 12), border_radius=2)
        draw_text(surf, fonts.body_bold(14),
                  U.fit(fonts.body_bold(14), p.name, cw - 66), U.TEXT,
                  (box.x + 12, box.y + 7))
        sub = sub_fn(p) if sub_fn else "%d richtig" % game.correct.get(p.pid, 0)
        draw_text(surf, fonts.body(12), sub, U.MUTED, (box.x + 12, box.y + 28))
        val = value_fn(p) if value_fn else ("OK" if answered else "")
        if val:
            img = fonts.display(17).render(str(val), True, U.OK if val == "OK" else U.TEXT)
            surf.blit(img, img.get_rect(midright=(box.right - 12, box.centery)))
        x += cw + 10
