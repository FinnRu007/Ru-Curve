"""Kleiner, handgemachter Widget-Satz im Ru-Design-Look."""

from __future__ import annotations

from typing import Callable

import pygame

from .. import theme as T


def draw_text(surf, font, text, color, pos, *, center=False, right=False):
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    elif right:
        rect.topright = pos
    else:
        rect.topleft = pos
    surf.blit(img, rect)
    return rect


def wrap_text(font, text: str, max_w: int, max_lines: int = 3) -> list:
    """Bricht an Wortgrenzen um - nicht mitten im Wort."""
    words = str(text).split()
    lines, cur = [], ""
    for w in words:
        probe = (cur + " " + w).strip()
        if cur and font.size(probe)[0] > max_w:
            lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
        else:
            cur = probe
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


def key_name(code: int) -> str:
    try:
        n = pygame.key.name(code)
    except Exception:
        n = "?"
    n = n.replace("[", "").replace("]", "")
    special = {
        "left": "←", "right": "→", "up": "↑", "down": "↓",
        "space": "Leer", "return": "Enter", "left shift": "L-Shift",
        "right shift": "R-Shift", "left ctrl": "L-Strg", "right ctrl": "R-Strg",
        "page up": "BildAuf", "page down": "BildAb",
    }
    return special.get(n, n.upper() if len(n) == 1 else n.title())


# --------------------------------------------------------------------------- #
# Merkt sich pro Bild, ob die Maus ueber etwas Anklickbarem steht - daraus
# macht app.py den Handzeiger.
_hover_seen = False


def note_hover() -> None:
    global _hover_seen
    _hover_seen = True


def take_hover() -> bool:
    """Gab es seit dem letzten Aufruf etwas unter der Maus? (setzt zurueck)"""
    global _hover_seen
    was, _hover_seen = _hover_seen, False
    return was


# Solange ein Scroll-Bereich zeichnet, gilt nur der sichtbare Ausschnitt:
# eine Zeile, die oben aus dem Bereich herausragt, darf nicht auf Hover
# reagieren, obwohl ihr Rechteck die Maus enthaelt.
_clip = None


def set_hover_clip(rect) -> None:
    global _clip
    _clip = pygame.Rect(rect) if rect is not None else None


def hover_here(rect) -> bool:
    """Fuer Elemente, die nicht von Widget erben (eigene Kopfzeilen usw.)."""
    pos = pygame.mouse.get_pos()
    if not pygame.Rect(rect).collidepoint(pos):
        return False
    if _clip is not None and not _clip.collidepoint(pos):
        return False
    note_hover()
    return True


def hover_tint(base, amount: int = 18):
    """Farbe fuers Ueberfahren - hell wird heller, dunkel wird heller."""
    return tuple(max(0, min(255, c + amount)) for c in base[:3])


class Widget:
    def __init__(self, rect) -> None:
        self.rect = pygame.Rect(rect)
        self.visible = True
        self.enabled = True

    def hovered(self, rect=None) -> bool:
        """Steht die Maus darueber?

        Wird beim Zeichnen gefragt und nicht aus MOUSEMOTION gefuettert: so
        stimmt die Markierung auch, wenn sich das Fenster oder die Liste
        aendert, ohne dass die Maus bewegt wird.
        """
        if not (self.visible and self.enabled):
            return False
        r = self.rect if rect is None else rect
        pos = pygame.mouse.get_pos()
        if not r.collidepoint(pos):
            return False
        if _clip is not None and not _clip.collidepoint(pos):
            return False
        note_hover()
        return True

    def handle_event(self, e) -> bool:
        return False

    def update(self, dt: float) -> None:
        pass

    def draw(self, surf, fonts) -> None:
        pass


