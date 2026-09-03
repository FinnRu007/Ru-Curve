"""Alles Anklickbare muss sich unter der Maus sichtbar veraendern.

Der Test vergleicht Pixel: einmal mit der Maus weit weg, einmal darauf. Ein
Widget, das sich dabei nicht ruehrt, faellt auf - egal ob jemand spaeter ein
neues hinzufuegt und den Hover vergisst.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["RUCURVE_CONFIG"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_tmp", "config.json")

import pygame  # noqa: E402

from rucurve.app import App  # noqa: E402
from rucurve.ui.widgets import (  # noqa: E402
    Label,
    ScrollPanel,
    take_hover,
)

FAR = (2, 2)          # Ecke ohne Bedienelemente

_app = None


def app():
    global _app
    if _app is None:
        _app = App()
    return _app


def render(scene, pos):
    pygame.mouse.set_pos(pos)
    pygame.event.pump()
    take_hover()
    scene.draw(app().screen)
    return app().screen.copy(), take_hover()


def patch(surf, rect):
    rect = rect.clip(surf.get_rect())
    if rect.w <= 0 or rect.h <= 0:
        return None
    return pygame.image.tostring(surf.subsurface(rect), "RGB")


def clickable(scene):
    """(Name, Rechteck auf dem Bildschirm) aller anklickbaren Elemente."""
    out = []

    def walk(widgets, dy=0):
        for w in widgets:
            if isinstance(w, ScrollPanel):
                for c in w.children:
                    scr = c.rect.move(0, -w.scroll_y)
                    if w.rect.contains(scr):
                        walk([c], 0)
                continue
            if isinstance(w, Label):
                continue
            if type(w).__name__ in ("_RowLabel", "_SubHead", "_Static", "_Mini"):
                continue
            if not getattr(w, "visible", True) or not getattr(w, "enabled", True):
                continue
            r = w.rect.move(0, dy)
            if r.w < 6 or r.h < 6:
                continue
            out.append((type(w).__name__, pygame.Rect(r)))

    walk(list(getattr(scene, "widgets", [])))
    walk(list(getattr(scene, "_picker_widgets", [])))
    return out


def check_scene(scene, label, skip=()):
    scene.on_enter()
    base, _ = render(scene, FAR)
    items = clickable(scene)
    assert items, "%s: nichts Anklickbares gefunden" % label
    dead = []
    for name, rect in items:
        if name in skip:
            continue
        shot, saw = render(scene, rect.center)
        if not saw:
            dead.append("%s (meldet sich gar nicht)" % name)
            continue
        if patch(base, rect) == patch(shot, rect):
            dead.append("%s bei %s (sieht gleich aus)" % (name, tuple(rect.topleft)))
        # und wieder zurueck, damit der naechste Vergleich sauber ist
        base, _ = render(scene, FAR)
    assert not dead, "%s ohne Hover-Markierung: %s" % (label, ", ".join(dead))
    return len(items)


# =========================================================================== #
def test_menu_marks_everything():
    from rucurve.scenes.menu import MenuScene

    n = check_scene(MenuScene(app()), "Hauptmenue")
    assert n >= 6, "nur %d Knoepfe geprueft" % n


def test_lobby_marks_everything_including_the_colour_swatch():
    from rucurve.scenes.lobby import LobbyScene

    sc = LobbyScene(app(), "local")
    n = check_scene(sc, "Lobby")
    assert n >= 8, "nur %d Elemente geprueft" % n
    names = {name for name, _r in clickable(sc)}
    assert "_Swatch" in names, "Farbfeld war nicht dabei"
    assert "Dropdown" in names and "TextInput" in names


def test_game_picker_marks_everything():
    from rucurve.scenes.lobby import LobbyScene

    sc = LobbyScene(app(), "local")
    sc.on_enter()
    sc._open_picker()
    base, _ = render(sc, FAR)
    # Nur die Knoepfe der Auswahl - die Lobby dahinter liegt unter dem Schleier
    # und darf sich beim Ueberfahren gerade NICHT ruehren.
    for wgt in sc._picker_widgets:
        rect = wgt.rect
        shot, saw = render(sc, rect.center)
        assert saw, "Spielauswahl: Knopf meldet keinen Hover"
        assert patch(base, rect) != patch(shot, rect), "Spielauswahl ohne Markierung"


def test_settings_marks_sliders_numbers_and_toggles():
    from rucurve.scenes.settings_scene import SettingsScene

    sc = SettingsScene(app(), lambda: None)
    sc.on_enter()
    panel = next(w for w in sc.widgets if isinstance(w, ScrollPanel))
    panel.children[0].on_click()            # ersten Bereich aufklappen
    names = {name for name, _r in clickable(sc)}
    assert {"Slider", "NumberField", "Toggle"} <= names, names
    check_scene(sc, "Einstellungen")


def test_controls_page_marks_the_key_fields():
    from rucurve.scenes.controls import ControlsScene

    sc = ControlsScene(app(), lambda: None)
    sc.on_enter()
    names = {name for name, _r in clickable(sc)}
    assert "KeyBindField" in names, names
    check_scene(sc, "Steuerung")


def test_join_page_marks_everything():
    from rucurve.scenes.join import JoinScene

    sc = JoinScene(app())
    try:
        check_scene(sc, "Beitreten")
    finally:
        sc.on_exit()


def test_nothing_under_the_mouse_means_no_marking():
    from rucurve.scenes.menu import MenuScene

    sc = MenuScene(app())
    sc.on_enter()
    _shot, saw = render(sc, FAR)
    assert not saw, "leere Stelle meldet trotzdem etwas unter der Maus"


def test_cursor_switches_to_a_hand():
    from rucurve.scenes.menu import MenuScene

    a = app()
    sc = MenuScene(a)
    sc.on_enter()
    a.scene = sc
    rect = clickable(sc)[0][1]
    pygame.mouse.set_pos(rect.center)
    pygame.event.pump()
    take_hover()
    sc.draw(a.screen)
    a._update_cursor()
    assert a._cursor == pygame.SYSTEM_CURSOR_HAND, "kein Handzeiger ueber dem Knopf"

    pygame.mouse.set_pos(FAR)
    pygame.event.pump()
    take_hover()
    sc.draw(a.screen)
    a._update_cursor()
    assert a._cursor == pygame.SYSTEM_CURSOR_ARROW, "Handzeiger blieb haengen"


if __name__ == "__main__":
    import traceback

    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok   %s" % name)
            except Exception:
                fails += 1
                print("FAIL %s" % name)
                traceback.print_exc()
    sys.exit(1 if fails else 0)
