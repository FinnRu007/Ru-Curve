"""Gemeinsame Optik fuer den Turnier-Modus.

Bewusst dunkler und bunter als die weissen Menue-Seiten - das Turnier soll wie
ein Partyspiel aussehen, nicht wie ein Einstellungsdialog.
"""

from __future__ import annotations

import math

import pygame

from ..ui.widgets import draw_text

# --- Palette ---------------------------------------------------------------
BG = (13, 15, 26)
BG_2 = (22, 26, 44)
PANEL = (28, 33, 52)
PANEL_HI = (40, 47, 72)
LINE = (58, 66, 96)
TEXT = (238, 243, 255)
MUTED = (146, 157, 186)
GOLD = (255, 199, 72)
SILVER = (200, 208, 224)
BRONZE = (206, 137, 74)
OK = (74, 214, 146)
BAD = (240, 92, 92)
ACCENT = (96, 140, 255)

PLACE_COLORS = (GOLD, SILVER, BRONZE)
# Beschriftung der drei Spieler-Tasten (Links / Aktion / Rechts)
BTN_LABEL = ("linke Taste", "Aktionstaste", "rechte Taste")
BTN_SHORT = ("L", "A", "R")
ELL = "…"

_bg_cache = {}


def backdrop(surf):
    """Dunkler Verlauf mit weichem Licht in der Mitte - einmal vorgerechnet."""
    size = surf.get_size()
    bg = _bg_cache.get(size)
    if bg is None:
        w, h = size
        bg = pygame.Surface(size).convert()
        for y in range(0, h, 4):
            t = y / max(1, h)
            col = tuple(int(BG[i] + (BG_2[i] - BG[i]) * t) for i in range(3))
            pygame.draw.rect(bg, col, (0, y, w, 4))
        glow = pygame.Surface((w, h), pygame.SRCALPHA)
        r = int(min(w, h) * 0.75)
        for i in range(r, 0, -8):
            a = int(26 * (1 - i / r) ** 2)
            pygame.draw.circle(glow, (90, 120, 220, a), (w // 2, int(h * 0.42)), i)
        bg.blit(glow, (0, 0))
        if len(_bg_cache) > 4:
            _bg_cache.clear()
        _bg_cache[size] = bg
    surf.blit(bg, (0, 0))


def panel(surf, rect, color=PANEL, border=None, radius=16, alpha=255):
    rect = pygame.Rect(rect)
    if alpha >= 255:
        pygame.draw.rect(surf, color, rect, border_radius=radius)
    else:
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (color[0], color[1], color[2], alpha), s.get_rect(),
                         border_radius=radius)
        surf.blit(s, rect)
    if border:
        pygame.draw.rect(surf, border, rect, width=2, border_radius=radius)


def title(surf, fonts, text, y, size=44, color=TEXT, center_x=None):
    cx = center_x if center_x is not None else surf.get_width() // 2
    img = fonts.display(size).render(str(text), True, color)
    surf.blit(img, img.get_rect(midtop=(cx, y)))


def subtitle(surf, fonts, text, y, size=19, color=MUTED, center_x=None):
    cx = center_x if center_x is not None else surf.get_width() // 2
    img = fonts.body(size).render(str(text), True, color)
    surf.blit(img, img.get_rect(midtop=(cx, y)))


def key_cap(surf, fonts, rect, label, color=PANEL_HI, text_color=TEXT,
            pressed=False, glow=None):
    """Zeichnet eine Tastenkappe mit dem echten Tastennamen des Spielers."""
    rect = pygame.Rect(rect)
    depth = 3 if pressed else 6
    base = pygame.Rect(rect.x, rect.y + depth, rect.w, rect.h - depth)
    shadow = tuple(int(c * 0.45) for c in color)
    pygame.draw.rect(surf, shadow, (rect.x, rect.y + 4, rect.w, rect.h - 2),
                     border_radius=12)
    if glow:
        g = pygame.Surface((rect.w + 24, rect.h + 24), pygame.SRCALPHA)
        pygame.draw.rect(g, (glow[0], glow[1], glow[2], 90), g.get_rect(),
                         border_radius=20)
        surf.blit(g, (rect.x - 12, rect.y - 12))
    pygame.draw.rect(surf, color, base, border_radius=12)
    pygame.draw.rect(surf, tuple(min(255, int(c * 1.25)) for c in color), base,
                     width=2, border_radius=12)
    img = fonts.body_bold(min(26, max(13, base.h // 2))).render(str(label), True, text_color)
    surf.blit(img, img.get_rect(center=base.center))


def timer_bar(surf, rect, frac, color=ACCENT, bg=PANEL):
    rect = pygame.Rect(rect)
    frac = max(0.0, min(1.0, frac))
    pygame.draw.rect(surf, bg, rect, border_radius=rect.h // 2)
    if frac > 0:
        w = max(rect.h, int(rect.w * frac))
        col = color if frac > 0.3 else BAD
        pygame.draw.rect(surf, col, (rect.x, rect.y, w, rect.h),
                         border_radius=rect.h // 2)


def countdown_number(surf, fonts, n, center, color=TEXT):
    pulse = 1.0 + 0.10 * math.sin(pygame.time.get_ticks() / 90.0)
    img = fonts.display(int(120 * pulse)).render(str(n), True, color)
    surf.blit(img, img.get_rect(center=center))


def player_chip(surf, fonts, rect, player, value="", sub="", dim=False,
                highlight=False):
    """Eine Karte je Spieler: Farbstreifen, Name, Wert."""
    rect = pygame.Rect(rect)
    panel(surf, rect, color=PANEL_HI if highlight else PANEL,
          border=player.color if highlight else None)
    stripe = player.color if not dim else tuple(int(c * .4) for c in player.color)
    pygame.draw.rect(surf, stripe, (rect.x, rect.y + 6, 5, rect.h - 12), border_radius=3)
    name_col = TEXT if not dim else MUTED
    draw_text(surf, fonts.body_bold(16), fit(fonts.body_bold(16), player.name, rect.w - 90),
              name_col, (rect.x + 14, rect.y + 7))
    if sub:
        draw_text(surf, fonts.body(12), fit(fonts.body(12), sub, rect.w - 90),
                  MUTED, (rect.x + 14, rect.y + 27))
    if value != "":
        img = fonts.display(20).render(str(value), True, name_col)
        surf.blit(img, img.get_rect(midright=(rect.right - 12, rect.centery)))


def leaderboard(surf, fonts, rect, rows, heading="Rangliste", compact=False):
    """rows = [{place, name, color_index, points, delta?}]"""
    from ..colors import color_for

    rect = pygame.Rect(rect)
    panel(surf, rect, radius=18)
    draw_text(surf, fonts.display(20), heading, TEXT, (rect.x + 18, rect.y + 14))
    y = rect.y + 52
    row_h = 34 if compact else 42
    for r in rows:
        if y + row_h > rect.bottom - 8:
            break
        place = r.get("place", 0)
        box = pygame.Rect(rect.x + 10, y, rect.w - 20, row_h - 6)
        if place <= 3:
            pygame.draw.rect(surf, PANEL_HI, box, border_radius=10)
        pc = PLACE_COLORS[place - 1] if 1 <= place <= 3 else MUTED
        draw_text(surf, fonts.display(16), str(place), pc, (box.x + 10, box.centery - 10))
        pygame.draw.circle(surf, color_for(r.get("color_index", 0)),
                           (box.x + 42, box.centery), 7)
        draw_text(surf, fonts.body_bold(15),
                  fit(fonts.body_bold(15), r.get("name", "?"), box.w - 120),
                  TEXT, (box.x + 58, box.centery - 9))
        val = str(r.get("points", r.get("value", "")))
        img = fonts.display(17).render(val, True, TEXT)
        surf.blit(img, img.get_rect(midright=(box.right - 12, box.centery)))
        delta = r.get("delta")
        if delta:
            d = fonts.body_bold(12).render("+" + str(delta), True, OK)
            surf.blit(d, d.get_rect(midright=(box.right - 46, box.centery + 1)))
        y += row_h


def banner(surf, fonts, text, color=TEXT, y=None, size=40):
    w, h = surf.get_size()
    cy = y if y is not None else h // 2
    img = fonts.display(size).render(str(text), True, color)
    box = img.get_rect(center=(w // 2, cy)).inflate(70, 40)
    s = pygame.Surface(box.size, pygame.SRCALPHA)
    pygame.draw.rect(s, (8, 10, 18, 226), s.get_rect(), border_radius=20)
    pygame.draw.rect(s, (color[0], color[1], color[2], 120), s.get_rect(),
                     width=2, border_radius=20)
    surf.blit(s, box)
    surf.blit(img, img.get_rect(center=(w // 2, cy)))


def fit(font, text, max_w):
    text = str(text)
    if font.size(text)[0] <= max_w:
        return text
    while text and font.size(text + ELL)[0] > max_w:
        text = text[:-1]
    return text + ELL if text else ""
