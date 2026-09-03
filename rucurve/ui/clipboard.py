"""Zwischenablage - mit Rueckfallebenen, weil ein Weg allein nicht reicht.

SDL (pygame.scrap) ist der einfachste Weg, scheitert unter Windows aber
regelmaessig mit "Zugriff verweigert": die Zwischenablage kann immer nur ein
Programm gleichzeitig offen haben, und irgendeins hat sie oft gerade auf.
Deshalb der Reihe nach:

  1. pygame.scrap
  2. Windows direkt ueber user32 (mit mehreren Versuchen, weil genau dieses
     Belegen die uebliche Fehlerquelle ist)

Kein tkinter als dritter Weg: ein zweites Fenster neben dem laufenden Spiel
zu oeffnen kostet den Fokus, und beim Ausprobieren blieb der Aufruf haengen.
Ein haengendes Spiel ist schlimmer als eine Zwischenablage, die einmal nicht
funktioniert.

Zwei Dinge waren beim Bauen wichtig:

* **Jeder Rueckgabewert wird geprueft.** Schlaegt `OpenClipboard` fehl und
  man arbeitet trotzdem weiter, stuerzt das Programm ab - genau das ist beim
  Entwickeln passiert.
* **argtypes/restype muessen gesetzt sein.** Ohne sie kuerzt ctypes 64-Bit-
  Handles auf 32 Bit, und man uebergibt Windows einen kaputten Zeiger.

Klappt gar nichts, geben die Funktionen das ehrlich zurueck - der Aufrufer
zeigt dann einen Hinweis, statt so zu tun, als waere kopiert worden.
"""

from __future__ import annotations

import sys
import time

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
_IS_WINDOWS = sys.platform.startswith("win")


# --------------------------------------------------------------------------- #
def _pygame_put(text: str) -> bool:
    try:
        import pygame

        pygame.scrap.put_text(text)
        return True
    except Exception:
        return False


def _pygame_get() -> str | None:
    try:
        import pygame

        return pygame.scrap.get_text() or None
    except Exception:
        return None


# --------------------------------------------------------------------------- #
def _win_api():
    """user32/kernel32 mit vollstaendig gesetzten Signaturen."""
    import ctypes
    from ctypes import wintypes

    u = ctypes.windll.user32
    k = ctypes.windll.kernel32
    u.OpenClipboard.argtypes = [wintypes.HWND]
    u.OpenClipboard.restype = wintypes.BOOL
    u.CloseClipboard.argtypes = []
    u.CloseClipboard.restype = wintypes.BOOL
    u.EmptyClipboard.argtypes = []
    u.EmptyClipboard.restype = wintypes.BOOL
    u.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    u.SetClipboardData.restype = wintypes.HANDLE
    u.GetClipboardData.argtypes = [wintypes.UINT]
    u.GetClipboardData.restype = wintypes.HANDLE
    k.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k.GlobalAlloc.restype = wintypes.HGLOBAL
    k.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    k.GlobalUnlock.restype = wintypes.BOOL
    k.GlobalFree.argtypes = [wintypes.HGLOBAL]
    k.GlobalFree.restype = wintypes.HGLOBAL
    return ctypes, u, k


def _win_open(u, tries: int = 6) -> bool:
    for i in range(tries):
        if u.OpenClipboard(None):
            return True
        time.sleep(0.02 * (i + 1))
    return False


def _win_put(text: str) -> bool:
    if not _IS_WINDOWS:
        return False
    try:
        ctypes, u, k = _win_api()
    except Exception:
        return False
    try:
        if not _win_open(u):
            return False
        handle = None
        try:
            if not u.EmptyClipboard():
                return False
            buf = ctypes.create_unicode_buffer(text)
            size = ctypes.sizeof(buf)
            handle = k.GlobalAlloc(GMEM_MOVEABLE, size)
            if not handle:
                return False
            target = k.GlobalLock(handle)
            if not target:
                return False
            ctypes.memmove(target, ctypes.byref(buf), size)
            k.GlobalUnlock(handle)
            if not u.SetClipboardData(CF_UNICODETEXT, handle):
                return False
            handle = None            # gehoert jetzt Windows
            return True
        finally:
            if handle:
                k.GlobalFree(handle)
            u.CloseClipboard()
    except Exception:
        return False


def _win_get() -> str | None:
    if not _IS_WINDOWS:
        return None
    try:
        ctypes, u, k = _win_api()
    except Exception:
        return None
    try:
        if not _win_open(u):
            return None
        try:
            handle = u.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            ptr = k.GlobalLock(handle)
            if not ptr:
                return None
            try:
                return ctypes.c_wchar_p(ptr).value or None
            finally:
                k.GlobalUnlock(handle)
        finally:
            u.CloseClipboard()
    except Exception:
        return None


# --------------------------------------------------------------------------- #
def put_text(text: str) -> bool:
    """Text in die Zwischenablage. True nur, wenn es wirklich geklappt hat."""
    text = str(text)
    for fn in (_pygame_put, _win_put):
        try:
            if fn(text):
                return True
        except Exception:
            continue
    return False


def get_text() -> str:
    """Erste Zeile aus der Zwischenablage - leer, wenn nichts zu holen ist."""
    for fn in (_pygame_get, _win_get):
        try:
            got = fn()
        except Exception:
            continue
        if got:
            return got.replace("\r", "").split("\n")[0]
    return ""