# --------------------------------------------------------------------------- #
class Button(Widget):
    def __init__(self, rect, text: str, on_click: Callable[[], None], kind: str = "primary") -> None:
        super().__init__(rect)
        self.text = text
        self.on_click = on_click
        self.kind = kind
        self._hover = False

    def handle_event(self, e) -> bool:
        if not (self.visible and self.enabled):
            return False
        if e.type == pygame.MOUSEMOTION:
            self._hover = self.rect.collidepoint(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos):
            self.on_click()
            return True
        return False

    def draw(self, surf, fonts) -> None:
        if not self.visible:
            return
        hover = self.hovered()
        if self.kind == "primary":
            bg = T.ACCENT_DARK if hover else T.ACCENT
            fg = (255, 255, 255)
            border = None
        elif self.kind == "danger":
            bg = (196, 48, 48) if hover else T.DANGER
            fg = (255, 255, 255)
            border = None
        else:  # ghost
            bg = T.SURFACE_ALT if hover else T.SURFACE
            fg = T.TEXT
            border = T.BORDER
        if not self.enabled:
            bg = T.SURFACE_ALT
            fg = T.TEXT_MUTED
        pygame.draw.rect(surf, bg, self.rect, border_radius=T.R_PILL)
        if border:
            pygame.draw.rect(surf, border, self.rect, width=1, border_radius=T.R_PILL)
        draw_text(surf, fonts.body_bold(19), self.text, fg, self.rect.center, center=True)


