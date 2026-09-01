"""Einstellungsseite: aufklappbare Bereiche, jeder Wert als Slider + Zahlenfeld.

Bereiche: System - Sound - Spiel - Bots - Powerups.
Unter "Powerups" hat jedes Powerup einen eigenen aufklappbaren Block mit
An/Aus, Dauer, Staerke, Ladungen und Abklingzeit.
"""

from __future__ import annotations

from dataclasses import fields

import pygame

from .. import theme as T
from ..config import GameSettings, default_powerups
from ..game.powerups import POWERUPS
from ..party.registry import ALL_GAMES
from ..ui.widgets import (
    Button,
    NumberField,
    ScrollPanel,
    Slider,
    Toggle,
    draw_text,
)
from .common import BaseMenuScene

# Zeilen-Typen:  ("num", attr, label, lo, hi, step, dec, suffix)
#                ("bool", attr, label)
#                ("sub", ueberschrift)
SECTIONS: list[tuple[str, str, list]] = [
    ("system", "System", [
        ("sub", "Spielfeld"),
        ("num", "arena_size", "Groesse (kleiner = alles groesser)", 550, 1800, 25, 0, ""),
        ("sub", "Fenster (wirkt beim Verlassen der Seite)"),
        ("num", "window_width", "Fensterbreite", 800, 3840, 10, 0, " px"),
        ("num", "window_height", "Fensterhoehe", 600, 2160, 10, 0, " px"),
        ("bool", "fullscreen", "Vollbild"),
    ]),
    ("sound", "Sound", [
        ("num", "sound_volume", "Soundeffekte", 0.0, 1.0, 0.05, 2, ""),
    ]),
    ("spiel", "Spiel", [
        ("sub", "Bewegung"),
        ("num", "speed", "Geschwindigkeit", 30, 400, 1, 0, " px/s"),
        ("num", "turn_radius", "Lenkradius", 12, 400, 1, 0, " px"),
        ("num", "line_width", "Linienbreite", 1.5, 20, 0.5, 1, " px"),
        ("sub", "Luecken hinter sich"),
        ("num", "gap_distance", "Abstand zwischen Luecken", 40, 1200, 10, 0, " px"),
        ("num", "gap_distance_jitter", "Zufall auf den Abstand", 0.0, 0.9, 0.05, 2, ""),
        ("num", "gap_size", "Groesse einer Luecke", 6, 200, 2, 0, " px"),
        ("sub", "Punkte & Matchende"),
        ("num", "points_per_opponent", "Punkte je ueberlebtem Gegner", 1, 10, 1, 0, ""),
        ("num", "target_score", "Punkte zum Sieg", 1, 500, 1, 0, ""),
        ("sub", "Runde"),
        ("num", "countdown_seconds", "Countdown", 0.0, 10, 0.5, 1, " s"),
        ("num", "round_time_limit", "Zeitlimit (0 = keins)", 0.0, 600, 10, 0, " s"),
        ("bool", "self_collision", "Eigene Linie toedlich"),
    ]),
    ("turnier", "Turnier", [
        ("num", "party_games", "Anzahl Minispiele", 1, 40, 1, 0, ""),
        ("num", "party_points_top", "Punkte fuer Platz 1", 2, 50, 1, 0, ""),
        ("bool", "party_shuffle", "Reihenfolge mischen"),
    ]),
    ("bots", "Bots", [
        ("num", "bot_count", "Anzahl beim Start", 0, 11, 1, 0, ""),
        ("num", "bot_difficulty", "Staerke (1.0 = sehr stark)", 0.0, 1.0, 0.05, 2, ""),
    ]),
    ("powerups", "Powerups", []),      # wird dynamisch gebaut
]

ROW_H = 54
SUB_H = 38
HEAD_H = 52
PU_HEAD_H = 44


