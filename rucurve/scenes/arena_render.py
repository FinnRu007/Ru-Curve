"""Zeichnet das Spielfeld: Trail-Surface + Koepfe + HUD.

Wird sowohl vom Host (GameScene) als auch vom Client (ClientGameScene) benutzt.
Die Trail-Surface hat die Groesse des angezeigten Feldes; Arena-Koordinaten
werden per `scale` umgerechnet.
"""

from __future__ import annotations

import math

import pygame

from .. import theme as T
from ..ui.widgets import draw_text


class ArenaView:
    def __init__(self, settings, screen_size: tuple[int, int]) -> None:
        self.aw = settings.arena_width
        self.ah = settings.arena_height
        sw, sh = screen_size
        avail_w = sw - 48
        avail_h = sh - 150
        self.scale = min(avail_w / self.aw, avail_h / self.ah)
        self.view_w = int(self.aw * self.scale)
        self.view_h = int(self.ah * self.scale)
        self.ox = (sw - self.view_w) // 2
        self.oy = 120 + (sh - 120 - self.view_h) // 2
        self.surf = pygame.Surface((self.view_w, self.view_h)).convert()
        self.reset()

    def reset(self) -> None:
        self.surf.fill(T.ARENA_BG)

    # ------------------------------------------------------------------ #
    def apply_segments(self, segments, color_map: dict) -> None:
        s = self.scale
        for (cid, x0, y0, x1, y1, width, gap) in segments:
            if gap:
                continue
            col = color_map.get(cid, (200, 200, 200))
            w = max(1, int(round(width * s)))
            p0 = (x0 * s, y0 * s)
            p1 = (x1 * s, y1 * s)
            if w <= 2:
                pygame.draw.line(self.surf, col, p0, p1, w)
            else:
                pygame.draw.line(self.surf, col, p0, p1, w)
                r = w // 2
                pygame.draw.circle(self.surf, col, (int(p1[0]), int(p1[1])), r)

    # ------------------------------------------------------------------ #
    def draw(self, target, render_curves: list[dict], fonts, *, countdown=0.0,
             round_no=1, phase="running", banner: str | None = None) -> None:
        target.fill(T.BG)
        # Feld
        frame = pygame.Rect(self.ox - 3, self.oy - 3, self.view_w + 6, self.view_h + 6)
        pygame.draw.rect(target, T.ARENA_BORDER, frame, border_radius=6)
        target.blit(self.surf, (self.ox, self.oy))

        s = self.scale
        for rc in render_curves:
            if not rc.get("alive", True):
                continue
            x = self.ox + rc["x"] * s
            y = self.oy + rc["y"] * s
            col = rc["color"]
            rad = max(3, int(rc.get("width", 4) * s * 0.5) + 2)
            if rc.get("boost"):
                pygame.draw.circle(target, (255, 255, 255), (int(x), int(y)), rad + 4, 2)
            pygame.draw.circle(target, col, (int(x), int(y)), rad)
            pygame.draw.circle(target, (255, 255, 255), (int(x), int(y)), rad, 1)
            h = rc.get("h", 0.0)
            target_pos = (x + math.cos(h) * (rad + 6), y + math.sin(h) * (rad + 6))
            pygame.draw.line(target, (255, 255, 255), (x, y), target_pos, 2)

        self._draw_hud(target, render_curves, fonts, round_no)

        if phase == "countdown":
            n = max(1, math.ceil(countdown))
            big = fonts.display(120).render(str(n), True, T.ACCENT)
            target.blit(big, big.get_rect(center=(self.ox + self.view_w // 2, self.oy + self.view_h // 2)))
        elif phase == "running" and countdown > -0.6 and countdown <= 0 and round_no:
            pass

        if banner:
            self._banner(target, fonts, banner)

    def _draw_hud(self, target, render_curves, fonts, round_no) -> None:
        draw_text(target, fonts.display(20), f"Runde {round_no}", T.TEXT, (24, 20))
        x = 200
        for rc in render_curves:
            col = rc["color"]
            box = pygame.Rect(x, 16, 168, 46)
            pygame.draw.rect(target, T.SURFACE, box, border_radius=T.R_SM)
            pygame.draw.rect(target, col, (box.x, box.y, 5, box.h), border_radius=2)
            name = rc["name"][:12] + ("" if rc.get("alive", True) else "  (raus)")
            draw_text(target, fonts.body_bold(15), name,
                      T.TEXT if rc.get("alive", True) else T.TEXT_MUTED, (box.x + 14, box.y + 5))
            draw_text(target, fonts.body(13), f"{rc.get('score', 0)} Pkt", T.TEXT_MUTED, (box.x + 14, box.y + 25))
            charges = rc.get("pu", 0)
            for i in range(min(charges, 6)):
                pygame.draw.circle(target, T.ACCENT, (box.right - 12 - i * 12, box.y + 14), 4)
            cd = rc.get("cd", 0)
            if cd and cd > 0:
                draw_text(target, fonts.body(11), f"{cd:.0f}s", T.TEXT_MUTED, (box.right - 30, box.y + 26))
            x += 178
            if x > target.get_width() - 180:
                break

    def _banner(self, target, fonts, text) -> None:
        cx = self.ox + self.view_w // 2
        cy = self.oy + self.view_h // 2
        img = fonts.display(48).render(text, True, (255, 255, 255))
        bg = img.get_rect(center=(cx, cy)).inflate(60, 40)
        s = pygame.Surface(bg.size, pygame.SRCALPHA)
        s.fill((10, 12, 18, 210))
        target.blit(s, bg)
        target.blit(img, img.get_rect(center=(cx, cy)))
