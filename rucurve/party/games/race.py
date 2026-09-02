"""Ru-Rennen: ein Autorennen mit den drei Tasten.

Zweites Minispiel, bei dem der Host fuer alle rechnet (wie Achtung die Kurve):
alle fahren gleichzeitig auf derselben Strecke, rempeln sich gegenseitig und
sehen jederzeit, wer vorn liegt. Genau darum geht es hier - schneller als die
anderen zu sein, nicht nur "richtig".

Steuerung: linke/rechte Taste lenkt, die Aktionstaste gibt Schub (Tank leert
sich und fuellt sich langsam wieder). Neben der Strecke ist man deutlich
langsamer.

Die Simulation laeuft in einem festen Logikraum (LOGIC_W x LOGIC_H) und wird
erst beim Zeichnen auf den Bereich skaliert - so sehen alle Rechner dasselbe,
egal wie gross ihr Fenster ist.
"""

from __future__ import annotations

import math
import random

import pygame

from ...ui.widgets import draw_text
from .. import ui as U
from ..base import MiniGame, Result

LOGIC_W, LOGIC_H = 1600.0, 900.0
SAMPLES = 240                 # Stuetzpunkte der Mittellinie
TRACK_HALF = 88.0             # halbe Streckenbreite
LAPS = 2
TICK = 1.0 / 60.0

MAX_SPEED = 430.0             # px/s im Logikraum
GRASS_FACTOR = 0.50
ACCEL = 520.0
BRAKE = 900.0
# Wendekreis muss in die engste Kurve passen: bei Vollgas ist der Radius
# v / (TURN_RATE * 0.6) ~ 163 px, die engste Strecke hat ~150 px. Mit Schub
# reicht es bewusst NICHT - Schub gehoert auf die Gerade.
TURN_RATE = 4.4               # rad/s bei niedrigem Tempo
BOOST_FACTOR = 1.42
BOOST_MAX = 2.6               # Sekunden Tank
BOOST_REFILL = 0.42           # pro Sekunde
CAR_R = 24.0                  # Radius fuer Rempler
TOW_DIST = TRACK_HALF * 2.2   # so weit daneben gilt man als "von der Strecke"
TOW_AFTER = 2.0               # nach so vielen Sekunden zurueck auf die Bahn

ASPHALT = (44, 48, 62)
ASPHALT_HI = (54, 59, 76)
GRASS = (22, 40, 30)
KERB_A = (226, 78, 78)
KERB_B = (240, 240, 245)


# --------------------------------------------------------------------------- #
def _smooth(pts: list, passes: int = 3) -> list:
    """Gleitender Mittelwert - nimmt der Strecke die zu spitzen Ecken."""
    n = len(pts)
    for _ in range(passes):
        pts = [((pts[(i - 1) % n][0] + 2 * pts[i][0] + pts[(i + 1) % n][0]) / 4.0,
                (pts[(i - 1) % n][1] + 2 * pts[i][1] + pts[(i + 1) % n][1]) / 4.0)
               for i in range(n)]
    return pts


