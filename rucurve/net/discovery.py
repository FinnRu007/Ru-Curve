"""LAN-Erkennung per UDP-Broadcast.

Der Host sendet 1x/s ein kleines JSON-Paket auf DISCOVERY_PORT, der Beitreten-
Bildschirm hoert zu und listet die gefundenen Hosts.
"""

from __future__ import annotations

import json
import socket
import threading
import time

from ..config import DISCOVERY_PORT

def local_ips() -> list:
    """Alle IPv4-Adressen dieses Rechners (mehrere bei WLAN + LAN + VPN)."""
    ips = set()
    try:
        ips.add(local_ip())
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(a for a in ips if a and not a.startswith("127."))


def broadcast_targets() -> list:
    """Wohin das Suchsignal geht.

    Nur 255.255.255.255 reicht oft nicht - viele Windows-Setups und Router
    verwerfen den globalen Broadcast. Darum zusaetzlich der Broadcast des
    eigenen Subnetzes (z.B. 192.168.178.255) fuer jede lokale Adresse.
    """
    targets = ["255.255.255.255"]
    for ip in local_ips():
        parts = ip.split(".")
        if len(parts) == 4:
            sub = ".".join(parts[:3]) + ".255"
            if sub not in targets:
                targets.append(sub)
    return targets


class Beacon:
    def __init__(self, info_provider) -> None:
        self._info = info_provider          # callable -> dict
        self._running = False
        self._sock: socket.socket | None = None

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._running = True
        threading.Thread(target=self._loop, name="beacon", daemon=True).start()

    def _loop(self) -> None:
        targets = broadcast_targets()
        n = 0
        while self._running and self._sock:
            n += 1
            if n % 10 == 0:                 # Netzwerk kann sich aendern (WLAN)
                targets = broadcast_targets()
            try:
                payload = json.dumps({"app": "ru-curve", **self._info()}).encode("utf-8")
                for addr in targets:
                    try:
                        self._sock.sendto(payload, (addr, DISCOVERY_PORT))
                    except OSError:
                        pass
            except OSError:
                pass
            time.sleep(1.0)

    def stop(self) -> None:
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None


class Listener:
    def __init__(self) -> None:
        self._running = False
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._found: dict[str, dict] = {}   # ip -> {name, port, players, max, ts}
        self.error: str | None = None

    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", DISCOVERY_PORT))
        except OSError as exc:
            sock.close()
            self.error = str(exc)
            return
        sock.settimeout(0.5)
        self._sock = sock
        self._running = True
        threading.Thread(target=self._loop, name="discovery-listen", daemon=True).start()

    def _loop(self) -> None:
        while self._running and self._sock:
            try:
                data, addr = self._sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                info = json.loads(data.decode("utf-8"))
            except ValueError:
                continue
            if info.get("app") != "ru-curve":
                continue
            with self._lock:
                self._found[addr[0]] = {
                    "ip": addr[0],
                    "name": info.get("name", "Host"),
                    "port": int(info.get("port", 0)),
                    "players": int(info.get("players", 0)),
                    "max": int(info.get("max", 0)),
                    "ts": time.time(),
                }

    def hosts(self, max_age: float = 4.0) -> list[dict]:
        now = time.time()
        with self._lock:
            return sorted(
                (h for h in self._found.values() if now - h["ts"] <= max_age),
                key=lambda h: h["name"],
            )

    def stop(self) -> None:
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None


def local_ip() -> str:
    """Beste Vermutung fuer die LAN-IP dieses Rechners."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