# --------------------------------------------------------------------------- #
class Label(Widget):
    def __init__(self, rect, text: str, *, size=18, color=None, bold=False, align="left") -> None:
        super().__init__(rect)
        self.text = text
        self.size = size
        self.color = color or T.TEXT
        self.bold = bold
        self.align = align

    def draw(self, surf, fonts) -> None:
        if not self.visible:
            return
        font = fonts.body_bold(self.size) if self.bold else fonts.body(self.size)
        if self.align == "center":
            draw_text(surf, font, self.text, self.color, self.rect.center, center=True)
        elif self.align == "right":
            draw_text(surf, font, self.text, self.color, self.rect.topright, right=True)
        else:
            draw_text(surf, font, self.text, self.color, (self.rect.x, self.rect.centery - self.size // 2))


# --------------------------------------------------------------------------- #
class Slider(Widget):
    def __init__(self, rect, lo, hi, value, on_change, *, step=None) -> None:
        super().__init__(rect)
        self.lo = float(lo)
        self.hi = float(hi)
        self.value = float(value)
        self.on_change = on_change
        self.step = step
        self._drag = False

    def _set_from_x(self, x) -> None:
        t = (x - self.rect.x) / max(1, self.rect.w)
        t = max(0.0, min(1.0, t))
        v = self.lo + t * (self.hi - self.lo)
        if self.step:
            v = round(v / self.step) * self.step
        v = max(self.lo, min(self.hi, v))
        if v != self.value:
            self.value = v
            self.on_change(v)

    def handle_event(self, e) -> bool:
        if not (self.visible and self.enabled):
            return False
        hit = self.rect.inflate(0, 18).collidepoint(getattr(e, "pos", (0, 0)))
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and hit:
            self._drag = True
            self._set_from_x(e.pos[0])
            return True
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self._drag = False
        if e.type == pygame.MOUSEMOTION and self._drag:
            self._set_from_x(e.pos[0])
            return True
        return False

    def draw(self, surf, fonts) -> None:
        if not self.visible:
            return
        cy = self.rect.centery
        hover = self.hovered(self.rect.inflate(0, 18)) or self._drag
        pygame.draw.line(surf, T.BORDER, (self.rect.x, cy), (self.rect.right, cy), 4)
        t = (self.value - self.lo) / max(1e-9, self.hi - self.lo)
        hx = int(self.rect.x + t * self.rect.w)
        pygame.draw.line(surf, T.ACCENT, (self.rect.x, cy), (hx, cy), 4)
        if hover:
            pygame.draw.circle(surf, T.ACCENT_SOFT, (hx, cy), 14)
        pygame.draw.circle(surf, T.ACCENT_DARK if hover else T.ACCENT, (hx, cy),
                           11 if hover else 9)
        pygame.draw.circle(surf, (255, 255, 255), (hx, cy), 5 if hover else 4)


# --------------------------------------------------------------------------- #
class NumberField(Widget):
    def __init__(self, rect, lo, hi, value, on_change, *, step=1.0, decimals=0, suffix="") -> None:
        super().__init__(rect)
        self.lo, self.hi = float(lo), float(hi)
        self.value = float(value)
        self.on_change = on_change
        self.step = float(step)
        self.decimals = decimals
        self.suffix = suffix
        self.focused = False
        self._text = ""

    # -- helpers ----------------------------------------------------------
    def _fmt(self) -> str:
        s = f"{self.value:.{self.decimals}f}" if self.decimals else f"{int(round(self.value))}"
        return s + self.suffix

    def _commit(self, v: float) -> None:
        v = max(self.lo, min(self.hi, v))
        v = round(v, self.decimals) if self.decimals else round(v)
        if v != self.value:
            self.value = float(v)
            self.on_change(self.value)
        else:
            self.value = float(v)

    def set_value(self, v: float) -> None:
        self.value = max(self.lo, min(self.hi, float(v)))

    @property
    def _btn_up(self):
        return pygame.Rect(self.rect.right - 26, self.rect.y, 26, self.rect.h // 2)

    @property
    def _btn_dn(self):
        return pygame.Rect(self.rect.right - 26, self.rect.centery, 26, self.rect.h - self.rect.h // 2)

    def handle_event(self, e) -> bool:
        if not (self.visible and self.enabled):
            return False
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self._btn_up.collidepoint(e.pos):
                self._commit(self.value + self.step)
                return True
            if self._btn_dn.collidepoint(e.pos):
                self._commit(self.value - self.step)
                return True
            if self.rect.collidepoint(e.pos):
                self.focused = True
                self._text = self._fmt().replace(self.suffix, "")
                return True
            self._flush_text()
            self.focused = False
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (4, 5) and self.rect.collidepoint(e.pos):
            self._commit(self.value + (self.step if e.button == 4 else -self.step))
            return True
        elif e.type == pygame.KEYDOWN and self.focused:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                self._flush_text()
                self.focused = False
            elif e.key == pygame.K_BACKSPACE:
                self._text = self._text[:-1]
            elif e.unicode and (e.unicode.isdigit() or e.unicode in ".,-"):
                self._text += e.unicode.replace(",", ".")
            return True
        return False

    def _flush_text(self) -> None:
        if not self.focused:
            return
        try:
            self._commit(float(self._text))
        except ValueError:
            pass
        self._text = ""

    def draw(self, surf, fonts) -> None:
        if not self.visible:
            return
        hover = self.hovered()
        pygame.draw.rect(surf, T.SURFACE_ALT if hover and not self.focused else T.BG,
                         self.rect, border_radius=T.R_SM)
        if self.focused:
            border, width = T.ACCENT, 2
        elif hover:
            border, width = T.ACCENT, 1
        else:
            border, width = T.BORDER, 1
        pygame.draw.rect(surf, border, self.rect, width=width, border_radius=T.R_SM)
        txt = self._text if self.focused else self._fmt()
        draw_text(surf, fonts.body(17), txt, T.TEXT, (self.rect.x + 10, self.rect.centery - 9))
        for r, arrow in ((self._btn_up, "▲"), (self._btn_dn, "▼")):
            # Die beiden Pfeilfelder markieren sich einzeln - man soll sehen,
            # welches von beiden man gerade trifft.
            if self.hovered(r):
                pygame.draw.rect(surf, T.ACCENT_SOFT, r.inflate(-3, -3),
                                 border_radius=6)
                draw_text(surf, fonts.body(10), arrow, T.ACCENT_DARK, r.center,
                          center=True)
            else:
                draw_text(surf, fonts.body(10), arrow, T.TEXT_MUTED, r.center,
                          center=True)


# --------------------------------------------------------------------------- #
class Toggle(Widget):
    def __init__(self, pos, value: bool, on_change) -> None:
        super().__init__((pos[0], pos[1], 52, 28))
        self.value = bool(value)
        self.on_change = on_change

    def handle_event(self, e) -> bool:
        if not (self.visible and self.enabled):
            return False
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and self.rect.collidepoint(e.pos):
            self.value = not self.value
            self.on_change(self.value)
            return True
        return False

    def draw(self, surf, fonts) -> None:
        if not self.visible:
            return
        hover = self.hovered()
        col = T.ACCENT if self.value else T.BORDER
        if hover:
            col = T.ACCENT_DARK if self.value else hover_tint(T.BORDER, 26)
        pygame.draw.rect(surf, col, self.rect, border_radius=T.R_PILL)
        if hover:
            pygame.draw.rect(surf, T.ACCENT, self.rect, width=2,
                             border_radius=T.R_PILL)
        cx = self.rect.right - 14 if self.value else self.rect.x + 14
        pygame.draw.circle(surf, (255, 255, 255), (cx, self.rect.centery), 11)


# --------------------------------------------------------------------------- #
class Dropdown(Widget):
    def __init__(self, rect, options: list[tuple], value, on_change) -> None:
        super().__init__(rect)
        self.options = options            # [(value, label), ...]
        self.value = value
        self.on_change = on_change
        self.open = False
        self._scroll = 0

    def _label(self) -> str:
        for v, lbl in self.options:
            if v == self.value:
                return lbl
        return "?"

    # -- Liste kann laenger sein als der Platz: klappt notfalls nach oben auf
    #    und laesst sich mit dem Mausrad scrollen.
    def _layout(self, screen_h: int | None = None) -> tuple[int, int, int]:
        """(erste sichtbare Zeile, Anzahl sichtbar, y der ersten Zeile)."""
        h = self.rect.h
        sh = screen_h or pygame.display.get_surface().get_height()
        below = max(0, sh - self.rect.bottom - 8)
        above = max(0, self.rect.y - 8)
        n = len(self.options)
        if below >= n * h or below >= above:
            vis = max(1, min(n, below // h))
            top = self.rect.bottom
        else:
            vis = max(1, min(n, above // h))
            top = self.rect.y - vis * h
        self._scroll = max(0, min(self._scroll, n - vis))
        return self._scroll, vis, top

    def handle_event(self, e) -> bool:
        if not (self.visible and self.enabled):
            return False
        if self.open and e.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, self._scroll - e.y)
            return True
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                self.open = not self.open
                if self.open:      # gewaehlten Eintrag mit anzeigen
                    idx = next((i for i, (v, _l) in enumerate(self.options) if v == self.value), 0)
                    self._scroll = idx
                return True
            if self.open:
                start, vis, top = self._layout()
                for row in range(vis):
                    i = start + row
                    if i >= len(self.options):
                        break
                    r = pygame.Rect(self.rect.x, top + row * self.rect.h, self.rect.w, self.rect.h)
                    if r.collidepoint(e.pos):
                        self.value = self.options[i][0]
                        self.on_change(self.value)
                        self.open = False
                        return True
                self.open = False
        return False

    def draw(self, surf, fonts) -> None:
        if not self.visible:
            return
        hover = self.hovered() or self.open
        pygame.draw.rect(surf, T.SURFACE_ALT if hover else T.BG, self.rect,
                         border_radius=T.R_SM)
        pygame.draw.rect(surf, T.ACCENT if hover else T.BORDER, self.rect,
                         width=2 if self.open else 1, border_radius=T.R_SM)
        draw_text(surf, fonts.body(16), self._label(), T.TEXT, (self.rect.x + 10, self.rect.centery - 9))
        draw_text(surf, fonts.body(10), "▼", T.ACCENT_DARK if hover else T.TEXT_MUTED,
                  (self.rect.right - 16, self.rect.centery - 5))

    def draw_overlay(self, surf, fonts) -> None:
        if not self.open:
            return
        start, vis, top = self._layout(surf.get_height())
        n = len(self.options)
        for row in range(vis):
            i = start + row
            if i >= n:
                break
            v, lbl = self.options[i]
            r = pygame.Rect(self.rect.x, top + row * self.rect.h, self.rect.w, self.rect.h)
            row_hover = self.hovered(r)
            if row_hover:
                bg, border = T.ACCENT, T.ACCENT_DARK
            elif v == self.value:
                bg, border = T.ACCENT_SOFT, T.BORDER
            else:
                bg, border = T.BG, T.BORDER
            pygame.draw.rect(surf, bg, r)
            pygame.draw.rect(surf, border, r, width=1)
            draw_text(surf, fonts.body(16), lbl,
                      (255, 255, 255) if row_hover else T.TEXT,
                      (r.x + 10, r.centery - 9))
        if vis < n:      # Scroll-Hinweis
            bar = pygame.Rect(self.rect.right - 5, top, 3, vis * self.rect.h)
            pygame.draw.rect(surf, T.SURFACE_ALT, bar)
            bh = max(16, int(bar.h * vis / n))
            by = bar.y + int((bar.h - bh) * (start / max(1, n - vis)))
            pygame.draw.rect(surf, T.BORDER, (bar.x, by, 3, bh))


# --------------------------------------------------------------------------- #
class KeyBindField(Widget):
    def __init__(self, rect, code: int, on_change, *, conflict=False) -> None:
        super().__init__(rect)
        self.code = code
        self.on_change = on_change
        self.capturing = False
        self.conflict = conflict

    def handle_event(self, e) -> bool:
        if not (self.visible and self.enabled):
            return False
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.capturing = self.rect.collidepoint(e.pos)
            return self.capturing
        if e.type == pygame.KEYDOWN and self.capturing:
            if e.key != pygame.K_ESCAPE:
                self.code = e.key
                self.on_change(e.key)
            self.capturing = False
            return True
        return False

    def draw(self, surf, fonts) -> None:
        if not self.visible:
            return
        hover = self.hovered()
        if self.capturing:
            border, label = T.ACCENT, "druecke Taste..."
        elif self.conflict:
            border, label = T.DANGER, key_name(self.code)
        elif hover:
            border, label = T.ACCENT, key_name(self.code)
        else:
            border, label = T.BORDER, key_name(self.code)
        pygame.draw.rect(surf, T.SURFACE_ALT if hover and not self.capturing else T.BG,
                         self.rect, border_radius=T.R_SM)
        pygame.draw.rect(surf, border, self.rect,
                         width=2 if (self.capturing or self.conflict or hover) else 1,
                         border_radius=T.R_SM)
        draw_text(surf, fonts.body(15), label, T.TEXT if not self.conflict else T.DANGER, self.rect.center, center=True)


# --------------------------------------------------------------------------- #
from .clipboard import get_text as clipboard_get      # noqa: E402
from .clipboard import put_text as clipboard_put      # noqa: E402


class TextInput(Widget):
    """Einzeiliges Textfeld mit dem, was man von einem Textfeld erwartet.

    Schreibmarke, Pfeiltasten, Pos1/Ende, Entf, Markieren (Umschalt +
    Pfeile, Doppelklick, Ziehen mit der Maus) und Strg+C/V/X/A. Vorher
    konnte man nur hinten anhaengen - eine vertippte IP-Adresse musste man
    komplett neu tippen.
    """

    PAD = 10

    def __init__(self, rect, text: str, on_change, *, max_len=16, placeholder="") -> None:
        super().__init__(rect)
        self.text = text
        self.on_change = on_change
        self.max_len = max_len
        self.placeholder = placeholder
        self.focused = False
        self.caret = len(text)          # Position der Schreibmarke
        self.anchor = self.caret        # Anfang der Markierung
        self._drag = False
        self._font = None               # zuletzt benutzte Schrift (fuer Klicks)

    # -- Markierung -----------------------------------------------------
    @property
    def sel(self):
        a, b = sorted((self.anchor, self.caret))
        return a, b

    @property
    def has_sel(self) -> bool:
        return self.anchor != self.caret

    def select_all(self) -> None:
        self.anchor, self.caret = 0, len(self.text)

    def _set_caret(self, pos: int, keep_sel: bool = False) -> None:
        self.caret = max(0, min(len(self.text), pos))
        if not keep_sel:
            self.anchor = self.caret

    def _delete_sel(self) -> bool:
        if not self.has_sel:
            return False
        a, b = self.sel
        self._commit(self.text[:a] + self.text[b:])
        self._set_caret(a)
        return True

    def _commit(self, text: str) -> None:
        self.text = text[:self.max_len]
        self.on_change(self.text)

    def _insert(self, chunk: str) -> None:
        chunk = "".join(c for c in chunk if c.isprintable())
        if not chunk:
            return
        self._delete_sel()
        room = self.max_len - len(self.text)
        chunk = chunk[:max(0, room)]
        if not chunk:
            return
        at = self.caret
        self._commit(self.text[:at] + chunk + self.text[at:])
        self._set_caret(at + len(chunk))

    # -- Maus -----------------------------------------------------------
    def _index_at(self, x: int) -> int:
        """Welche Stelle im Text liegt unter diesem Bildschirm-x?"""
        font = self._font
        if font is None:
            return len(self.text)
        rel = x - (self.rect.x + self.PAD)
        best, best_d = 0, abs(rel)
        for i in range(1, len(self.text) + 1):
            d = abs(font.size(self.text[:i])[0] - rel)
            if d < best_d:
                best_d, best = d, i
        return best

    def handle_event(self, e) -> bool:
        if not (self.visible and self.enabled):
            return False

        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            inside = self.rect.collidepoint(e.pos)
            self.focused = inside
            if not inside:
                self._drag = False
                return False
            if getattr(e, "clicks", 1) >= 2:
                self.select_all()
            else:
                self._set_caret(self._index_at(e.pos[0]))
                self._drag = True
            return True
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self._drag = False
        if e.type == pygame.MOUSEMOTION and self._drag and self.focused:
            self._set_caret(self._index_at(e.pos[0]), keep_sel=True)
            return True

        if e.type != pygame.KEYDOWN or not self.focused:
            return False

        ctrl = bool(e.mod & pygame.KMOD_CTRL)
        shift = bool(e.mod & pygame.KMOD_SHIFT)

        if ctrl and e.key == pygame.K_a:
            self.select_all()
        elif ctrl and e.key in (pygame.K_c, pygame.K_x):
            a, b = self.sel
            clipboard_put(self.text[a:b] if self.has_sel else self.text)
            if e.key == pygame.K_x:
                if not self._delete_sel():
                    self._commit("")
                    self._set_caret(0)
        elif ctrl and e.key == pygame.K_v:
            self._insert(clipboard_get())
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB,
                       pygame.K_ESCAPE):
            self.focused = False
        elif e.key == pygame.K_LEFT:
            self._set_caret((self.sel[0] if self.has_sel and not shift
                             else self.caret - 1), keep_sel=shift)
        elif e.key == pygame.K_RIGHT:
            self._set_caret((self.sel[1] if self.has_sel and not shift
                             else self.caret + 1), keep_sel=shift)
        elif e.key == pygame.K_HOME:
            self._set_caret(0, keep_sel=shift)
        elif e.key == pygame.K_END:
            self._set_caret(len(self.text), keep_sel=shift)
        elif e.key == pygame.K_BACKSPACE:
            if not self._delete_sel() and self.caret > 0:
                at = self.caret
                self._commit(self.text[:at - 1] + self.text[at:])
                self._set_caret(at - 1)
        elif e.key == pygame.K_DELETE:
            if not self._delete_sel() and self.caret < len(self.text):
                at = self.caret
                self._commit(self.text[:at] + self.text[at + 1:])
                self._set_caret(at)
        elif e.unicode and e.unicode.isprintable():
            self._insert(e.unicode)
        return True

    def draw(self, surf, fonts) -> None:
        if not self.visible:
            return
        font = fonts.body(16)
        self._font = font
        hover = self.hovered()
        pygame.draw.rect(surf, T.SURFACE_ALT if hover and not self.focused else T.BG,
                         self.rect, border_radius=T.R_SM)
        pygame.draw.rect(surf, T.ACCENT if (self.focused or hover) else T.BORDER,
                         self.rect, width=2 if self.focused else 1,
                         border_radius=T.R_SM)

        x0 = self.rect.x + self.PAD
        y0 = self.rect.centery - 9
        prev = surf.get_clip()
        surf.set_clip(self.rect.inflate(-4, -4))

        if self.focused and self.has_sel:
            a, b = self.sel
            sx = x0 + font.size(self.text[:a])[0]
            sw = font.size(self.text[a:b])[0]
            pygame.draw.rect(surf, T.ACCENT_SOFT,
                             (sx, self.rect.y + 5, sw, self.rect.h - 10))

        if self.text:
            draw_text(surf, font, self.text, T.TEXT, (x0, y0))
        elif self.placeholder:
            draw_text(surf, font, self.placeholder, T.TEXT_MUTED, (x0, y0))

        if self.focused and (pygame.time.get_ticks() // 500) % 2 == 0:
            cx = x0 + font.size(self.text[:self.caret])[0]
            pygame.draw.line(surf, T.TEXT, (cx, self.rect.y + 6),
                             (cx, self.rect.bottom - 6), 2)
        surf.set_clip(prev)


# --------------------------------------------------------------------------- #
class ScrollPanel(Widget):
    """Container mit vertikalem Scrollen. Kinder werden in Inhaltskoordinaten
    positioniert; das Panel verschiebt sie beim Zeichnen/Event um scroll_y."""

    def __init__(self, rect, content_height: int) -> None:
        super().__init__(rect)
        self.children: list[Widget] = []
        self.content_height = content_height
        self.scroll_y = 0

    def add(self, w: Widget) -> Widget:
        self.children.append(w)
        return w

    def _max_scroll(self) -> int:
        return max(0, self.content_height - self.rect.h)

    def _clamp(self, v: int) -> int:
        return max(0, min(self._max_scroll(), int(v)))

    def handle_event(self, e) -> bool:
        if not self.visible:
            return False
        if e.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if self.rect.collidepoint(mx, my):
                self.scroll_y = self._clamp(self.scroll_y - e.y * 40)
                return True
        if e.type == pygame.MOUSEBUTTONDOWN and e.button in (4, 5) and self.rect.collidepoint(e.pos):
            self.scroll_y = self._clamp(self.scroll_y + (-40 if e.button == 4 else 40))
            return True

        # Kinder bleiben in Inhaltskoordinaten; nur die Event-Position wird
        # von Bildschirm- in Inhaltskoordinaten uebersetzt.
        if hasattr(e, "pos"):
            if e.type == pygame.MOUSEBUTTONDOWN and not self.rect.collidepoint(e.pos):
                return False
            ce = pygame.event.Event(e.type, {**e.dict, "pos": (e.pos[0], e.pos[1] + self.scroll_y)})
        else:
            ce = e

        used = False
        for c in self.children:
            if c.handle_event(ce):
                used = True
        return used

    def update(self, dt: float) -> None:
        for c in self.children:
            c.update(dt)

    def draw(self, surf, fonts) -> None:
        if not self.visible:
            return
        prev_clip = surf.get_clip()
        surf.set_clip(self.rect)
        set_hover_clip(self.rect)
        for c in self.children:
            c.rect.y -= self.scroll_y
            visible = c.rect.bottom >= self.rect.y - 40 and c.rect.y <= self.rect.bottom + 40
            if visible:
                c.draw(surf, fonts)
            c.rect.y += self.scroll_y
        set_hover_clip(None)
        surf.set_clip(prev_clip)
        # Scrollbalken
        if self._max_scroll() > 0:
            track = pygame.Rect(self.rect.right - 6, self.rect.y, 4, self.rect.h)
            pygame.draw.rect(surf, T.SURFACE_ALT, track, border_radius=2)
            frac = self.rect.h / self.content_height
            bh = max(24, int(self.rect.h * frac))
            by = self.rect.y + int((self.rect.h - bh) * (self.scroll_y / self._max_scroll()))
            pygame.draw.rect(surf, T.BORDER, (track.x, by, 4, bh), border_radius=2)
