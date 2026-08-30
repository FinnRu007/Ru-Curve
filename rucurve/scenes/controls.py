"""Steuerung: pro Spieler-Slot Name, Farbe, Powerup und drei frei belegbare Tasten."""

from __future__ import annotations

import pygame

from .. import theme as T
from ..colors import PLAYER_COLORS, color_for, color_name
from ..game.powerups import POWERUPS
from ..ui.widgets import (
    Button,
    Dropdown,
    KeyBindField,
    ScrollPanel,
    TextInput,
    Toggle,
    draw_text,
)
from .common import BaseMenuScene

_PU_OPTIONS = [(p["id"], p["label"]) for p in POWERUPS]


class ControlsScene(BaseMenuScene):
    title = "Steuerung"
    subtitle = "Klicke ein Tastenfeld an und druecke die gewuenschte Taste"

    def __init__(self, app, back) -> None:
        super().__init__(app)
        self._back = back
        self.slots = app.config.slots

    def on_enter(self) -> None:
        self.build()

    # ------------------------------------------------------------------ #
    def build(self) -> None:
        area = self.content_rect()
        row_h = 122
        panel = ScrollPanel(area, len(self.slots) * row_h + 20)
        self.panel = panel
        self._keyfields: list[tuple[KeyBindField, int, str]] = []

        for i, slot in enumerate(self.slots):
            top = area.y + 10 + i * row_h
            self._build_row(panel, area, top, i, slot)

        w, h = self.size
        self.widgets = [
            panel,
            Button((w - 360, h - 56, 150, 42), "Zuruecksetzen", self._reset, "ghost"),
            Button((w - 196, h - 56, 150, 42), "Fertig", self._done, "primary"),
        ]
        self._refresh_conflicts()

    def _build_row(self, panel, area, top, idx, slot):
        x = area.x + 8
        en = Toggle((x, top + 6), slot.enabled, lambda v, s=slot: (setattr(s, "enabled", v), self._refresh_conflicts()))
        panel.add(en)

        sw = _Swatch((x + 66, top + 4, 34, 34), idx, self)
        panel.add(sw)

        name = TextInput((x + 112, top + 4, 190, 34), slot.name, lambda t, s=slot: setattr(s, "name", t), max_len=14)
        panel.add(name)

        pu = Dropdown((x + 320, top + 4, 220, 34), _PU_OPTIONS, slot.powerup_kind,
                      lambda v, s=slot: setattr(s, "powerup_kind", v))
        panel.add(pu)
        self._overlay_dropdowns = getattr(self, "_overlay_dropdowns", [])
        self._overlay_dropdowns.append(pu)

        ky = top + 56
        specs = [("Links", "left"), ("Rechts", "right"), ("Powerup", "powerup")]
        for j, (label, attr) in enumerate(specs):
            fx = x + j * 210
            panel.add(_Mini((fx, ky, 70, 34), label))
            kf = KeyBindField(
                (fx + 66, ky, 120, 34),
                getattr(slot, attr),
                lambda code, s=slot, a=attr: (setattr(s, a, code), self._refresh_conflicts()),
            )
            panel.add(kf)
            self._keyfields.append((kf, idx, attr))

    # ------------------------------------------------------------------ #
    def _refresh_conflicts(self) -> None:
        seen: dict[int, int] = {}
        dupes: set[int] = set()
        for slot in self.slots:
            if not slot.enabled:
                continue
            for code in (slot.left, slot.right, slot.powerup):
                if code in seen:
                    dupes.add(code)
                seen[code] = seen.get(code, 0) + 1
        for kf, idx, attr in self._keyfields:
            enabled = self.slots[idx].enabled
            kf.conflict = enabled and kf.code in dupes

    def _reset(self) -> None:
        from ..config import default_slots

        self.app.config.slots = default_slots()
        self.slots = self.app.config.slots
        self._overlay_dropdowns = []
        self.build()

    def _done(self) -> None:
        self.app.save_config()
        self.app.audio.play("click")
        self.app.set_scene(self._back())

    def on_escape(self) -> bool:
        self._done()
        return True

    # ------------------------------------------------------------------ #
    def handle_events(self, events) -> None:
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                # nur schliessen, wenn kein Tastenfeld gerade aufnimmt
                if not any(kf.capturing for kf, _, _ in self._keyfields):
                    self._done()
                    continue
            used = False
            for pu in getattr(self, "_overlay_dropdowns", []):
                if pu.open and pu.handle_event(e):
                    used = True
                    break
            if used:
                continue
            for w in self.widgets:
                if w.handle_event(e):
                    break

    def draw(self, surf) -> None:
        surf.fill(T.BG)
        w, h = self.size
        draw_text(surf, self.app.fonts.display(34), self.title, T.TEXT, (48, 44))
        draw_text(surf, self.app.fonts.body(17), self.subtitle, T.TEXT_MUTED, (50, 86))
        pygame.draw.line(surf, T.BORDER, (48, 112), (w - 48, 112), 1)
        for x in self.widgets:
            x.draw(surf, self.app.fonts)
        # Dropdown-Overlays ueber allem
        prev = surf.get_clip()
        surf.set_clip(self.panel.rect)
        for pu in getattr(self, "_overlay_dropdowns", []):
            if pu.open:
                pu.rect.y -= self.panel.scroll_y
                pu.draw_overlay(surf, self.app.fonts)
                pu.rect.y += self.panel.scroll_y
        surf.set_clip(prev)
        draw_text(surf, self.app.fonts.body(14),
                  "Tipp: HW-Tastaturen erkennen oft nur ~6 Tasten gleichzeitig.",
                  T.TEXT_MUTED, (50, h - 40))


class _Swatch:
    def __init__(self, rect, slot_idx, scene):
        self.rect = pygame.Rect(rect)
        self.slot_idx = slot_idx
        self.scene = scene

    def handle_event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3) and self.rect.collidepoint(e.pos):
            slot = self.scene.slots[self.slot_idx]
            step = 1 if e.button == 1 else -1
            slot.color_index = (slot.color_index + step) % len(PLAYER_COLORS)
            return True
        return False

    def update(self, dt):
        pass

    def draw(self, surf, fonts):
        slot = self.scene.slots[self.slot_idx]
        pygame.draw.rect(surf, color_for(slot.color_index), self.rect, border_radius=8)
        pygame.draw.rect(surf, T.BORDER, self.rect, width=1, border_radius=8)


class _Mini:
    def __init__(self, rect, text):
        self.rect = pygame.Rect(rect)
        self.text = text

    def handle_event(self, e):
        return False

    def update(self, dt):
        pass

    def draw(self, surf, fonts):
        draw_text(surf, fonts.body(14), self.text, T.TEXT_MUTED, (self.rect.x, self.rect.centery - 8))
