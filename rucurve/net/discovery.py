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

_BROADCAST_ADDRS = ("255.255.255.255", "<broadcast>")


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
        while self._running and self._sock:
            try:
                payload = json.dumps({"app": "ru-curve", **self._info()}).encode("utf-8")
                for addr in _BROADCAST_ADDRS:
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

    def start(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", DISCOVERY_PORT))
        except OSError:
            sock.close()
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
