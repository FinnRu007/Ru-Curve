"""Zeichnet das Spielfeld: Trail-Surface + Koepfe + HUD + Effekte.

Das Feld fuellt (bis auf die HUD-Leiste oben) das ganze Fenster; auf grossen
Bildschirmen wird dadurch alles groesser dargestellt. Linien werden mit
anti-aliased Kreisen gestempelt. Von Host- und Client-Spielszene benutzt.
"""

from __future__ import annotations

import math

import pygame

from .. import theme as T
from ..ui.widgets import draw_text

try:
    _AAC = pygame.draw.aacircle
except AttributeError:  # sehr alte pygame-Version
    _AAC = None

_TOP = 66          # Hoehe der HUD-Leiste
_PAD = 14


def _disc(surf, color, x, y, r):
    if _AAC is not None and r >= 1.4:
        _AAC(surf, color, (x, y), r, 0)
    else:
        pygame.draw.circle(surf, color, (int(x), int(y)), max(1, int(round(r))))


def _ring(surf, color, x, y, r, w):
    if _AAC is not None and r >= 1.4:
        _AAC(surf, color, (x, y), r, w)
    else:
        pygame.draw.circle(surf, color, (int(x), int(y)), max(1, int(r)), w)


_glow_cache: dict[int, pygame.Surface] = {}
_hole_cache: dict[int, pygame.Surface] = {}


def _hole_mask(r: int) -> pygame.Surface:
    """Weicher Alpha-Kreis - wird per BLEND_RGBA_SUB aus dem Nebel gestanzt."""
    m = _hole_cache.get(r)
    if m is None:
        m = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        steps = 26
        for i in range(steps, 0, -1):
            rad = int(r * i / steps)
            a = int(255 * (1 - (i / steps) ** 2.2))
            pygame.draw.circle(m, (0, 0, 0, a), (r, r), rad)
        _hole_cache[r] = m
    return m


def _glow_mask(r: int) -> pygame.Surface:
    m = _glow_cache.get(r)
    if m is None:
        R = max(4, int(r * 3))
        m = pygame.Surface((R * 2, R * 2), pygame.SRCALPHA)
        for i in range(R, 0, -1):
            a = int(90 * (1 - i / R) ** 2)
            pygame.draw.circle(m, (255, 255, 255, a), (R, R), i)
        _glow_cache[r] = m
    return m


