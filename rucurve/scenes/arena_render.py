"""Zeichnet das Spielfeld: Trail-Surface + Koepfe + HUD.

Die Trail-Surface hat die Groesse des angezeigten Feldes; Arena-Koordinaten
werden per `scale` umgerechnet. Linien werden mit anti-aliased Kreisen gestempelt,
damit die Kurven glatt aussehen. Wird von Host- und Client-Spielszene benutzt.
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


def _disc(surf, color, x, y, r):
    if _AAC is not None and r >= 1.5:
        _AAC(surf, color, (x, y), r, 0)
    else:
        pygame.draw.circle(surf, color, (int(x), int(y)), max(1, int(round(r))))


class ArenaView:
    def __init__(self, settings, screen_size: tuple[int, int]) -> None:
        self.aw = settings.arena_width
        self.ah = settings.arena_height
        sw, sh = screen_size
        avail_w = max(200, sw - 48)
        avail_h = max(200, sh - 168)
        self.scale = min(avail_w / self.aw, avail_h / self.ah)
        self.view_w = max(1, int(self.aw * self.scale))
        self.view_h = max(1, int(self.ah * self.scale))
        self.ox = (sw - self.view_w) // 2
        self.oy = 132 + (sh - 132 - self.view_h) // 2
        self.surf = pygame.Surface((self.view_w, self.view_h)).convert()
        self.reset()

    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        self.surf.fill(T.ARENA_BG)
        grid = (28, 31, 42)
        step = max(60, int(110 * self.scale))
        for gx in range(step, self.view_w, step):
            pygame.draw.line(self.surf, grid, (gx, 0), (gx, self.view_h), 1)
        for gy in range(step, self.view_h, step):
            pygame.draw.line(self.surf, grid, (0, gy), (self.view_w, gy), 1)

    # ------------------------------------------------------------------ #
    def apply_segments(self, segments, color_map: dict) -> None:
        s = self.scale
        for (cid, x0, y0, x1, y1, width, gap) in segments:
            if gap:
                continue
            col = color_map.get(cid, (200, 200, 200))
            r = max(1.0, width * s * 0.5)
            ax, ay, bx, by = x0 * s, y0 * s, x1 * s, y1 * s
            if r > 1.5:
                pygame.draw.line(self.surf, col, (ax, ay), (bx, by), int(r * 2))
            _disc(self.surf, col, bx, by, r)

    # ------------------------------------------------------------------ #
    def draw(self, target, render_curves: list[dict], fonts, *, countdown=0.0,
             round_no=1, phase="running", banner: str | None = None) -> None:
        target.fill(T.BG)

        shadow = pygame.Rect(self.ox - 6, self.oy - 4, self.view_w + 12, self.view_h + 14)
        pygame.draw.rect(target, (232, 234, 240), shadow, border_radius=14)
        frame = pygame.Rect(self.ox - 3, self.oy - 3, self.view_w + 6, self.view_h + 6)
        pygame.draw.rect(target, T.ARENA_BORDER, frame, border_radius=8)
        target.blit(self.surf, (self.ox, self.oy))

        s = self.scale
        for rc in render_curves:
            if not rc.get("alive", True):
                continue
            x = self.ox + rc["x"] * s
            y = self.oy + rc["y"] * s
            col = rc["color"]
            rad = max(3.0, rc.get("width", 4) * s * 0.5 + 2.2)
            if rc.get("boost"):
                _ring(target, (255, 255, 255), x, y, rad + 5, 2)
            _disc(target, col, x, y, rad)
            _ring(target, (255, 255, 255), x, y, rad, 1)
            h = rc.get("h", 0.0)
            pygame.draw.aaline(target, (255, 255, 255),
                               (x, y), (x + math.cos(h) * (rad + 7), y + math.sin(h) * (rad + 7)))

        self._draw_hud(target, render_curves, fonts, round_no)

        if phase == "countdown":
            n = max(1, math.ceil(countdown))
            cx = self.ox + self.view_w // 2
            cy = self.oy + self.view_h // 2
            veil = pygame.Surface((150, 150), pygame.SRCALPHA)
            pygame.draw.circle(veil, (10, 12, 18, 150), (75, 75), 75)
            target.blit(veil, (cx - 75, cy - 75))
            big = fonts.display(96).render(str(n), True, (255, 255, 255))
            target.blit(big, big.get_rect(center=(cx, cy)))

        if banner:
            self._banner(target, fonts, banner)

    # ------------------------------------------------------------------ #
    def _draw_hud(self, target, render_curves, fonts, round_no) -> None:
        draw_text(target, fonts.display(19), f"Runde {round_no}", T.TEXT, (24, 22))
        n = max(1, len(render_curves))
        left = 176
        avail = target.get_width() - left - 16
        bw = int(max(84, min(176, avail / n - 6)))
        compact = bw < 128
        x = left
        for rc in render_curves:
            col = rc["color"]
            box = pygame.Rect(x, 14, bw, 50)
            pygame.draw.rect(target, T.SURFACE, box, border_radius=T.R_SM)
            pygame.draw.rect(target, col, (box.x, box.y, 5, box.h), border_radius=2)
            alive = rc.get("alive", True)
            fg = T.TEXT if alive else T.TEXT_MUTED
            if compact:
                draw_text(target, fonts.body_bold(14), rc["name"][:8], fg, (box.x + 12, box.y + 5))
                tail = f"{rc.get('score', 0)}" + ("" if alive else " (raus)")
                draw_text(target, fonts.body(12), tail, T.TEXT_MUTED, (box.x + 12, box.y + 26))
            else:
                name = rc["name"][:12] + ("" if alive else "  (raus)")
                draw_text(target, fonts.body_bold(15), name, fg, (box.x + 14, box.y + 6))
                draw_text(target, fonts.body(13), f"{rc.get('score', 0)} Pkt", T.TEXT_MUTED, (box.x + 14, box.y + 27))
                for i in range(min(rc.get("pu", 0), 6)):
                    pygame.draw.circle(target, T.ACCENT, (box.right - 13 - i * 12, box.y + 15), 4)
                cd = rc.get("cd", 0)
                if cd and cd > 0:
                    draw_text(target, fonts.body(11), f"{cd:.0f}s", T.TEXT_MUTED, (box.right - 30, box.y + 28))
            x += bw + 6

    def _banner(self, target, fonts, text) -> None:
        cx = self.ox + self.view_w // 2
        cy = self.oy + self.view_h // 2
        img = fonts.display(44).render(text, True, (255, 255, 255))
        bg = img.get_rect(center=(cx, cy)).inflate(64, 42)
        s = pygame.Surface(bg.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (10, 12, 18, 220), s.get_rect(), border_radius=16)
        target.blit(s, bg)
        target.blit(img, img.get_rect(center=(cx, cy)))


def _ring(surf, color, x, y, r, w):
    if _AAC is not None:
        _AAC(surf, color, (x, y), r, w)
    else:
        pygame.draw.circle(surf, color, (int(x), int(y)), max(1, int(r)), w)
