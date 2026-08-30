"""Einstellungsseite - jeder Gameplay-Parameter als Slider + exaktes Zahlenfeld."""

from __future__ import annotations

from dataclasses import asdict

import pygame

from .. import theme as T
from ..config import GameSettings
from ..ui.widgets import Button, NumberField, Slider, Toggle, draw_text
from .common import BaseMenuScene

# (attr, Label, lo, hi, step, decimals, suffix)
GROUPS: list[tuple[str, list]] = [
    ("Bewegung", [
        ("speed", "Geschwindigkeit", 30, 400, 1, 0, " px/s"),
        ("turn_radius", "Lenkradius", 12, 400, 1, 0, " px"),
        ("line_width", "Linienbreite", 1.5, 20, 0.5, 1, " px"),
    ]),
    ("Luecken hinter sich", [
        ("gap_distance", "Abstand zwischen Luecken", 40, 1200, 10, 0, " px"),
        ("gap_distance_jitter", "Zufall auf den Abstand", 0.0, 0.9, 0.05, 2, ""),
        ("gap_size", "Groesse einer Luecke", 6, 200, 2, 0, " px"),
    ]),
    ("Powerup", [
        ("powerup_duration", "Wirkdauer", 0.2, 10, 0.1, 1, " s"),
        ("powerup_boost_factor", "Speed-Faktor", 1.05, 4.0, 0.05, 2, " x"),
        ("powerup_charges", "Ladungen pro Runde", 0, 50, 1, 0, ""),
        ("powerup_cooldown", "Abklingzeit", 0.0, 30, 0.5, 1, " s"),
    ]),
    ("Punkte & Matchende", [
        ("points_per_opponent", "Punkte je ueberlebtem Gegner", 1, 10, 1, 0, ""),
        ("target_score", "Punkte zum Sieg", 1, 500, 1, 0, ""),
    ]),
    ("Runde", [
        ("countdown_seconds", "Countdown", 0.0, 10, 0.5, 1, " s"),
        ("round_time_limit", "Zeitlimit (0 = keins)", 0.0, 600, 10, 0, " s"),
    ]),
    ("Spielfeld", [
        ("arena_size", "Groesse (kleiner = alles groesser)", 550, 1800, 25, 0, ""),
    ]),
    ("Bots", [
        ("bot_count", "Anzahl Bots (Standard)", 0, 11, 1, 0, ""),
        ("bot_difficulty", "Bot-Staerke", 0.0, 1.0, 0.05, 2, ""),
    ]),
    ("Audio", [
        ("sound_volume", "Soundeffekte", 0.0, 1.0, 0.05, 2, ""),
    ]),
    ("Fenster (wirkt nach Verlassen der Seite)", [
        ("window_width", "Fensterbreite", 800, 3840, 10, 0, " px"),
        ("window_height", "Fensterhoehe", 600, 2160, 10, 0, " px"),
    ]),
]
TOGGLES = [
    ("self_collision", "Eigene Linie toedlich", "Runde"),
    ("fullscreen", "Vollbild", "Fenster (wirkt nach Verlassen der Seite)"),
]