class ArenaView:
    def __init__(self, settings, screen_size: tuple[int, int]) -> None:
        self.aw = settings.arena_width
        self.ah = settings.arena_height
        sw, sh = screen_size
        avail_w = max(200, sw - 2 * _PAD)
        avail_h = max(200, sh - _TOP - 2 * _PAD)
        self.scale = min(avail_w / self.aw, avail_h / self.ah)
        self.view_w = max(1, int(self.aw * self.scale))
        self.view_h = max(1, int(self.ah * self.scale))
        self.ox = (sw - self.view_w) // 2
        self.oy = _TOP + _PAD + (avail_h - self.view_h) // 2
        self.surf = pygame.Surface((self.view_w, self.view_h)).convert()
        # wiederverwendete Flaechen fuer Nebel / Farbumkehr (nicht je Frame neu)
        self._fog_surf = pygame.Surface((self.view_w, self.view_h), pygame.SRCALPHA)
        self._invert_surf: pygame.Surface | None = None
        self._flashes: list[dict] = []
        self.reset()

    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        self.surf.fill(T.ARENA_BG)
        grid = (27, 30, 41)
        step = max(52, int(110 * self.scale))
        for gx in range(step, self.view_w, step):
            pygame.draw.line(self.surf, grid, (gx, 0), (gx, self.view_h), 1)
        for gy in range(step, self.view_h, step):
            pygame.draw.line(self.surf, grid, (0, gy), (self.view_w, gy), 1)
        # Vignette
        vg = pygame.Surface((self.view_w, self.view_h), pygame.SRCALPHA)
        band = max(24, int(min(self.view_w, self.view_h) * 0.14))
        for i in range(band):
            a = int(60 * (1 - i / band) ** 2)
            pygame.draw.rect(vg, (0, 0, 0, a), (i, i, self.view_w - 2 * i, self.view_h - 2 * i), 1)
        self.surf.blit(vg, (0, 0))

    # ------------------------------------------------------------------ #
    def apply_segments(self, segments, color_map: dict) -> None:
        s = self.scale
        for (cid, x0, y0, x1, y1, width, gap) in segments:
            if gap:
                continue
            col = color_map.get(cid, (200, 200, 200))
            r = max(1.0, width * s * 0.5)
            ax, ay, bx, by = x0 * s, y0 * s, x1 * s, y1 * s
            if r > 1.4:
                pygame.draw.line(self.surf, col, (ax, ay), (bx, by), int(r * 2))
            _disc(self.surf, col, bx, by, r)

    def add_flash(self, x: float, y: float, color) -> None:
        self._flashes.append({"x": x, "y": y, "color": color, "t0": pygame.time.get_ticks()})

    # ------------------------------------------------------------------ #
    def draw(self, target, render_curves: list[dict], fonts, *, countdown=0.0,
             round_no=1, phase="running", banner: str | None = None,
             inverted: bool = False, fog: float = 0.0, hint: str | None = None) -> None:
        target.fill(T.BG)

        shadow = pygame.Rect(self.ox - 6, self.oy - 4, self.view_w + 12, self.view_h + 16)
        pygame.draw.rect(target, (231, 233, 240), shadow, border_radius=16)
        frame = pygame.Rect(self.ox - 3, self.oy - 3, self.view_w + 6, self.view_h + 6)
        pygame.draw.rect(target, T.ARENA_BORDER, frame, border_radius=9)
        target.blit(self.surf, (self.ox, self.oy))

        s = self.scale
        self._draw_flashes(target)

        for rc in render_curves:
            if not rc.get("alive", True):
                continue
            x = self.ox + rc["x"] * s
            y = self.oy + rc["y"] * s
            col = rc["color"]
            rad = max(3.6, rc.get("width", 4) * s * 0.5 + 3.4)
            gm = _glow_mask(int(rad))
            tint = gm.copy()
            tint.fill((*col, 255), special_flags=pygame.BLEND_RGBA_MULT)
            target.blit(tint, (x - gm.get_width() / 2, y - gm.get_height() / 2),
                        special_flags=pygame.BLEND_RGBA_ADD)
            if rc.get("boost"):
                _ring(target, (255, 255, 255), x, y, rad + 5, 2)
            if rc.get("shield"):
                _ring(target, (235, 245, 255), x, y, rad + 8, 2)
            if rc.get("ghost"):
                _ring(target, col, x, y, rad, 2)
            elif rc.get("square"):
                sq = pygame.Rect(0, 0, rad * 1.9, rad * 1.9)
                sq.center = (x, y)
                pygame.draw.rect(target, col, sq)
                pygame.draw.rect(target, (255, 255, 255), sq, 1)
            else:
                _disc(target, col, x, y, rad)
                _ring(target, (255, 255, 255), x, y, rad, 1)
            h = rc.get("h", 0.0)
            pygame.draw.aaline(target, (255, 255, 255),
                               (x, y), (x + math.cos(h) * (rad + 7), y + math.sin(h) * (rad + 7)))

        if fog > 0:
            self._draw_fog(target, render_curves, fog)

        self._draw_hud(target, render_curves, fonts, round_no)

        if phase == "countdown":
            self._countdown(target, fonts, countdown)
        if banner:
            self._banner(target, fonts, banner)
        if hint:
            self._hint(target, fonts, hint)

        if inverted:
            if self._invert_surf is None or self._invert_surf.get_size() != target.get_size():
                self._invert_surf = pygame.Surface(target.get_size())
                self._invert_surf.fill((255, 255, 255))
            target.blit(self._invert_surf, (0, 0), special_flags=pygame.BLEND_RGB_SUB)

    # ------------------------------------------------------------------ #
    def _draw_flashes(self, target) -> None:
        now = pygame.time.get_ticks()
        s = self.scale
        alive = []
        for f in self._flashes:
            age = (now - f["t0"]) / 420.0
            if age >= 1.0:
                continue
            alive.append(f)
            x = self.ox + f["x"] * s
            y = self.oy + f["y"] * s
            rad = 6 + age * 46
            a = int(200 * (1 - age))
            ring = pygame.Surface((int(rad * 2) + 4, int(rad * 2) + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring, (*f["color"], a), ring.get_rect().center, int(rad), 3)
            target.blit(ring, (x - ring.get_width() / 2, y - ring.get_height() / 2))
        self._flashes = alive

    def _draw_fog(self, target, render_curves, radius_units: float) -> None:
        """Nebel: Feld verdunkeln, um jeden lebenden Kopf bleibt ein Sichtfenster."""
        r = max(24, int(radius_units * self.scale))
        fog = self._fog_surf
        fog.fill((6, 7, 12, 235))
        hole = _hole_mask(r)
        for rc in render_curves:
            if not rc.get("alive", True):
                continue
            hx = int(rc["x"] * self.scale) - r
            hy = int(rc["y"] * self.scale) - r
            fog.blit(hole, (hx, hy), special_flags=pygame.BLEND_RGBA_SUB)
        target.blit(fog, (self.ox, self.oy))

    def _hint(self, target, fonts, text) -> None:
        cx = self.ox + self.view_w // 2
        y = self.oy + self.view_h - 46
        img = fonts.body_bold(17).render(text, True, (255, 255, 255))
        bg = img.get_rect(center=(cx, y)).inflate(40, 22)
        s = pygame.Surface(bg.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (42, 76, 224, 235), s.get_rect(), border_radius=999)
        target.blit(s, bg)
        target.blit(img, img.get_rect(center=(cx, y)))

    def _countdown(self, target, fonts, countdown) -> None:
        n = max(1, math.ceil(countdown))
        cx = self.ox + self.view_w // 2
        cy = self.oy + self.view_h // 2
        pulse = 1.0 + 0.12 * math.sin(pygame.time.get_ticks() / 90.0)
        veil = pygame.Surface((170, 170), pygame.SRCALPHA)
        pygame.draw.circle(veil, (10, 12, 18, 150), (85, 85), 85)
        target.blit(veil, (cx - 85, cy - 85))
        big = fonts.display(int(96 * pulse)).render(str(n), True, (255, 255, 255))
        target.blit(big, big.get_rect(center=(cx, cy)))

    def _draw_hud(self, target, render_curves, fonts, round_no) -> None:
        draw_text(target, fonts.display(19), f"Runde {round_no}", T.TEXT, (24, 20))
        n = max(1, len(render_curves))
        left = 172
        avail = target.get_width() - left - 12
        bw = int(max(78, min(182, avail / n - 6)))
        compact = bw < 160 or n >= 6
        x = left
        for rc in render_curves:
            col = rc["color"]
            box = pygame.Rect(x, 12, bw, 46)
            pygame.draw.rect(target, T.SURFACE, box, border_radius=T.R_SM)
            pygame.draw.rect(target, col, (box.x, box.y, 5, box.h), border_radius=2)
            alive = rc.get("alive", True)
            fg = T.TEXT if alive else T.TEXT_MUTED
            if compact:
                draw_text(target, fonts.body_bold(14), rc["name"][:8], fg, (box.x + 12, box.y + 4))
                tail = f"{rc.get('score', 0)}" + ("" if alive else " (raus)")
                draw_text(target, fonts.body(12), tail, T.TEXT_MUTED, (box.x + 12, box.y + 24))
            else:
                name = rc["name"][:12] + ("" if alive else "  (raus)")
                draw_text(target, fonts.body_bold(15), name, fg, (box.x + 13, box.y + 5))
                draw_text(target, fonts.body(13), f"{rc.get('score', 0)} Pkt", T.TEXT_MUTED, (box.x + 13, box.y + 25))
                for i in range(min(rc.get("pu", 0), 6)):
                    pygame.draw.circle(target, T.ACCENT, (box.right - 13 - i * 12, box.y + 14), 4)
                cd = rc.get("cd", 0)
                if cd and cd > 0:
                    draw_text(target, fonts.body(11), f"{cd:.0f}s", T.TEXT_MUTED, (box.right - 30, box.y + 26))
            x += bw + 6

    def _banner(self, target, fonts, text) -> None:
        cx = self.ox + self.view_w // 2
        cy = self.oy + self.view_h // 2
        img = fonts.display(44).render(text, True, (255, 255, 255))
        bg = img.get_rect(center=(cx, cy)).inflate(64, 42)
        s = pygame.Surface(bg.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (10, 12, 18, 224), s.get_rect(), border_radius=16)
        target.blit(s, bg)
        target.blit(img, img.get_rect(center=(cx, cy)))
