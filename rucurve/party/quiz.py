"""Gemeinsame Basis fuer alle Multiple-Choice-Minispiele.

Jede Frage hat genau DREI Antworten - passend zu den drei Tasten jedes Spielers
(Links / Aktion / Rechts). Jede Frage laeuft feste `per_question` Sekunden, auf
jeder Maschine exakt gleich lang.

**Tempo zaehlt.** Eine richtige Antwort bringt nicht einfach einen Punkt,
sondern zwischen MAX_POINTS (sofort) und MIN_POINTS (kurz vor Ablauf) - wer
schneller ist, gewinnt also auch bei gleich vielen richtigen Antworten klar.
Eine falsche Antwort bringt nichts und laesst sich nicht korrigieren.

**Die Aufgaben passen sich an.** Der Host wuerfelt zu jedem Aufgabenplatz
gleich alle LEVELS Schwierigkeitsstufen aus und schickt sie an alle. Welche
Stufe gilt, entscheidet allein der Host anhand der Trefferquote *aller*
Spieler - so bekommt jeder immer dieselbe Aufgabe. Lief es gut, wird die
naechste schwerer; lief es schlecht, leichter.

Damit die Entscheidung rechtzeitig ueberall ankommt, wird die Stufe fuer
Aufgabe i+1 schon beim START von Aufgabe i festgelegt und danach ~3x pro
Sekunde mitgeschickt - eine ganze Aufgabenlaenge Vorlauf.
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
    live_unit = " Pkt"
    MAX_POINTS = 100     # sofort geantwortet
    # Muss ueber der Haelfte von MAX_POINTS liegen: sonst waere eine einzige
    # blitzschnelle Antwort mehr wert als zwei richtige, nur langsame.
    MIN_POINTS = 55      # in letzter Sekunde geantwortet

    LEVELS = 4           # Stufe 0 = am leichtesten, 3 = am schwersten
    START_LEVEL = 1
    UP_AT = 0.70         # ab dieser Trefferquote wird die naechste schwerer
    DOWN_AT = 0.34       # darunter wieder leichter

    # -- von Unterklassen zu fuellen ------------------------------------
    @staticmethod
    def make_question(rng, index, level):
        """Liefert dict mit prompt, options (3 Strings), correct (0..2).

        `level` laeuft von 0 (leicht) bis LEVELS-1 (schwer).
        """
        raise NotImplementedError

    def draw_question(self, surf, area, q):
        """Optional ueberschreiben: grafische Darstellung der Frage."""
        img = self.ctx.fonts.display(46).render(str(q["prompt"]), True, U.TEXT)
        surf.blit(img, img.get_rect(center=(area.centerx, area.centery)))

    # ------------------------------------------------------------------ #
    @classmethod
    def make_config(cls, rng, players):
        # Zu jedem Platz gleich ALLE Stufen mitschicken - dann kostet ein
        # Stufenwechsel spaeter keine Nachricht mit Aufgabendaten mehr.
        ladder = [[cls.make_question(rng, i, lv) for lv in range(cls.LEVELS)]
                  for i in range(cls.n_questions)]
        return {
            "per_question": cls.per_question,
            "ladder": ladder,
            "bot_seed": rng.randrange(1 << 30),
        }

    def __init__(self, ctx):
        super().__init__(ctx)
        self.ladder = [list(row) for row in self.cfg.get("ladder", [])]
        self.n_slots = len(self.ladder)
        self.levels = [self.START_LEVEL] * self.n_slots
        # pid -> Zeichenkette wie "1011", ein Zeichen je erledigter Aufgabe.
        # Der Host sammelt hier auch die Meldungen der Clients ein.
        self.hits = {}
        self._decided_upto = 0
        self.per_q = float(self.cfg.get("per_question", self.per_question))
        self.max_seconds = self.per_q * self.n_slots + 1.0
        self.q_index = 0
        self.q_time = 0.0
        self.answers: dict[int, int] = {}
        self.correct: dict[int, int] = {pid: 0 for pid in ctx.local_pids}
        self.points: dict[int, float] = {pid: 0.0 for pid in ctx.local_pids}
        self.gained: dict[int, int] = {}      # Punkte der letzten Antwort (Anzeige)
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
                for _ in range(self.n_slots)
            ]
        return plan

    def _bot_update(self):
        for pid, plan in self._bot_plan.items():
            if pid in self.answers or self.q_index >= len(plan):
                continue
            delay, right = plan[self.q_index]
            if self.q_time >= min(delay, self.per_q - 0.15):
                q = self.question
                pick = q["correct"] if right else (q["correct"] + 1 + pid % 2) % 3
                self._answer(pid, pick)

    # -- Schwierigkeitsstufe --------------------------------------------
    def level_of(self, slot):
        if 0 <= slot < len(self.levels):
            return max(0, min(self.LEVELS - 1, int(self.levels[slot])))
        return self.START_LEVEL

    def hit_rate(self, slot):
        """Trefferquote aller bekannten Spieler bei Aufgabe `slot`."""
        seen = hits = 0
        for record in self.hits.values():
            if slot < len(record):
                seen += 1
                hits += 1 if record[slot] == "1" else 0
        return (hits / seen) if seen else None

    def _decide_next_level(self):
        """Host: Stufe fuer die uebernaechste Aufgabe festlegen.

        Bewertet wird die Aufgabe VOR der laufenden - die ist sicher fertig,
        und der Vorlauf reicht, damit alle Clients die Stufe rechtzeitig haben.
        """
        target = self.q_index + 1
        if target >= self.n_slots or target <= self._decided_upto:
            return
        self._decided_upto = target
        judged = self.q_index - 1
        base = self.level_of(self.q_index)
        rate = self.hit_rate(judged) if judged >= 0 else None
        if rate is None:
            step = 0
        elif rate >= self.UP_AT:
            step = 1
        elif rate <= self.DOWN_AT:
            step = -1
        else:
            step = 0
        new = max(0, min(self.LEVELS - 1, base + step))
        for slot in range(target, self.n_slots):
            self.levels[slot] = new

    def _note_hit(self, pid, ok):
        record = self.hits.get(pid, "")
        record = record.ljust(self.q_index, "0")[:self.q_index]
        self.hits[pid] = record + ("1" if ok else "0")

    # -- Netz: Stufe nach unten, Trefferquote nach oben -----------------
    def net_live_down(self):
        return {"lv": list(self.levels)} if self.ctx.is_host else None

    def apply_live_down(self, data):
        levels = data.get("lv")
        if not isinstance(levels, list):
            return
        # Die LAUFENDE Aufgabe nie umstellen - nur was noch kommt.
        for slot in range(self.q_index + 1, min(len(levels), self.n_slots)):
            self.levels[slot] = int(levels[slot])

    def net_live_up(self):
        if self.ctx.is_host:
            return None
        return {"h": dict((str(pid), self.hits.get(pid, ""))
                          for pid in self.ctx.local_pids)}

    def apply_live_up(self, client_id, data):
        for pid, record in (data.get("h") or {}).items():
            if isinstance(record, str):
                self.hits[int(pid)] = record

    # -- Ablauf ---------------------------------------------------------
    @property
    def questions(self):
        """Die gerade gueltigen Aufgaben - je Platz die aktive Stufe."""
        return [row[self.level_of(i)] for i, row in enumerate(self.ladder)]

    @property
    def question(self):
        if 0 <= self.q_index < self.n_slots:
            return self.ladder[self.q_index][self.level_of(self.q_index)]
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

    def speed_points(self, t: float) -> int:
        """Punkte fuer eine richtige Antwort nach t Sekunden."""
        k = max(0.0, min(1.0, t / max(0.01, self.per_q)))
        return int(round(self.MAX_POINTS - (self.MAX_POINTS - self.MIN_POINTS) * k))

    def _answer(self, pid, btn):
        q = self.question
        if q is None:
            return
        self.answers[pid] = btn
        self.spent[pid] = self.spent.get(pid, 0.0) + self.q_time
        hit = btn == q["correct"]
        self._note_hit(pid, hit)
        gain = self.speed_points(self.q_time) if hit else 0
        if hit:
            self.correct[pid] = self.correct.get(pid, 0) + 1
            self.points[pid] = self.points.get(pid, 0.0) + gain
        self.gained[pid] = gain
        self.flash[pid] = [U.OK if hit else U.BAD, 0.45]
        p = self.ctx.player(pid)
        if p is not None and not p.is_bot:
            self.ctx.play("correct" if hit else "wrong")

    def update(self, dt):
        super().update(dt)
        if self.finished:
            return
        self.q_time += dt
        if self.ctx.is_host:
            self._decide_next_level()
        self._bot_update()
        for pid in list(self.flash):
            self.flash[pid][1] -= dt
            if self.flash[pid][1] <= 0:
                del self.flash[pid]

        if self.q_time >= self.per_q:
            for pid in self.ctx.local_pids:
                if pid not in self.answers:
                    self.spent[pid] = self.spent.get(pid, 0.0) + self.per_q
                    self._note_hit(pid, False)
            self.answers.clear()
            self.gained.clear()
            self.q_index += 1
            self.q_time = 0.0
            if self.q_index >= self.n_slots:
                self.finish()

    def finish(self):
        for pid in self.ctx.local_pids:
            r = self.results_map[pid]
            r.raw = round(self.points.get(pid, 0.0), 1)
            r.time = round(self.spent.get(pid, 0.0), 3)
            r.detail = "%d Pkt - %d/%d richtig" % (
                r.raw, self.correct.get(pid, 0), self.n_slots)
        super().finish()

    def live_rows(self):
        return {pid: self.points.get(pid, 0.0) for pid in self.ctx.local_pids}

    # -- Anzeige --------------------------------------------------------
    def draw(self, surf):
        area = self.ctx.area
        fonts = self.ctx.fonts
        q = self.question
        if q is None:
            return

        draw_text(surf, fonts.body(16),
                  "Frage %d von %d   -   Stufe %d" % (
                      self.q_index + 1, self.n_slots,
                      self.level_of(self.q_index) + 1),
                  U.MUTED, (area.x + 4, area.y))
        U.timer_bar(surf, (area.x, area.y + 26, area.w, 10),
                    1.0 - self.q_time / self.per_q)
        # Was eine richtige Antwort JETZT noch bringt - macht Tempo greifbar
        now = self.speed_points(self.q_time)
        img = fonts.body_bold(16).render("jetzt %d Punkte" % now, True,
                                         U.GOLD if now > 70 else U.MUTED)
        surf.blit(img, img.get_rect(topright=(area.right - 4, area.y)))

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
        if sub_fn:
            sub = sub_fn(p)
        else:
            sub = "%d Pkt" % round(getattr(game, "points", {}).get(p.pid, 0))
        draw_text(surf, fonts.body(12), sub, U.MUTED, (box.x + 12, box.y + 28))
        if value_fn:
            val = value_fn(p)
        elif answered:
            gain = getattr(game, "gained", {}).get(p.pid, 0)
            val = ("+%d" % gain) if gain else "-"
        else:
            val = ""
        if val:
            col = U.OK if str(val).startswith("+") else (U.BAD if val == "-" else U.TEXT)
            img = fonts.display(17).render(str(val), True, col)
            surf.blit(img, img.get_rect(midright=(box.right - 12, box.centery)))
        x += cw + 10