class SettingsScene(BaseMenuScene):
    title = "Einstellungen"
    subtitle = "Bereich anklicken zum Auf- und Zuklappen"

    def __init__(self, app, back) -> None:
        super().__init__(app)
        self._back = back
        self.s: GameSettings = app.config.settings
        self._win_before = (self.s.window_width, self.s.window_height, self.s.fullscreen)
        self._open: set[str] = set()
        self._open_pu: set[str] = set()
        self.panel: ScrollPanel | None = None

    # ------------------------------------------------------------------ #
    def on_enter(self) -> None:
        self.build()

    def resize(self) -> None:
        keep = self.panel.scroll_y if self.panel else 0
        self.build()
        if self.panel:
            self.panel.scroll_y = self.panel._clamp(keep)

    def _toggle(self, sid: str) -> None:
        self._open.symmetric_difference_update({sid})
        self._rebuild_keep_scroll()

    def _toggle_pu(self, pid: str) -> None:
        self._open_pu.symmetric_difference_update({pid})
        self._rebuild_keep_scroll()

    def _rebuild_keep_scroll(self) -> None:
        keep = self.panel.scroll_y if self.panel else 0
        self.build()
        if self.panel:
            self.panel.scroll_y = self.panel._clamp(keep)

    # ------------------------------------------------------------------ #
    def build(self) -> None:
        w, h = self.size
        area = pygame.Rect(max(40, (w - 940) // 2), 124, min(940, w - 80), h - 196)
        panel = ScrollPanel(area, 10)
        self.panel = panel
        y = 6

        for sid, label, rows in SECTIONS:
            is_open = sid in self._open
            panel.add(_SectionHeader((area.x, area.y + y, area.w - 18, HEAD_H),
                                     label, is_open, lambda s=sid: self._toggle(s)))
            y += HEAD_H
            if not is_open:
                y += 6
                continue
            if sid == "powerups":
                y = self._build_powerups(panel, area, y)
            else:
                for row in rows:
                    y = self._build_row(panel, area, y, row)
                if sid == "turnier":
                    y = self._build_party_games(panel, area, y)
            y += 12

        panel.content_height = y + 10

        self.widgets = [
            panel,
            Button((area.x, h - 62, 190, 42), "Zuruecksetzen", self._reset, "ghost"),
            Button((area.right - 150, h - 62, 150, 42), "Fertig", self._done, "primary"),
        ]

    # ------------------------------------------------------------------ #
    def _build_row(self, panel, area, y, row) -> int:
        kind = row[0]
        if kind == "sub":
            panel.add(_SubHead((area.x + 22, area.y + y, area.w - 60, SUB_H), row[1]))
            return y + SUB_H
        if kind == "bool":
            _, attr, label = row
            self._add_bool(panel, area, y, self.s, attr, label, indent=34)
            return y + ROW_H
        _, attr, label, lo, hi, step, dec, suffix = row
        self._add_num(panel, area, y, self.s, attr, label, lo, hi, step, dec, suffix, indent=34)
        return y + ROW_H

    def _build_party_games(self, panel, area, y) -> int:
        """An/Aus-Schalter fuer jedes einzelne Minispiel."""
        panel.add(_SubHead((area.x + 22, area.y + y, area.w - 60, SUB_H),
                           "Welche Minispiele sollen vorkommen?"))
        y += SUB_H
        panel.add(Button((area.x + 34, area.y + y, 120, 34), "Alle an",
                         lambda: self._all_party(True), "ghost"))
        panel.add(Button((area.x + 166, area.y + y, 120, 34), "Alle aus",
                         lambda: self._all_party(False), "ghost"))
        y += 46
        for cls in ALL_GAMES:
            gid = cls.id
            panel.add(_Desc((area.x + 56, area.y + y + 1, 420, 24), cls.name,
                            size=17, color=T.TEXT, bold=True))
            panel.add(_Desc((area.x + 56, area.y + y + 24, area.w - 180, 24), cls.rules))
            tg = Toggle((area.x + area.w - 96, area.y + y + 8),
                        self.s.party_game_enabled(gid), None)
            tg.on_change = lambda v, g=gid: self._set_party(g, v)
            panel.add(tg)
            y += ROW_H
        return y

    def _set_party(self, gid, on):
        self.s.party_enabled[gid] = bool(on)
        if not any(self.s.party_enabled.get(c.id, True) for c in ALL_GAMES):
            self.s.party_enabled[ALL_GAMES[0].id] = True     # mind. eines an
            self._rebuild_keep_scroll()

    def _all_party(self, on):
        for cls in ALL_GAMES:
            self.s.party_enabled[cls.id] = on
        if not on:
            self.s.party_enabled[ALL_GAMES[0].id] = True
        self._rebuild_keep_scroll()

    def _build_powerups(self, panel, area, y) -> int:
        panel.add(Button((area.x + 34, area.y + y, 120, 34), "Alle an",
                         lambda: self._all_powerups(True), "ghost"))
        panel.add(Button((area.x + 166, area.y + y, 120, 34), "Alle aus",
                         lambda: self._all_powerups(False), "ghost"))
        y += 48

        for meta in POWERUPS:
            pid = meta["id"]
            cfg = self.s.powerup_cfg(pid)
            is_open = pid in self._open_pu
            panel.add(_PowerupHeader(
                (area.x + 22, area.y + y, area.w - 60, PU_HEAD_H),
                meta, cfg, is_open, lambda p=pid: self._toggle_pu(p)))
            tg = Toggle((area.x + area.w - 96, area.y + y + 8), cfg.enabled, None)
            tg.on_change = lambda v, cc=cfg: setattr(cc, "enabled", v)
            panel.add(tg)
            y += PU_HEAD_H
            if not is_open:
                y += 4
                continue

            panel.add(_Desc((area.x + 56, area.y + y, area.w - 110, 30), meta["desc"]))
            y += 30
            if meta["duration"] is not None:
                self._add_num(panel, area, y, cfg, "duration", "Wirkdauer",
                              0.1, 30, 0.1, 1, " s", indent=56)
                y += ROW_H
            if meta["strength"] is not None:
                lo, hi, step, dec = meta["strength_range"]
                self._add_num(panel, area, y, cfg, "strength", meta["strength_label"],
                              lo, hi, step, dec, meta.get("strength_suffix", ""), indent=56)
                y += ROW_H
            self._add_num(panel, area, y, cfg, "charges", "Ladungen pro Runde",
                          0, 99, 1, 0, "", indent=56)
            y += ROW_H
            self._add_num(panel, area, y, cfg, "cooldown", "Abklingzeit",
                          0.0, 60, 0.5, 1, " s", indent=56)
            y += ROW_H + 10
        return y

    # ------------------------------------------------------------------ #
    def _add_num(self, panel, area, y, obj, attr, label, lo, hi, step, dec, suffix, *, indent) -> None:
        val = float(getattr(obj, attr))
        num_w, sld_gap = 118, 24
        lbl_w = 300
        sld_x = area.x + indent + lbl_w
        sld_w = max(80, area.w - indent - lbl_w - num_w - sld_gap - 30)

        slider = Slider((sld_x, area.y + y + 17, sld_w, 8), lo, hi, val, None, step=step)
        num = NumberField((area.x + area.w - num_w - 30, area.y + y + 5, num_w, 34),
                          lo, hi, val, None, step=step, decimals=dec, suffix=suffix)

        def on_slider(v, o=obj, a=attr, n=num):
            setattr(o, a, int(v) if dec == 0 else v)
            n.set_value(v)
            self._live(a)

        def on_num(v, o=obj, a=attr, sl=slider):
            setattr(o, a, int(v) if dec == 0 else v)
            sl.value = v
            self._live(a)

        slider.on_change = on_slider
        num.on_change = on_num
        panel.add(_RowLabel((area.x + indent, area.y + y, lbl_w, ROW_H - 6), label))
        panel.add(slider)
        panel.add(num)

    def _add_bool(self, panel, area, y, obj, attr, label, *, indent) -> None:
        tg = Toggle((area.x + area.w - 96, area.y + y + 10), getattr(obj, attr), None)
        tg.on_change = lambda v, o=obj, a=attr: setattr(o, a, v)
        panel.add(_RowLabel((area.x + indent, area.y + y, 460, ROW_H - 6), label))
        panel.add(tg)

    # ------------------------------------------------------------------ #
    def _all_powerups(self, on: bool) -> None:
        for meta in POWERUPS:
            self.s.powerup_cfg(meta["id"]).enabled = on
        if not on:                      # mindestens eines muss bleiben
            self.s.powerup_cfg(POWERUPS[0]["id"]).enabled = True
        self._rebuild_keep_scroll()

    def _live(self, attr: str) -> None:
        if attr == "sound_volume":
            self.app.audio.refresh_volume()

    def _reset(self) -> None:
        defaults = GameSettings()
        for f in fields(GameSettings):
            if f.name == "powerups":
                continue
            setattr(self.s, f.name, getattr(defaults, f.name))
        self.s.powerups = default_powerups()
        self.s.party_enabled = {}
        self._rebuild_keep_scroll()

    def _done(self) -> None:
        clean = self.s.clamped()
        for f in fields(GameSettings):
            setattr(self.s, f.name, getattr(clean, f.name))
        self.app.config.settings = self.s
        self.app.save_config()
        self.app.audio.play("click")
        if (self.s.window_width, self.s.window_height, self.s.fullscreen) != self._win_before:
            self.app.rebuild_window()
        self.app.set_scene(self._back())

    def on_escape(self) -> bool:
        self._done()
        return True

    # ------------------------------------------------------------------ #
    def draw(self, surf) -> None:
        surf.fill(T.BG)
        w, h = self.size
        draw_text(surf, self.app.fonts.display(34), self.title, T.TEXT, (48, 40))
        draw_text(surf, self.app.fonts.body(16), self.subtitle, T.TEXT_MUTED, (50, 84))
        pygame.draw.line(surf, T.BORDER, (48, 114), (w - 48, 114), 1)
        for x in self.widgets:
            x.draw(surf, self.app.fonts)


# =========================================================================== #
def _arrow(surf, center, size, down: bool, color) -> None:
    """Kleines Dreieck - selbst gezeichnet, damit es in jedem Font da ist."""
    cx, cy = center
    if down:
        pts = [(cx - size, cy - size // 2), (cx + size, cy - size // 2), (cx, cy + size)]
    else:
        pts = [(cx - size // 2, cy - size), (cx - size // 2, cy + size), (cx + size, cy)]
    pygame.draw.polygon(surf, color, pts)


class _SectionHeader:
    def __init__(self, rect, text, is_open, on_click):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.is_open = is_open
        self.on_click = on_click
        self._hover = False

    def handle_event(self, e):
        if e.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos):
            self.on_click()
            return True
        return False

    def update(self, dt):
        pass

    def draw(self, surf, fonts):
        bg = T.ACCENT_SOFT if (self.is_open or self._hover) else T.SURFACE
        pygame.draw.rect(surf, bg, self.rect, border_radius=T.R_SM)
        _arrow(surf, (self.rect.x + 24, self.rect.centery), 6, self.is_open, T.ACCENT)
        draw_text(surf, fonts.display(21), self.text, T.ACCENT,
                  (self.rect.x + 40, self.rect.centery - 14))


class _PowerupHeader:
    def __init__(self, rect, meta, cfg, is_open, on_click):
        self.rect = pygame.Rect(rect)
        self.meta = meta
        self.cfg = cfg
        self.is_open = is_open
        self.on_click = on_click

    def handle_event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            hit = pygame.Rect(self.rect.x, self.rect.y, self.rect.w - 110, self.rect.h)
            if hit.collidepoint(e.pos):
                self.on_click()
                return True
        return False

    def update(self, dt):
        pass

    def draw(self, surf, fonts):
        pygame.draw.rect(surf, T.SURFACE if self.is_open else T.BG, self.rect, border_radius=T.R_SM)
        pygame.draw.rect(surf, T.BORDER, self.rect, width=1, border_radius=T.R_SM)
        col = T.TEXT if self.cfg.enabled else T.TEXT_MUTED
        _arrow(surf, (self.rect.x + 22, self.rect.centery), 5, self.is_open, T.TEXT_MUTED)
        draw_text(surf, fonts.body_bold(17), self.meta["label"], col,
                  (self.rect.x + 36, self.rect.centery - 10))
        if not self.cfg.enabled:
            draw_text(surf, fonts.body(13), "aus", T.TEXT_MUTED,
                      (self.rect.right - 118, self.rect.centery - 8), right=True)


class _SubHead:
    def __init__(self, rect, text):
        self.rect = pygame.Rect(rect)
        self.text = text

    def handle_event(self, e):
        return False

    def update(self, dt):
        pass

    def draw(self, surf, fonts):
        draw_text(surf, fonts.body_bold(15), self.text, T.TEXT_MUTED,
                  (self.rect.x, self.rect.bottom - 24))
        pygame.draw.line(surf, T.BORDER, (self.rect.x, self.rect.bottom - 4),
                         (self.rect.right, self.rect.bottom - 4), 1)


class _RowLabel:
    def __init__(self, rect, text):
        self.rect = pygame.Rect(rect)
        self.text = text

    def handle_event(self, e):
        return False

    def update(self, dt):
        pass

    def draw(self, surf, fonts):
        draw_text(surf, fonts.body(17), self.text, T.TEXT, (self.rect.x, self.rect.centery - 9))


class _Desc:
    def __init__(self, rect, text, size=14, color=None, bold=False):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.size = size
        self.color = color or T.TEXT_MUTED
        self.bold = bold

    def handle_event(self, e):
        return False

    def update(self, dt):
        pass

    def draw(self, surf, fonts):
        font = fonts.body_bold(self.size) if self.bold else fonts.body(self.size)
        draw_text(surf, font, self.text, self.color, (self.rect.x, self.rect.y + 4))
