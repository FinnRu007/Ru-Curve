"""Die vier Multiple-Choice-Minispiele: Kopfrechnen, Flaechen, Schaetzen,
Ausreisser finden. Alle nutzen QuizGame und damit die drei Spielertasten."""

from __future__ import annotations

import math
import random

import pygame

from ...ui.widgets import draw_text
from .. import ui as U
from ..quiz import QuizGame


def _choices(rng, correct, spread, lo=None, as_int=True):
    """Korrekte Antwort plus zwei plausible Ablenker, gemischt."""
    opts = {correct}
    guard = 0
    while len(opts) < 3 and guard < 200:
        guard += 1
        delta = rng.choice([-1, 1]) * rng.randint(1, max(1, spread))
        cand = correct + delta
        if lo is not None and cand < lo:
            continue
        opts.add(int(cand) if as_int else round(cand, 1))
    while len(opts) < 3:
        opts.add(correct + len(opts))
    out = list(opts)
    rng.shuffle(out)
    return [str(o) for o in out], out.index(correct)


# =========================================================================== #
class MathQuiz(QuizGame):
    id = "math"
    name = "Kopfrechnen"
    rules = "10 Aufgaben, je 5 Sekunden. Antworte mit deinen drei Tasten."
    n_questions = 10

    @staticmethod
    def make_question(rng, index):
        step = index / 9.0 if index else 0.0
        hi = int(10 + 40 * step)
        op = rng.choice("++-x" if index < 4 else "+-xx:")
        if op == "+":
            a, b = rng.randint(2, hi), rng.randint(2, hi)
            val, txt = a + b, "%d + %d" % (a, b)
        elif op == "-":
            a, b = rng.randint(5, hi + 10), rng.randint(2, hi)
            a, b = max(a, b), min(a, b)
            val, txt = a - b, "%d - %d" % (a, b)
        elif op == "x":
            a, b = rng.randint(2, 4 + int(9 * step)), rng.randint(2, 4 + int(9 * step))
            val, txt = a * b, "%d x %d" % (a, b)
        else:
            b = rng.randint(2, 9)
            val = rng.randint(2, 12)
            txt = "%d : %d" % (val * b, b)
        options, correct = _choices(rng, val, max(2, abs(val) // 4 + 2), lo=0)
        return {"prompt": txt + " = ?", "options": options, "correct": correct}


# =========================================================================== #
class AreaQuiz(QuizGame):
    id = "area"
    name = "Flaecheninhalt"
    rules = "Wie gross ist die Flaeche? 10 Aufgaben, je 5 Sekunden."
    n_questions = 10

    @staticmethod
    def make_question(rng, index):
        kind = rng.choice(["rect", "rect", "tri", "circle", "square"])
        if kind == "rect":
            a, b = rng.randint(3, 14), rng.randint(3, 12)
            val, prompt = a * b, "Rechteck  %d x %d" % (a, b)
            dims = [a, b]
        elif kind == "square":
            a = rng.randint(3, 13)
            val, prompt = a * a, "Quadrat  Seite %d" % a
            dims = [a, a]
        elif kind == "tri":
            g, h = rng.randint(4, 16), rng.randint(3, 12)
            if (g * h) % 2:
                g += 1
            val, prompt = g * h // 2, "Dreieck  g=%d  h=%d" % (g, h)
            dims = [g, h]
        else:
            r = rng.randint(2, 7)
            val = round(math.pi * r * r)
            prompt = "Kreis  r=%d  (auf ganze Zahl)" % r
            dims = [r, r]
        options, correct = _choices(rng, val, max(3, val // 5 + 2), lo=1)
        return {"prompt": prompt, "options": options, "correct": correct,
                "kind": kind, "dims": dims}

    def draw_question(self, surf, area, q):
        fonts = self.ctx.fonts
        draw_text(surf, fonts.display(28), q["prompt"], U.TEXT,
                  (area.centerx - fonts.display(28).size(q["prompt"])[0] // 2, area.y + 4))
        box = pygame.Rect(0, 0, min(300, area.w - 40), min(190, area.h - 60))
        box.center = (area.centerx, area.y + 52 + box.h // 2)
        kind = q.get("kind", "rect")
        dims = q.get("dims", [4, 3])
        col = U.ACCENT
        if kind in ("rect", "square"):
            a, b = dims
            scale = min(box.w / max(a, 1), box.h / max(b, 1)) * 0.85
            r = pygame.Rect(0, 0, int(a * scale), int(b * scale))
            r.center = box.center
            pygame.draw.rect(surf, (*col, 70) if False else U.PANEL_HI, r)
            pygame.draw.rect(surf, col, r, width=3)
            self._label(surf, "%d" % a, (r.centerx, r.bottom + 14))
            self._label(surf, "%d" % b, (r.left - 16, r.centery))
        elif kind == "tri":
            g, h = dims
            scale = min(box.w / max(g, 1), box.h / max(h, 1)) * 0.85
            gw, gh = int(g * scale), int(h * scale)
            x0 = box.centerx - gw // 2
            y0 = box.centery + gh // 2
            pts = [(x0, y0), (x0 + gw, y0), (x0 + gw // 3, y0 - gh)]
            pygame.draw.polygon(surf, U.PANEL_HI, pts)
            pygame.draw.polygon(surf, col, pts, 3)
            self._label(surf, "g=%d" % g, (box.centerx, y0 + 14))
            self._label(surf, "h=%d" % h, (x0 + gw // 3 + 26, y0 - gh // 2))
        else:
            r = dims[0]
            rad = int(min(box.w, box.h) * 0.42)
            pygame.draw.circle(surf, U.PANEL_HI, box.center, rad)
            pygame.draw.circle(surf, col, box.center, rad, 3)
            pygame.draw.line(surf, col, box.center,
                             (box.centerx + rad, box.centery), 2)
            self._label(surf, "r=%d" % r, (box.centerx + rad // 2, box.centery - 14))

    def _label(self, surf, text, center):
        img = self.ctx.fonts.body_bold(15).render(text, True, U.MUTED)
        surf.blit(img, img.get_rect(center=center))


# =========================================================================== #
class EstimateQuiz(QuizGame):
    id = "estimate"
    name = "Schaetzen"
    rules = "Wie viele Punkte siehst du? 8 Aufgaben, je 4 Sekunden."
    n_questions = 8
    per_question = 4.0

    @staticmethod
    def make_question(rng, index):
        n = rng.randint(9, 20 + index * 5)
        spread = max(3, n // 4)
        options, correct = _choices(rng, n, spread, lo=1)
        return {"prompt": "Wie viele Punkte?", "options": options,
                "correct": correct, "count": n, "seed": rng.randrange(1 << 30)}

    def __init__(self, ctx):
        super().__init__(ctx)
        self._dots_cache = {}

    def _dots(self, q, box):
        key = (q["seed"], box.w, box.h)
        pts = self._dots_cache.get(key)
        if pts is None:
            rng = random.Random(q["seed"])
            pts = []
            for _ in range(q["count"]):
                pts.append((rng.uniform(0.06, 0.94), rng.uniform(0.08, 0.92),
                            rng.randint(0, 5)))
            self._dots_cache = {key: pts}
        return pts

    def draw_question(self, surf, area, q):
        from ...colors import color_for

        box = pygame.Rect(area.x + 40, area.y + 6, area.w - 80, area.h - 20)
        U.panel(surf, box, color=(18, 21, 34), border=U.LINE, radius=14)
        r = max(5, min(box.w, box.h) // 34)
        for fx, fy, ci in self._dots(q, box):
            pygame.draw.circle(surf, color_for(ci),
                               (int(box.x + fx * box.w), int(box.y + fy * box.h)), r)


# =========================================================================== #
class OddOneQuiz(QuizGame):
    id = "oddone"
    name = "Ausreisser finden"
    rules = "Ein Feld hat eine andere Farbe. In welchem Drittel liegt es?"
    n_questions = 8
    per_question = 4.0

    @staticmethod
    def make_question(rng, index):
        cols = 9
        rows = 4 + min(3, index // 3)
        third = rng.randint(0, 2)
        cx = rng.randrange(third * (cols // 3), (third + 1) * (cols // 3))
        cy = rng.randrange(rows)
        base = rng.randrange(12)
        diff = max(46 - index * 4, 14)
        return {"prompt": "Wo ist das andere Feld?",
                "options": ["links", "mitte", "rechts"], "correct": third,
                "cols": cols, "rows": rows, "cx": cx, "cy": cy,
                "base": base, "diff": diff}

    def draw_question(self, surf, area, q):
        from ...colors import color_for

        cols, rows = q["cols"], q["rows"]
        box = pygame.Rect(0, 0, min(area.w - 60, cols * 74), min(area.h - 24, rows * 66))
        box.center = (area.centerx, area.centery)
        cw, ch = box.w // cols, box.h // rows
        base = color_for(q["base"])
        odd = tuple(max(0, min(255, c - q["diff"])) for c in base)
        for r in range(rows):
            for c in range(cols):
                cell = pygame.Rect(box.x + c * cw + 3, box.y + r * ch + 3, cw - 6, ch - 6)
                col = odd if (c == q["cx"] and r == q["cy"]) else base
                pygame.draw.rect(surf, col, cell, border_radius=8)
        for i in range(1, 3):
            x = box.x + i * (box.w // 3)
            pygame.draw.line(surf, U.LINE, (x, box.y - 6), (x, box.bottom + 6), 2)
