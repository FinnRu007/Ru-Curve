"""Autoritativer Spiel-Host: nimmt TCP-Verbindungen an, sammelt Nachrichten,
broadcastet an alle Clients. Alle Sockets laufen in Daemon-Threads; die
Spiel-Logik ruft nur `poll()` / `broadcast()` aus dem Hauptthread."""

from __future__ import annotations

import queue
import socket
import threading

from .protocol import FrameReader, encode


class _Client:
    def __init__(self, cid: int, sock: socket.socket, addr) -> None:
        self.cid = cid
        self.sock = sock
        self.addr = addr
        self.name = f"Client {cid}"
        self.lock = threading.Lock()
        self.alive = True


class GameHost:
    def __init__(self, port: int) -> None:
        self.port = port
        self._srv: socket.socket | None = None
        self._clients: dict[int, _Client] = {}
        self._next_id = 1
        self._inbox: "queue.Queue[tuple[int, dict]]" = queue.Queue()
        self._running = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("0.0.0.0", self.port))
        self._srv.listen(16)
        self._running = True
        threading.Thread(target=self._accept_loop, name="host-accept", daemon=True).start()

    def stop(self) -> None:
        self._running = False
        with self._lock:
            clients = list(self._clients.values())
        for c in clients:
            self._drop(c.cid, notify=False)
        if self._srv:
            try:
                self._srv.close()
            except OSError:
                pass
            self._srv = None

    # ------------------------------------------------------------------ #
    def _accept_loop(self) -> None:
        while self._running and self._srv:
            try:
                sock, addr = self._srv.accept()
            except OSError:
                break
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with self._lock:
                cid = self._next_id
                self._next_id += 1
                client = _Client(cid, sock, addr)
                self._clients[cid] = client
            self._inbox.put((cid, {"type": "__connect__", "addr": addr[0]}))
            threading.Thread(target=self._read_loop, args=(client,), name=f"host-cli-{cid}", daemon=True).start()

    def _read_loop(self, client: _Client) -> None:
        reader = FrameReader()
        try:
            while self._running and client.alive:
                chunk = client.sock.recv(65536)
                if not chunk:
                    break
                for msg in reader.feed(chunk):
                    self._inbox.put((client.cid, msg))
        except OSError:
            pass
        finally:
            self._drop(client.cid, notify=True)

    def _drop(self, cid: int, notify: bool) -> None:
        with self._lock:
            client = self._clients.pop(cid, None)
        if client is None:
            return
        client.alive = False
        try:
            client.sock.close()
        except OSError:
            pass
        if notify:
            self._inbox.put((cid, {"type": "__disconnect__"}))

    # ------------------------------------------------------------------ #
    def poll(self) -> list[tuple[int, dict]]:
        out: list[tuple[int, dict]] = []
        while True:
            try:
                out.append(self._inbox.get_nowait())
            except queue.Empty:
                break
        return out

    def send(self, cid: int, obj) -> None:
        with self._lock:
            client = self._clients.get(cid)
        if client is None:
            return
        data = encode(obj)
        try:
            with client.lock:
                client.sock.sendall(data)
        except OSError:
            self._drop(cid, notify=True)

    def broadcast(self, obj, *, exclude: int | None = None) -> None:
        data = encode(obj)
        with self._lock:
            clients = list(self._clients.values())
        for client in clients:
            if client.cid == exclude:
                continue
            try:
                with client.lock:
                    client.sock.sendall(data)
            except OSError:
                self._drop(client.cid, notify=True)

    def set_name(self, cid: int, name: str) -> None:
        with self._lock:
            if cid in self._clients:
                self._clients[cid].name = name

    @property
    def client_ids(self) -> list[int]:
        with self._lock:
            return list(self._clients)

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)
