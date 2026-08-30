"""Laengenpraefigierte JSON-Frames ueber TCP.

Frame = 4 Byte big-endian Laenge + UTF-8-JSON.
"""

from __future__ import annotations

import json
import struct

HEADER = struct.Struct(">I")
MAX_FRAME = 8 * 1024 * 1024


def encode(obj) -> bytes:
    data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    return HEADER.pack(len(data)) + data


def send_msg(sock, obj) -> None:
    sock.sendall(encode(obj))


class FrameReader:
    """Bytes reinfuettern, fertige Nachrichten rausholen."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, chunk: bytes):
        self._buf += chunk
        while len(self._buf) >= HEADER.size:
            (length,) = HEADER.unpack_from(self._buf)
            if length > MAX_FRAME:
                self._buf.clear()
                return
            if len(self._buf) < HEADER.size + length:
                return
            payload = bytes(self._buf[HEADER.size : HEADER.size + length])
            del self._buf[: HEADER.size + length]
            try:
                yield json.loads(payload.decode("utf-8"))
            except ValueError:
                continue
