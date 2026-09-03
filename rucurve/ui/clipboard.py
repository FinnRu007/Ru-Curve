"""Zwischenablage - ausschliesslich ueber SDL (pygame.scrap).

**Warum nur SDL und nicht ueber die Windows-API?**

Eine fruehere Fassung sprach `user32` direkt an (OpenClipboard, GlobalAlloc,
memmove, SetClipboardData), damit das Kopieren auch dann klappt, wenn SDL
die Zwischenablage gerade nicht bekommt. Genau diese Aufruffolge ist aber
das Erkennungsmuster fuer Schadsoftware, die Zwischenablagen ausliest -
Windows Defender hat die fertige .exe daraufhin als
`Trojan:Win32/Wacatac.B!ml` eingestuft und geloescht, auch beim Download von
der Webseite.

Das ist den Aufwand nicht wert: ein Spiel, das als Virus gemeldet wird,
laedt niemand herunter. SDL macht dasselbe ueber einen Weg, der nicht
auffaellt. Klappt es einmal nicht, sagt das Programm das ehrlich, statt so
zu tun, als waere kopiert worden - siehe `LobbyScene.copy_address`.
"""

from __future__ import annotations


def put_text(text: str) -> bool:
    """Text in die Zwischenablage. True nur, wenn es wirklich geklappt hat."""
    try:
        import pygame

        pygame.scrap.put_text(str(text))
        return True
    except Exception:
        return False


def get_text() -> str:
    """Erste Zeile aus der Zwischenablage - leer, wenn nichts zu holen ist."""
    try:
        import pygame

        got = pygame.scrap.get_text()
    except Exception:
        return ""
    if not got:
        return ""
    return got.replace("\r", "").split("\n")[0]
