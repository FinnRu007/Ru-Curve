"""Oeffentliche IP ermitteln + Update-Pruefung - beides im Hintergrund.

Beides sind kurze HTTPS-Anfragen, die nie den Spielablauf blockieren duerfen:
sie laufen in Daemon-Threads und melden ihr Ergebnis ueber Attribute.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import rucurve

# Dienste, die nur die eigene oeffentliche IP zurueckgeben (Klartext)
IP_SERVICES = (
    "https://api.ipify.org",
    "https://ipv4.icanhazip.com",
    "https://checkip.amazonaws.com",
)

# Dort liegt die aktuelle Version (wird von der Ru-Services-Seite geliefert)
VERSION_URL = "https://finnru007.github.io/Ru-Services/version.json"
DOWNLOAD_PAGE = "https://finnru007.github.io/Ru-Services/"

USER_AGENT = "Ru-Curve/%s" % rucurve.__version__


def _get(url: str, timeout: float = 4.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace").strip()


# --------------------------------------------------------------------------- #
class PublicIP:
    """Fragt die oeffentliche IP ab (fuer Spielen uebers Internet)."""

    def __init__(self) -> None:
        self.ip = ""
        self.done = False
        self.error = ""

    def start(self) -> None:
        threading.Thread(target=self._run, name="public-ip", daemon=True).start()

    def _run(self) -> None:
        for url in IP_SERVICES:
            try:
                text = _get(url).split()[0]
            except (urllib.error.URLError, OSError, ValueError, IndexError) as exc:
                self.error = str(exc)[:60]
                continue
            if _looks_like_ip(text):
                self.ip = text
                break
        self.done = True


def _looks_like_ip(text: str) -> bool:
    parts = text.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


# --------------------------------------------------------------------------- #
def parse_version(text: str) -> tuple:
    """'1.2.3' -> (1, 2, 3); unbekanntes wird zu (0,)."""
    nums = []
    for chunk in str(text).strip().lstrip("vV").split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        nums.append(int(digits) if digits else 0)
    return tuple(nums) or (0,)


def is_newer(remote: str, local: str) -> bool:
    a, b = parse_version(remote), parse_version(local)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return a > b


class UpdateCheck:
    """Schaut auf der Ru-Services-Seite nach einer neueren Version."""

    def __init__(self, current: str | None = None, url: str = VERSION_URL) -> None:
        self.current = current or rucurve.__version__
        self.url = url
        self.latest = ""
        self.notes = ""
        self.page = DOWNLOAD_PAGE
        self.available = False
        self.done = False
        self.error = ""

    def start(self) -> None:
        threading.Thread(target=self._run, name="update-check", daemon=True).start()

    def _run(self) -> None:
        try:
            data = json.loads(_get(self.url, timeout=5.0))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self.error = str(exc)[:70]
            self.done = True
            return
        self.apply(data)
        self.done = True

    def apply(self, data: dict) -> None:
        """Getrennt, damit es sich ohne Netz testen laesst."""
        self.latest = str(data.get("version", "")).strip()
        self.notes = str(data.get("notes", "")).strip()
        self.page = str(data.get("page", DOWNLOAD_PAGE)).strip() or DOWNLOAD_PAGE
        self.available = bool(self.latest) and is_newer(self.latest, self.current)
