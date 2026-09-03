"""Die vier Multiple-Choice-Minispiele: Kopfrechnen, Flaechen, Schaetzen,
Ausreisser finden. Alle nutzen QuizGame und damit die drei Spielertasten.

Jedes Spiel liefert seine Aufgaben in vier Schwierigkeitsstufen (0 = leicht,
3 = schwer). Welche Stufe gerade gilt, entscheidet der Host nach der
Trefferquote aller Spieler - siehe `party/quiz.py`.
"""

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
        delta = rng.choice([-1, 1]) * rng.randint(1, max(1, int(spread)))
        cand = correct + delta
        if lo is not None and cand < lo:
            continue
        opts.add(int(cand) if as_int else round(cand, 1))
    while len(opts) < 3:
        opts.add(correct + len(opts))
    out = list(opts)
    rng.shuffle(out)
    return [str(o) for o in out], out.index(correct)


def _spread_choices(rng, correct, rel, lo=1):
    """Ablenker in RELATIVEM Abstand - je groesser `rel`, desto leichter.

    Fuers Schaetzen: bei "wie viele Punkte" nuetzen dicht beieinander
    liegende Zahlen nichts, man kann sie nicht auseinanderhalten.

    Zwei Dinge sind dabei wichtig:
      * Die richtige Zahl darf **nicht immer die mittlere** der drei sein.
        Sonst braucht man gar nicht zu schaetzen - man nimmt den Wert in der
        Mitte und liegt jedes Mal richtig.
      * Bei kleinen Zahlen ist unter der richtigen wenig Platz. Der zweite
        Schritt ist deshalb kleiner als der erste, damit "beide darunter"
        auch dann noch geht und nicht immer die Mitte uebrigbleibt.
    """
    gap = max(2, int(round(correct * rel)))
    step = max(2, int(round(gap * 0.7)))

    shapes = ["mitte", "oben"]
    if correct - gap - step >= lo:
        shapes.append("unten")
    shape = rng.choice(shapes)

    if shape == "unten":                 # richtig ist die groesste Zahl
        out = [correct, correct - gap, correct - gap - step]
    elif shape == "oben":                # richtig ist die kleinste Zahl
        out = [correct, correct + gap, correct + gap + step]
    else:                                # richtig liegt dazwischen
        out = [correct, max(lo, correct - gap), correct + gap]

    out = sorted(set(out))
    while len(out) < 3:                  # Notnagel bei winzigen Zahlen
        out.append(out[-1] + max(2, gap))
    out = out[:3]
    rng.shuffle(out)
    return [str(o) for o in out], out.index(correct)


