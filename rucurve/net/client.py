"""Spiel-Client: verbindet sich mit einem Host, sendet Eingaben, empfaengt
Snapshots. Empfang laeuft in einem Daemon-Thread, die Spiel-Logik ruft `poll()`."""

from __future__ import annotations

import queue
import socket
import threading

from .protocol import FrameReader, encode


class GameClient:
    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._inbox: "queue.Queue[dict]" = queue.Queue()
        self._running = False
        self._lock = threading.Lock()
        self.connected = False
        self.error: str | None = None

    def connect(self, host: str, port: int, timeout: float = 4.0) -> bool:
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
        except OSError as exc:
            self.error = str(exc)
            return False
        sock.settimeout(None)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock = sock
        self._running = True
        self.connected = True
        threading.Thread(target=self._read_loop, name="client-read", daemon=True).start()
        return True

    def _read_loop(self) -> None:
        reader = FrameReader()
        try:
            while self._running and self._sock:
                chunk = self._sock.recv(65536)
                if not chunk:
                    break
                for msg in reader.feed(chunk):
                    self._inbox.put(msg)
        except OSError:
            pass
        finally:
            self.connected = False
            self._inbox.put({"type": "__disconnect__"})

    def send(self, obj) -> None:
        if not self._sock:
            return
        try:
            with self._lock:
                self._sock.sendall(encode(obj))
        except OSError:
            self.connected = False

    def poll(self) -> list[dict]:
        out: list[dict] = []
        while True:
            try:
                out.append(self._inbox.get_nowait())
            except queue.Empty:
                break
        return out

    def close(self) -> None:
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