def _fit(pts: list, margin: float) -> list:
    """Strecke so stauchen und mittig legen, dass sie samt Rand ins Bild passt."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    k = min((LOGIC_W - 2 * margin) / max(1.0, w), (LOGIC_H - 2 * margin) / max(1.0, h))
    k = min(1.0, k)                      # nur verkleinern, nie aufblasen
    cx, cy = (max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0
    return [(LOGIC_W / 2 + (x - cx) * k, LOGIC_H / 2 + (y - cy) * k) for x, y in pts]


def min_curve_radius(pts: list) -> float:
    """Kleinster Kurvenradius der Mittellinie - muss deutlich ueber der halben
    Streckenbreite liegen, sonst schneidet sich die Innenkante selbst."""
    n = len(pts)
    best = 1e18
    for i in range(n):
        ax, ay = pts[(i - 2) % n]
        bx, by = pts[i]
        cx, cy = pts[(i + 2) % n]
        # Umkreisradius des Dreiecks a-b-c
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(d) < 1e-9:
            continue
        ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay)
              + (cx * cx + cy * cy) * (ay - by)) / d
        uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx)
              + (cx * cx + cy * cy) * (bx - ax)) / d
        best = min(best, math.hypot(bx - ux, by - uy))
    return best


def build_track(seed: int) -> list:
    """Geschlossene Mittellinie: verbeulte Ellipse, aus dem Seed reproduzierbar.

    Zu enge Varianten werden verworfen und neu gewuerfelt - eine Strecke, deren
    Innenkante sich selbst schneidet, waere unfahrbar.
    """
    rng = random.Random(seed)
    cx, cy = LOGIC_W * 0.5, LOGIC_H * 0.5
    # Grundform bewusst rund: eine flache Ellipse haette schon von sich aus
    # zu enge Scheitel, dann wuerde jede Wuerfelrunde flachgebuegelt.
    rx, ry = LOGIC_W * 0.33, LOGIC_H * 0.34
    best = None
    for attempt in range(24):
        amp1 = rng.uniform(0.09, 0.17) * (1.0 - attempt / 32.0)
        amp2 = rng.uniform(0.03, 0.07) * (1.0 - attempt / 32.0)
        waves = [(rng.randint(2, 3), rng.uniform(0, math.tau), amp1),
                 (rng.randint(4, 5), rng.uniform(0, math.tau), amp2)]
        pts = []
        for i in range(SAMPLES):
            a = i / SAMPLES * math.tau
            bump = 1.0
            for n, phase, amp in waves:
                bump += amp * math.sin(n * a + phase)
            pts.append((cx + math.cos(a) * rx * bump, cy + math.sin(a) * ry * bump))
        pts = _fit(_smooth(pts, 2), TRACK_HALF + 14.0)
        r = min_curve_radius(pts)
        if best is None or r > best[0]:
            best = (r, pts)
        if r > TRACK_HALF * 1.45:
            return pts
    return best[1]


def track_edges(center: list, half: float = TRACK_HALF):
    """Linke und rechte Streckenkante aus der Mittellinie."""
    n = len(center)
    left, right = [], []
    for i, (x, y) in enumerate(center):
        ax, ay = center[(i - 1) % n]
        bx, by = center[(i + 1) % n]
        dx, dy = bx - ax, by - ay
        d = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / d, dx / d
        left.append((x + nx * half, y + ny * half))
        right.append((x - nx * half, y - ny * half))
    return left, right


class RaceGame(MiniGame):
    id = "race"
    name = "Ru-Rennen"
    rules = ("Links/rechts lenken, Aktionstaste gibt Schub. %d Runden - "
             "neben der Strecke wirst du langsam, Rempler kosten Tempo." % LAPS)
    input_mode = "keys"
    scoring = "high"
    live_unit = " Rd"          # gefahrene Runden
    authoritative = True
    intro_seconds = 4.0
    max_seconds = 95.0

    @staticmethod
    def make_config(rng, players):
        return {"seed": rng.randrange(1 << 30), "laps": LAPS}

    # ------------------------------------------------------------------ #
    def __init__(self, ctx):
        super().__init__(ctx)
        self.seed = int(self.cfg.get("seed", 1))
        self.laps = int(self.cfg.get("laps", LAPS))
        self.center = build_track(self.seed)
        self.left_edge, self.right_edge = track_edges(self.center)
        self.cars: dict[int, dict] = {}
        self.sim_time = 0.0
        self._acc = 0.0
        self._remote_input: dict[int, tuple] = {}
        self._last_sent = None
        self._bot_rng = random.Random(self.seed ^ 0x5EED)
        self._crash_cool = 0.0
        self._scale = 1.0
        self._off = (0.0, 0.0)
        self._track_surf: pygame.Surface | None = None
        self._track_key = None
        self._build_cars()
        self._layout(ctx.area)

    def _build_cars(self):
        """Startaufstellung: gestaffelt hinter der Start-Ziel-Linie."""
        n = len(self.ctx.players)
        for i, p in enumerate(self.ctx.players):
            # eine Reihe pro zwei Autos, abwechselnd links/rechts versetzt
            back = (i // 2) * 78.0
            side = (-1 if i % 2 else 1) * TRACK_HALF * 0.48
            raw = -back / self._seg_len()
            idx = raw % SAMPLES
            x, y, head = self._pose_at(idx, side)
            # Wer hinter der Start-Ziel-Linie steht, faengt bei Runde -1 an -
            # sonst zaehlt schon das Ueberfahren der Linie beim Start als Runde.
            lap = -1 if raw < 0 else 0
            self.cars[p.pid] = {
                "x": x, "y": y, "h": head, "v": 0.0, "boost": BOOST_MAX,
                "idx": idx, "lap": lap, "prog": float(lap) + idx / SAMPLES,
                "fin": None, "bump": 0.0, "boosting": False, "lost": 0.0,
                # Bots fahren nach Schwierigkeit verhaltener
                "skill": (0.74 + 0.26 * max(0.0, min(1.0, p.difficulty))
                          if p.is_bot else 1.0),
            }

    def _seg_len(self) -> float:
        if not hasattr(self, "_slen"):
            total = 0.0
            n = len(self.center)
            for i in range(n):
                ax, ay = self.center[i]
                bx, by = self.center[(i + 1) % n]
                total += math.hypot(bx - ax, by - ay)
            self._slen = total / n
        return self._slen

    def _pose_at(self, idx: float, side: float = 0.0):
        """Punkt + Fahrtrichtung an der Stelle idx der Mittellinie."""
        n = len(self.center)
        i = int(idx) % n
        ax, ay = self.center[i]
        bx, by = self.center[(i + 1) % n]
        f = idx - math.floor(idx)
        x, y = ax + (bx - ax) * f, ay + (by - ay) * f
        head = math.atan2(by - ay, bx - ax)
        if side:
            x += math.cos(head + math.pi / 2) * side
            y += math.sin(head + math.pi / 2) * side
        return x, y, head

    # ------------------------------------------------------------------ #
    def _layout(self, area):
        self._scale = min(area.w / LOGIC_W, area.h / LOGIC_H)
        vw, vh = LOGIC_W * self._scale, LOGIC_H * self._scale
        self._off = (area.x + (area.w - vw) / 2, area.y + (area.h - vh) / 2)

    def on_resize(self, area):
        self._layout(area)
        self._track_surf = None

    def _to_screen(self, x, y):
        return (self._off[0] + x * self._scale, self._off[1] + y * self._scale)

    # -- Eingaben -------------------------------------------------------
    def handle_events(self, events):
        pass                       # Tasten werden pro Tick abgefragt

    def _read_local(self):
        keys = pygame.key.get_pressed()
        out = {}
        for pid in self.ctx.local_pids:
            b = self.ctx.bindings.get(pid)
            if not b:
                continue
            out[pid] = (bool(keys[b[0]]), bool(keys[b[2]]), bool(keys[b[1]]))
        return out

    def net_input(self):
        rows = [[pid, l, r, a] for pid, (l, r, a) in self._read_local().items()]
        if rows == self._last_sent:
            return None
        self._last_sent = [row[:] for row in rows]
        return {"in": rows}

    def apply_input(self, client_id, data):
        for row in data.get("in", []):
            try:
                pid, l, r, a = row
            except (TypeError, ValueError):
                continue
            self._remote_input[int(pid)] = (bool(l), bool(r), bool(a))

    # -- Simulation (nur Host) -----------------------------------------
    def update(self, dt):
        self.elapsed += dt
        if self.finished:
            return
        if not self.ctx.is_host:
            if self.elapsed >= self.max_seconds:
                self.finish()
            return

        inputs = dict(self._remote_input)
        inputs.update(self._read_local())
        self._acc += dt
        steps = 0
        while self._acc >= TICK and steps < 6:
            self._step(TICK, inputs)
            self._acc -= TICK
            steps += 1
        self._crash_cool = max(0.0, self._crash_cool - dt)
        if self.elapsed >= self.max_seconds or all(
                c["fin"] is not None for c in self.cars.values()):
            self.finish()

    def _step(self, dt, inputs):
        self.sim_time += dt
        for pid, car in self.cars.items():
            if car["fin"] is not None:
                car["v"] *= 0.96          # rollt aus
                self._advance(car, dt)
                continue
            p = self.ctx.player(pid)
            if p is not None and p.is_bot:
                l, r, a = self._bot_input(pid, car, p.difficulty)
            else:
                l, r, a = inputs.get(pid, (False, False, False))
            self._drive(car, dt, l, r, a)
            self._advance(car, dt)
            self._track_progress(pid, car)
            self._tow_if_lost(car, dt)
        self._bumps()

    def _drive(self, car, dt, left, right, action):
        on_track = self._distance_to_center(car) <= TRACK_HALF
        cap = MAX_SPEED * (1.0 if on_track else GRASS_FACTOR) * car.get("skill", 1.0)
        car["boosting"] = False
        if action and car["boost"] > 0.0 and on_track:
            cap *= BOOST_FACTOR
            car["boost"] = max(0.0, car["boost"] - dt)
            car["boosting"] = True
        else:
            car["boost"] = min(BOOST_MAX, car["boost"] + BOOST_REFILL * dt)

        if car["v"] < cap:
            car["v"] = min(cap, car["v"] + ACCEL * dt)
        else:
            car["v"] = max(cap, car["v"] - BRAKE * dt)

        # bei hohem Tempo lenkt es sich traeger - sonst waere Vollgas immer richtig
        agility = 0.60 + 0.40 * (1.0 - min(1.0, car["v"] / MAX_SPEED))
        turn = (1 if right else 0) - (1 if left else 0)
        car["h"] += turn * TURN_RATE * agility * dt

    def _advance(self, car, dt):
        car["x"] += math.cos(car["h"]) * car["v"] * dt
        car["y"] += math.sin(car["h"]) * car["v"] * dt
        car["x"] = max(4.0, min(LOGIC_W - 4.0, car["x"]))
        car["y"] = max(4.0, min(LOGIC_H - 4.0, car["y"]))
        car["bump"] = max(0.0, car["bump"] - dt)

    def _nearest_index(self, car) -> float:
        """Naechster Stuetzpunkt - nur im Fenster um die letzte Position gesucht."""
        n = len(self.center)
        best, best_d = car["idx"], 1e18
        base = int(car["idx"])
        for k in range(-14, 22):
            i = (base + k) % n
            px, py = self.center[i]
            d = (px - car["x"]) ** 2 + (py - car["y"]) ** 2
            if d < best_d:
                best_d, best = d, float(i)
        return best

    def _distance_to_center(self, car) -> float:
        i = int(self._nearest_index(car)) % len(self.center)
        px, py = self.center[i]
        return math.hypot(px - car["x"], py - car["y"])

    def _track_progress(self, pid, car):
        n = len(self.center)
        new = self._nearest_index(car)
        old = car["idx"]
        step = (new - old + n) % n
        if step > n / 2:                      # rueckwaerts - nicht werten
            car["idx"] = new
            return
        if old + step >= n:                   # Start-Ziel ueberfahren
            car["lap"] += 1
            if car["lap"] >= self.laps and car["fin"] is None:
                car["fin"] = self.sim_time
                self.ctx.play("whistle")
        car["idx"] = new
        car["prog"] = car["lap"] + new / n

    def _tow_if_lost(self, car, dt):
        """Wer sich weit verfaehrt, wird zurueck auf die Bahn gesetzt.

        Ohne das klebt jemand, der einmal in die Ecke gefahren ist, bis zum
        Rennende am Bildrand fest - das ist kein Spiel mehr.
        """
        if self._distance_to_center(car) > TOW_DIST:
            car["lost"] += dt
        else:
            car["lost"] = 0.0
            return
        if car["lost"] < TOW_AFTER:
            return
        x, y, head = self._pose_at(car["idx"])
        car["x"], car["y"], car["h"] = x, y, head
        car["v"] *= 0.35                  # Zeitverlust bleibt spuerbar
        car["lost"] = 0.0
        car["bump"] = 0.4

    def _bumps(self):
        """Rempler: schiebt auseinander, kostet aber nur bei echtem Aufprall Tempo.

        Wichtig: blosses Nebeneinanderfahren darf nicht bremsen - sonst kriecht
        ein ganzes Feld dauerhaft im Pulk, weil sich alle staendig beruehren.
        Tempo kostet es nur, wenn sich zwei wirklich aufeinander zubewegen.
        """
        pids = list(self.cars)
        for a in range(len(pids)):
            ca = self.cars[pids[a]]
            for b in range(a + 1, len(pids)):
                cb = self.cars[pids[b]]
                dx, dy = cb["x"] - ca["x"], cb["y"] - ca["y"]
                d = math.hypot(dx, dy)
                if d >= CAR_R * 2 or d < 1e-6:
                    continue
                ux, uy = dx / d, dy / d
                push = (CAR_R * 2 - d) / 2.0
                ca["x"] -= ux * push
                ca["y"] -= uy * push
                cb["x"] += ux * push
                cb["y"] += uy * push

                # Annaeherungstempo entlang der Beruehrungsachse
                avx, avy = math.cos(ca["h"]) * ca["v"], math.sin(ca["h"]) * ca["v"]
                bvx, bvy = math.cos(cb["h"]) * cb["v"], math.sin(cb["h"]) * cb["v"]
                closing = (avx - bvx) * ux + (avy - bvy) * uy
                if closing <= 12.0:
                    continue                  # nur streifen - kein Tempoverlust
                hit = min(1.0, closing / MAX_SPEED)
                # Wer auffaehrt, verliert mehr als der, auf den aufgefahren wird
                ca["v"] *= 1.0 - 0.28 * hit
                cb["v"] *= 1.0 - 0.12 * hit
                ca["bump"] = cb["bump"] = 0.25
                if self._crash_cool <= 0.0:
                    self._crash_cool = 0.3
                    self.ctx.play("crash")

    def _bot_input(self, pid, car, difficulty):
        """Zielt auf einen Punkt weiter vorn auf der Mittellinie und weicht aus."""
        d = max(0.0, min(1.0, difficulty))
        # Vorausschau am Tempo festmachen, nicht an der Schwierigkeit: sonst
        # schneiden die starken Bots die Kurven und landen im Gras.
        look = 4 + int(9 * min(1.0, car["v"] / MAX_SPEED))
        tx, ty, _ = self._pose_at(car["idx"] + look)
        # Vor mir jemand? Dann seitlich am Ziel vorbeizielen statt aufzufahren.
        for other_pid, oc in self.cars.items():
            if other_pid == pid:
                continue
            odx, ody = oc["x"] - car["x"], oc["y"] - car["y"]
            dist = math.hypot(odx, ody)
            if dist > 110.0 or dist < 1e-6:
                continue
            ahead = (math.cos(car["h"]) * odx + math.sin(car["h"]) * ody) / dist
            if ahead < 0.5:
                continue                       # steht neben oder hinter mir
            side = -math.sin(car["h"]) * odx + math.cos(car["h"]) * ody
            away = 1.0 if side < 0 else -1.0   # zur freien Seite ziehen
            dodge = 70.0 * (1.0 - dist / 110.0)
            tx += -math.sin(car["h"]) * away * dodge
            ty += math.cos(car["h"]) * away * dodge
        want = math.atan2(ty - car["y"], tx - car["x"])
        diff = (want - car["h"] + math.pi) % math.tau - math.pi
        dead = 0.16 * (1.4 - d)              # schwache Bots lenken unsauberer
        left = diff < -dead
        right = diff > dead
        boost = abs(diff) < 0.25 and car["boost"] > 0.6 and self._bot_rng.random() < 0.35 + 0.5 * d
        return left, right, boost

    # -- Netzwerk -------------------------------------------------------
    def net_state(self):
        return {
            "t": round(self.sim_time, 2),
            "c": [[pid, round(c["x"], 1), round(c["y"], 1), round(c["h"], 3),
                   round(c["v"], 1), c["lap"], round(c["boost"], 2),
                   round(c["prog"], 3), -1 if c["fin"] is None else round(c["fin"], 2),
                   1 if c["boosting"] else 0]
                  for pid, c in self.cars.items()],
        }

    def apply_state(self, d):
        self.sim_time = float(d.get("t", self.sim_time))
        for row in d.get("c", []):
            pid = int(row[0])
            car = self.cars.get(pid)
            if car is None:
                continue
            car["x"], car["y"], car["h"] = row[1], row[2], row[3]
            car["v"], car["lap"], car["boost"] = row[4], int(row[5]), row[6]
            car["prog"] = row[7]
            car["fin"] = None if row[8] < 0 else row[8]
            car["boosting"] = bool(row[9])

    # -- Ergebnis -------------------------------------------------------
    def finish(self):
        if self.ctx.is_host:
            for pid, car in self.cars.items():
                if car["fin"] is not None:
                    self.results_map[pid] = Result(
                        raw=float(self.laps), time=round(car["fin"], 3),
                        detail="Ziel %.1f s" % car["fin"], done=True)
                else:
                    done_laps = max(0.0, car["prog"])
                    self.results_map[pid] = Result(
                        raw=round(done_laps, 3), time=self.max_seconds,
                        detail="%.2f Runden" % done_laps, done=True)
        super().finish()

    def host_results(self):
        return self.results_map

    def live_rows(self):
        return {pid: round(c["prog"], 3) for pid, c in self.cars.items()}

    # -- Anzeige --------------------------------------------------------
    def _render_track(self, size):
        """Strecke einmal auf eine Flaeche malen - jeden Frame waere zu teuer."""
        key = (size, round(self._scale, 4), self.seed)
        if self._track_surf is not None and self._track_key == key:
            return self._track_surf
        surf = pygame.Surface(size).convert()
        surf.fill(GRASS)
        sc = self._scale
        ox = oy = 0.0

        def pt(p):
            return (p[0] * sc + ox, p[1] * sc + oy)

        outer = [pt(p) for p in self.left_edge]
        inner = [pt(p) for p in self.right_edge]
        pygame.draw.polygon(surf, ASPHALT, outer + inner[::-1])
        # Randstreifen rot/weiss - klassische Kerbs
        for edge in (self.left_edge, self.right_edge):
            for i in range(0, len(edge), 4):
                seg = [pt(edge[(i + k) % len(edge)]) for k in range(5)]
                col = KERB_A if (i // 4) % 2 == 0 else KERB_B
                pygame.draw.lines(surf, col, False, seg, max(2, int(6 * sc)))
        # Mittellinie gestrichelt
        for i in range(0, len(self.center), 8):
            seg = [pt(self.center[(i + k) % len(self.center)]) for k in range(4)]
            pygame.draw.lines(surf, ASPHALT_HI, False, seg, max(1, int(4 * sc)))
        # Start-Ziel-Linie karriert
        x0, y0, head = self._pose_at(0.0)
        nx, ny = math.cos(head + math.pi / 2), math.sin(head + math.pi / 2)
        cells = 10
        for c in range(cells):
            span = TRACK_HALF + 8
            f = (c / cells - 0.5) * 2 * span
            a = pt((x0 + nx * f, y0 + ny * f))
            b = pt((x0 + nx * (f + 2 * span / cells), y0 + ny * (f + 2 * span / cells)))
            col = (245, 245, 250) if c % 2 == 0 else (30, 30, 38)
            pygame.draw.line(surf, col, a, b, max(3, int(11 * sc)))
        self._track_surf = surf
        self._track_key = key
        return surf

    def _draw_car(self, surf, car, color, name, boosting):
        x, y = self._to_screen(car["x"], car["y"])
        sc = self._scale
        L, W = 46 * sc, 26 * sc
        h = car["h"]
        cos_h, sin_h = math.cos(h), math.sin(h)

        def corner(fx, fy):
            return (x + cos_h * fx - sin_h * fy, y + sin_h * fx + cos_h * fy)

        if boosting:                       # Schubflamme hinten
            flame = [corner(-L / 2, -W / 3), corner(-L / 2 - 16 * sc, 0),
                     corner(-L / 2, W / 3)]
            pygame.draw.polygon(surf, (255, 186, 74), flame)
        body = [corner(L / 2, 0), corner(L / 6, -W / 2), corner(-L / 2, -W / 2.3),
                corner(-L / 2, W / 2.3), corner(L / 6, W / 2)]
        pygame.draw.polygon(surf, color, body)
        pygame.draw.polygon(surf, (12, 14, 22), body, max(1, int(2 * sc)))
        # Cockpit
        pygame.draw.circle(surf, (14, 16, 26), corner(L * 0.04, 0), max(2, int(6.5 * sc)))
        if car["bump"] > 0:
            pygame.draw.circle(surf, (255, 255, 255), (int(x), int(y)),
                               int(CAR_R * sc + 4), 2)
        img = self.ctx.fonts.body_bold(12).render(name, True, U.TEXT)
        surf.blit(img, img.get_rect(midbottom=(x, y - 22 * sc)))

    def draw(self, surf):
        area = self.ctx.area
        sc = self._scale
        size = (max(1, int(LOGIC_W * sc)), max(1, int(LOGIC_H * sc)))
        surf.fill(GRASS, area)            # Rand des Bereichs auch begruenen
        surf.blit(self._render_track(size), (int(self._off[0]), int(self._off[1])))

        order = sorted(self.cars.items(), key=lambda kv: kv[1]["prog"])
        for pid, car in order:
            p = self.ctx.player(pid)
            self._draw_car(surf, car, p.color if p else (220, 220, 220),
                           p.name if p else "?", car["boosting"])

        self._draw_hud(surf, area)

    def _draw_hud(self, surf, area):
        fonts = self.ctx.fonts
        rows = sorted(self.cars.items(), key=lambda kv: -kv[1]["prog"])
        # Positionsliste oben links
        box = pygame.Rect(area.x + 8, area.y + 6, 218, 30 + 22 * min(8, len(rows)))
        U.panel(surf, box, color=U.PANEL, border=U.LINE, radius=12, alpha=215)
        draw_text(surf, fonts.body_bold(13), "Position", U.MUTED,
                  (box.x + 12, box.y + 7))
        y = box.y + 28
        for i, (pid, car) in enumerate(rows[:8]):
            p = self.ctx.player(pid)
            col = U.PLACE_COLORS[i] if i < 3 else U.TEXT
            pygame.draw.rect(surf, p.color if p else U.MUTED,
                             (box.x + 10, y + 5, 6, 10), border_radius=2)
            draw_text(surf, fonts.body_bold(13), "%d." % (i + 1), col, (box.x + 22, y))
            draw_text(surf, fonts.body(13),
                      U.fit(fonts.body(13), p.name if p else "?", 108), U.TEXT,
                      (box.x + 44, y))
            lap = max(1, min(self.laps, int(car["lap"]) + 1))
            draw_text(surf, fonts.body(12), "R%d" % lap, U.MUTED, (box.right - 30, y + 1))
            y += 22

        # Tank + Tempo der eigenen Spieler unten
        locals_ = [p for p in self.ctx.local_players if p.pid in self.cars]
        if not locals_:
            return
        n = len(locals_)
        cw = min(190, max(120, (area.w - 12 * (n - 1)) // n))
        x = area.centerx - (cw * n + 10 * (n - 1)) // 2
        y = area.bottom - 62
        for p in locals_:
            car = self.cars[p.pid]
            r = pygame.Rect(x, y, cw, 50)
            U.panel(surf, r, color=U.PANEL, border=p.color, radius=12, alpha=225)
            draw_text(surf, fonts.body_bold(13),
                      U.fit(fonts.body_bold(13), p.name, cw - 70), U.TEXT,
                      (r.x + 10, r.y + 5))
            draw_text(surf, fonts.body(12), "%d km/h" % int(car["v"] / 3), U.MUTED,
                      (r.x + 10, r.y + 30))
            U.timer_bar(surf, (r.x + 10, r.y + 24, cw - 20, 5),
                        car["boost"] / BOOST_MAX,
                        color=U.GOLD if car["boost"] > 0.2 else U.BAD)
            if car["fin"] is not None:
                draw_text(surf, fonts.body_bold(13), "Ziel!", U.OK,
                          (r.right - 44, r.y + 16))
            x += cw + 10