# =========================================================================== #
class MathQuiz(QuizGame):
    goal = ("Zehn Rechenaufgaben, je fuenf Sekunden. Unten stehen drei "
            "Antworten - jede liegt auf einer deiner drei Tasten.")
    key_help = ("linke Antwort", "mittlere Antwort", "rechte Antwort")
    id = "math"
    name = "Kopfrechnen"
    rules = "10 Aufgaben, je 5 Sekunden. Antworte mit deinen drei Tasten."
    n_questions = 10

    @staticmethod
    def make_question(rng, index, level):
        # Untergrenzen wachsen mit: sonst wuerfelt auch die hoechste Stufe
        # noch "3 x 2" und die Stufe waere nicht zu spueren.
        if level <= 0:
            op = rng.choice("+++--x")
            lo, hi, lo_mul, mul = 3, 15, 2, 5
        elif level == 1:
            op = rng.choice("++--xx:")
            lo, hi, lo_mul, mul = 8, 60, 3, 9
        elif level == 2:
            op = rng.choice("+--xxx::")
            lo, hi, lo_mul, mul = 20, 140, 6, 13
        else:
            op = rng.choice("-xxx::22")           # 2 = zweischrittig
            lo, hi, lo_mul, mul = 40, 240, 8, 19

        if op == "+":
            a, b = rng.randint(lo, hi), rng.randint(lo, hi)
            val, txt = a + b, "%d + %d" % (a, b)
        elif op == "-":
            a, b = rng.randint(lo + 5, hi + 10), rng.randint(lo, hi)
            a, b = max(a, b), min(a, b)
            val, txt = a - b, "%d - %d" % (a, b)
        elif op == "x":
            a, b = rng.randint(lo_mul, mul), rng.randint(lo_mul, mul)
            val, txt = a * b, "%d x %d" % (a, b)
        elif op == ":":
            b = rng.randint(2 + level, 4 + level * 3)
            val = rng.randint(3 + level * 2, 6 + level * 6)
            txt = "%d : %d" % (val * b, b)
        else:                                     # zwei Schritte
            a, b = rng.randint(6, 15), rng.randint(4, 9)
            c = rng.randint(8, 60)
            if rng.random() < 0.5:
                val, txt = a * b + c, "%d x %d + %d" % (a, b, c)
            else:
                val, txt = a * b - c, "%d x %d - %d" % (a, b, c)

        spread = max(2, abs(val) // (6 - level) + 2)
        options, correct = _choices(rng, val, spread, lo=min(0, val))
        return {"prompt": txt + " = ?", "options": options, "correct": correct}


# =========================================================================== #
class AreaQuiz(QuizGame):
    goal = ("Wie gross ist die Flaeche der gezeigten Form? Rechteck, "
            "Quadrat und Dreieck - ganz oben auch der Kreis, dann steht die "
            "Formel dabei.")
    key_help = ("linke Antwort", "mittlere Antwort", "rechte Antwort")
    id = "area"
    name = "Flaecheninhalt"
    rules = "Wie gross ist die Flaeche? 10 Aufgaben, je 5 Sekunden."
    n_questions = 10

    @staticmethod
    def make_question(rng, index, level):
        # Der Kreis kommt bewusst erst auf der hoechsten Stufe vor - mit Pi im
        # Kopf zu rechnen ist ein ganz anderes Kaliber als Laenge mal Breite.
        if level <= 0:
            kinds, hi = ["rect", "square"], 9
        elif level == 1:
            kinds, hi = ["rect", "rect", "square", "tri"], 12
        elif level == 2:
            kinds, hi = ["rect", "tri", "tri", "square"], 18
        else:
            kinds, hi = ["rect", "tri", "circle", "circle"], 22

        kind = rng.choice(kinds)
        hint = ""
        if kind == "rect":
            a, b = rng.randint(3, hi), rng.randint(3, max(3, hi - 2))
            val, prompt, dims = a * b, "Rechteck  %d x %d" % (a, b), [a, b]
        elif kind == "square":
            a = rng.randint(3, hi)
            val, prompt, dims = a * a, "Quadrat  Seite %d" % a, [a, a]
        elif kind == "tri":
            g, h = rng.randint(4, hi), rng.randint(3, max(3, hi - 4))
            if (g * h) % 2:
                g += 1
            val, prompt, dims = g * h // 2, "Dreieck  g=%d  h=%d" % (g, h), [g, h]
        else:
            r = rng.randint(2, 6)
            val = round(math.pi * r * r)
            prompt = "Kreis  r=%d" % r
            hint = "A = Pi mal r hoch 2   (Pi ist rund 3,14)"
            dims = [r, r]

        # Beim Kreis liegen die Antworten weit auseinander: gut schaetzen soll
        # reichen, genau rechnen ist in 5 Sekunden nicht drin.
        spread = max(3, val // 2) if kind == "circle" else max(3, val // 5 + 2)
        options, correct = _choices(rng, val, spread, lo=1)
        return {"prompt": prompt, "options": options, "correct": correct,
                "kind": kind, "dims": dims, "hint": hint}

    def draw_question(self, surf, area, q):
        fonts = self.ctx.fonts
        draw_text(surf, fonts.display(28), q["prompt"], U.TEXT,
                  (area.centerx - fonts.display(28).size(q["prompt"])[0] // 2, area.y + 4))
        hint = q.get("hint")
        top = area.y + 40
        if hint:
            img = fonts.body(15).render(hint, True, U.GOLD)
            surf.blit(img, img.get_rect(midtop=(area.centerx, top)))
            top += 24
        box = pygame.Rect(0, 0, min(300, area.w - 40), min(190, area.h - 60))
        box.center = (area.centerx, top + 12 + box.h // 2)
        kind = q.get("kind", "rect")
        dims = q.get("dims", [4, 3])
        col = U.ACCENT
        if kind in ("rect", "square"):
            a, b = dims
            scale = min(box.w / max(a, 1), box.h / max(b, 1)) * 0.85
            r = pygame.Rect(0, 0, int(a * scale), int(b * scale))
            r.center = box.center
            pygame.draw.rect(surf, U.PANEL_HI, r)
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
    goal = ("Wie viele Punkte liegen auf dem Feld? Vier Sekunden pro Bild - "
            "genau zaehlen schafft niemand, es geht um die Groessenordnung.")
    key_help = ("linke Antwort", "mittlere Antwort", "rechte Antwort")
    id = "estimate"
    name = "Schaetzen"
    rules = "Wie viele Punkte siehst du? 8 Aufgaben, je 4 Sekunden."
    n_questions = 8
    per_question = 4.0

    # Wie weit die Antworten auseinanderliegen (Anteil der richtigen Zahl).
    # Grosszuegig, denn Punkte im Feld zaehlt in 4 Sekunden niemand genau -
    # geschaetzt werden soll die Groessenordnung.
    # Abstand der Antworten (Anteil der richtigen Zahl). Grosszuegig, denn
    # Punkte zaehlt in vier Sekunden niemand genau - geschaetzt werden soll
    # die Groessenordnung. Auf Stufe 0 bewusst nicht groesser: bei ueber 50 %
    # passen keine zwei Ablenker mehr UNTER die richtige Zahl, und dann waere
    # die richtige nie die groesste der drei.
    SPREAD = (0.45, 0.38, 0.30, 0.24)
    RANGES = ((8, 16), (12, 25), (20, 38), (30, 55))

    @classmethod
    def make_question(cls, rng, index, level):
        lo, hi = cls.RANGES[max(0, min(3, level))]
        n = rng.randint(lo, hi)
        options, correct = _spread_choices(rng, n, cls.SPREAD[max(0, min(3, level))])
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
    goal = ("Ein Feld im Raster hat eine andere Farbe als alle anderen. In "
            "welchem Drittel liegt es? Die Einteilung wechselt zwischen "
            "senkrecht und waagerecht - schau auf die Trennlinien.")
    key_help = ("erstes Drittel", "zweites Drittel", "drittes Drittel")
    id = "oddone"
    name = "Ausreisser finden"
    rules = "Ein Feld hat eine andere Farbe. In welchem Drittel liegt es?"
    n_questions = 8
    per_question = 4.0

    ROWS = (3, 4, 5, 7)
    COLS = (6, 9, 9, 12)
    DIFF = (62, 42, 26, 15)          # Farbunterschied - kleiner = schwerer
    # Die Einteilung wechselt: mal senkrecht, mal waagerecht. Sonst schaut
    # man nach ein paar Runden nur noch auf drei feste Spalten.
    SPLITS = (("senkrecht", ("links", "mitte", "rechts")),
              ("waagerecht", ("oben", "mitte", "unten")))

    @classmethod
    def make_question(cls, rng, index, level):
        lv = max(0, min(3, level))
        cols, rows = cls.COLS[lv], cls.ROWS[lv]
        split, labels = rng.choice(cls.SPLITS)
        if split == "waagerecht" and rows < 3:
            split, labels = cls.SPLITS[0]
        third = rng.randint(0, 2)
        if split == "senkrecht":
            step = cols // 3
            cx = rng.randrange(third * step, min(cols, (third + 1) * step))
            cy = rng.randrange(rows)
        else:
            step = rows // 3
            cy = rng.randrange(third * step, min(rows, (third + 1) * step))
            cx = rng.randrange(cols)
        base = rng.randrange(12)
        return {"prompt": "Wo ist das andere Feld?",
                "options": list(labels), "correct": third,
                "cols": cols, "rows": rows, "cx": cx, "cy": cy,
                "split": split, "base": base, "diff": cls.DIFF[lv]}

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
        if q.get("split", "senkrecht") == "senkrecht":
            for i in range(1, 3):
                x = box.x + i * (box.w // 3)
                pygame.draw.line(surf, U.LINE, (x, box.y - 6), (x, box.bottom + 6), 2)
        else:
            for i in range(1, 3):
                y = box.y + i * (box.h // 3)
                pygame.draw.line(surf, U.LINE, (box.x - 6, y), (box.right + 6, y), 2)