class SettingsScene(BaseMenuScene):
    title = "Einstellungen"
    subtitle = "Alle Werte frei justierbar - so tunst du das Gameplay"

    def __init__(self, app, back) -> None:
        super().__init__(app)
        self._back = back
        self.s: GameSettings = app.config.settings
        self._before = asdict(self.s)
        self._rows: list = []

    # ------------------------------------------------------------------ #
    def on_enter(self) -> None:
        self.build()

    def build(self) -> None:
        area = self.content_rect()
        area.height -= 8
        from ..ui.widgets import ScrollPanel

        row_h = 58
        head_h = 46
        total = 12
        for name, params in GROUPS:
            total += head_h + len(params) * row_h
            total += sum(row_h for a, _l, _g in TOGGLES if _g == name)
        total += 40

        panel = ScrollPanel(area, total)
        self.panel = panel
        self._rows = []
        y = 8
        for gname, params in GROUPS:
            panel.add(_Header((area.x + 4, area.y + y, area.w - 20, head_h), gname))
            y += head_h
            for attr, label, lo, hi, step, dec, suffix in params:
                self._add_num_row(panel, area, y, attr, label, lo, hi, step, dec, suffix)
                y += row_h
            for attr, tlabel, tgroup in TOGGLES:
                if tgroup == gname:
                    self._add_toggle_row(panel, area, y, attr, tlabel)
                    y += row_h

        w, h = self.size
        self.widgets = [
            panel,
            Button((w - 360, h - 56, 150, 42), "Zuruecksetzen", self._reset, "ghost"),
            Button((w - 196, h - 56, 150, 42), "Fertig", self._done, "primary"),
        ]

    def _add_num_row(self, panel, area, y, attr, label, lo, hi, step, dec, suffix):
        val = getattr(self.s, attr)
        lbl_r = (area.x + 8, area.y + y, 300, 40)
        sld_r = (area.x + 330, area.y + y + 18, area.w - 330 - 150, 8)
        num_r = (area.x + area.w - 132, area.y + y + 6, 116, 34)

        slider = Slider(sld_r, lo, hi, val, None, step=step)
        num = NumberField(num_r, lo, hi, val, None, step=step, decimals=dec, suffix=suffix)

        def on_slider(v, a=attr, n=num):
            setattr(self.s, a, v)
            n.set_value(v)
            self._live(a)

        def on_num(v, a=attr, sl=slider):
            setattr(self.s, a, v)
            sl.value = v
            self._live(a)

        slider.on_change = on_slider
        num.on_change = on_num
        panel.add(_RowLabel(lbl_r, label))
        panel.add(slider)
        panel.add(num)

    def _add_toggle_row(self, panel, area, y, attr, label):
        lbl_r = (area.x + 8, area.y + y, 400, 40)
        tg = Toggle((area.x + area.w - 80, area.y + y + 4), getattr(self.s, attr), None)

        def on_tg(v, a=attr):
            setattr(self.s, a, v)

        tg.on_change = on_tg
        panel.add(_RowLabel(lbl_r, label))
        panel.add(tg)

    # ------------------------------------------------------------------ #
    def _live(self, attr: str) -> None:
        if attr in ("sound_volume", "music_volume"):
            self.app.audio.refresh_volume()

    def _reset(self) -> None:
        defaults = GameSettings()
        for f in asdict(defaults):
            setattr(self.s, f, getattr(defaults, f))
        self.build()

    def _done(self) -> None:
        for f, v in asdict(self.s.clamped()).items():
            setattr(self.s, f, v)
        self.app.config.settings = self.s
        self.app.save_config()
        after = asdict(self.s)
        need_win = (
            after["window_width"] != self._before["window_width"]
            or after["window_height"] != self._before["window_height"]
            or after["fullscreen"] != self._before["fullscreen"]
        )
        self.app.audio.play("click")
        if need_win:
            self.app.rebuild_window()
        self.app.set_scene(self._back())

    def on_escape(self) -> bool:
        self._done()
        return True

    # ------------------------------------------------------------------ #
    def draw(self, surf) -> None:
        surf.fill(T.BG)
        w, h = self.size
        draw_text(surf, self.app.fonts.display(34), self.title, T.TEXT, (48, 44))
        draw_text(surf, self.app.fonts.body(17), self.subtitle, T.TEXT_MUTED, (50, 86))
        pygame.draw.line(surf, T.BORDER, (48, 112), (w - 48, 112), 1)
        for x in self.widgets:
            x.draw(surf, self.app.fonts)


class _Header:
    def __init__(self, rect, text):
        self.rect = pygame.Rect(rect)
        self.text = text

    def handle_event(self, e):
        return False

    def update(self, dt):
        pass

    def draw(self, surf, fonts):
        draw_text(surf, fonts.display(19), self.text, T.ACCENT, (self.rect.x, self.rect.bottom - 26))
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
