"""Ru-Curve - Startpunkt.

    python main.py            normal starten
    python main.py --windowed Vollbild-Einstellung ignorieren
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Ru-Curve - Achtung die Kurve")
    parser.add_argument("--windowed", action="store_true", help="immer im Fenster starten")
    parser.add_argument("--no-audio", action="store_true", help="Ton komplett aus")
    args = parser.parse_args()

    if args.no_audio:
        import os

        os.environ["SDL_AUDIODRIVER"] = "dummy"

    from rucurve.app import App

    app = App()
    if args.windowed and app.config.settings.fullscreen:
        app.config.settings.fullscreen = False
        app.rebuild_window()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
