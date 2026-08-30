from __future__ import annotations

import sys

from rucurve.app import App


def main() -> int:
    App().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
