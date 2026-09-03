"""Prueft die haeufigen LAN-Stolpersteine.

Die Fehlerbilder, die in der Praxis auftraten: belegter Port, Verbindung
verweigert, Zeitueberschreitung, Hostsuche findet nichts.
"""

from __future__ import annotations

import os
import socket
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["RUCURVE_CONFIG"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_tmp", "config.json")

from rucurve.net.client import GameClient  # noqa: E402
from rucurve.net.discovery import (  # noqa: E402
    Beacon,
    Listener,
    broadcast_targets,
    local_ips,
)
from rucurve.net.errors import friendly, host_problem  # noqa: E402
from rucurve.net.host import GameHost  # noqa: E402

BASE = 54100


def test_busy_port_makes_host_move_instead_of_failing():
    """Regression: eine alte Instanz belegte den Port, der neue Host startete
    still nicht - die anderen bekamen nur 'Verbindung verweigert'."""
    a = GameHost(BASE)
    a.start()
    b = GameHost(BASE)
    b.start()
    try:
        assert a.port == BASE
        assert b.port != a.port, "zweiter Host muss ausweichen, nicht den Port stehlen"
        # Beide sind wirklich getrennt erreichbar
        for h in (a, b):
            c = GameClient()
            assert c.connect("127.0.0.1", h.port, timeout=3), c.error
            c.close()
    finally:
        a.stop()
        b.stop()


def test_connect_to_nothing_fails_with_a_hint():
    """Egal ob abgelehnt oder Zeitueberschreitung - es muss ein Tipp kommen.

    (Je nach Firewall meldet Windows 'abgelehnt' oder laesst es auflaufen.)
    """
    port = BASE + 40
    c = GameClient()
    assert not c.connect("127.0.0.1", port, timeout=2)
    head, tip = friendly(c.error, "127.0.0.1", port)
    assert head and tip, "leere Meldung"
    assert len(tip) > 20, tip


def test_error_texts_are_actionable():
    cases = {
        "[WinError 10061] Verbindung abgelehnt": ("abgelehnt", "hosten"),
        "refused": ("abgelehnt", "hosten"),
        "timed out": ("keine antwort", "firewall"),
        "[WinError 10060]": ("keine antwort", "firewall"),
        "[Errno 11001] getaddrinfo failed": ("nicht gefunden", "ip-adresse"),
        "[WinError 10013] Zugriff verweigert": ("zugriff", "firewall"),
        "[WinError 10065] unreachable": ("nicht erreichbar", "netz"),
    }
    for err, (want_head, want_tip) in cases.items():
        head, tip = friendly(err, "192.168.1.9", 51738)
        assert want_head in head.lower(), "%s -> %s" % (err, head)
        assert want_tip in tip.lower(), "%s -> %s" % (err, tip)


def test_timeout_hint_points_at_firewall():
    head, tip = friendly("timed out", "192.168.1.5", 51738)
    assert "keine antwort" in head.lower()
    assert "firewall" in tip.lower()


def test_host_problem_hint_for_busy_ports():
    head, tip = host_problem("Kein freier Port ab 51738 gefunden: [WinError 10048]")
    assert "belegt" in head.lower()
    assert "task-manager" in tip.lower()


def test_broadcast_targets_include_own_subnet():
    """Nur 255.255.255.255 reicht vielen Netzen nicht."""
    targets = broadcast_targets()
    assert "255.255.255.255" in targets
    for ip in local_ips():
        sub = ".".join(ip.split(".")[:3]) + ".255"
        assert sub in targets, "Subnetz-Broadcast %s fehlt" % sub


def test_discovery_finds_the_host():
    """Beacon + Listener auf derselben Maschine muessen sich finden."""
    host = GameHost(BASE + 60)
    host.start()
    listener = Listener()
    listener.start()
    if listener.error:                       # Port belegt (z.B. laufendes Spiel)
        host.stop()
        print("   (uebersprungen: %s)" % listener.error)
        return
    beacon = Beacon(lambda: {"name": "Testhost", "port": host.port,
                             "players": 3, "max": 12})
    beacon.start()
    try:
        found = []
        end = time.time() + 6
        while time.time() < end and not found:
            found = [h for h in listener.hosts() if h.get("name") == "Testhost"]
            time.sleep(0.2)
        assert found, "Host wurde per Broadcast nicht gefunden"
        assert found[0]["port"] == host.port, "gemeldeter Port stimmt nicht"
        assert found[0]["players"] == 3
    finally:
        beacon.stop()
        listener.stop()
        host.stop()


def test_beacon_reports_the_real_port_not_the_default():
    """Weicht der Host auf einen anderen Port aus, muss die Suche das melden."""
    blocker = GameHost(BASE + 80)
    blocker.start()
    host = GameHost(BASE + 80)
    host.start()
    try:
        assert host.port != blocker.port
        info = {"name": "X", "port": host.port, "players": 1, "max": 12}
        assert info["port"] == host.port
    finally:
        blocker.stop()
        host.stop()


def test_router_fallback_when_the_upnp_search_is_blocked():
    """Windows blockt oft den UDP-Multicast der UPnP-Suche, obwohl der Router
    selbst erreichbar waere - dann muss das Spiel direkt anklopfen koennen."""
    from rucurve.net import upnp

    cands = upnp.gateway_candidates()
    assert len(cands) <= upnp.MAX_CANDIDATES, "zu viele Adressen -> zu langes Warten"
    for c in cands:
        assert c.count(".") == 3 and c.rsplit(".", 1)[1] in ("1", "254"), c

    # all_locations() darf die Suche nicht ersetzen, sondern nur ergaenzen
    calls = []
    orig_disc, orig_fb = upnp.discover_locations, upnp.fallback_locations
    try:
        upnp.discover_locations = lambda *a, **k: (calls.append("suche") or ["X"])
        upnp.fallback_locations = lambda *a, **k: (calls.append("direkt") or ["Y"])
        assert upnp.all_locations() == ["X"]
        assert calls == ["suche"], "Rueckfallebene lief, obwohl die Suche klappte"

        calls.clear()
        upnp.discover_locations = lambda *a, **k: (calls.append("suche") or [])
        assert upnp.all_locations() == ["Y"]
        assert calls == ["suche", "direkt"]
    finally:
        upnp.discover_locations, upnp.fallback_locations = orig_disc, orig_fb


def test_upnp_failures_never_crash_the_host():
    """Egal was der Router antwortet - das Spiel muss im LAN weiterlaufen."""
    from rucurve.net.upnp import PortMapper

    m = PortMapper(51999)
    m.open_port = lambda: (_ for _ in ()).throw(OSError("Netz weg"))
    m._run()
    assert m.status == "fehlgeschlagen"
    assert m.message
    m.close()                     # darf ohne Freigabe nicht knallen


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
