# -*- coding: utf-8 -*-
"""Prueft, ob Spielen uebers Internet an diesem Anschluss moeglich ist.

Beantwortet drei Fragen in dieser Reihenfolge:

  1. Findet das Spiel den Router ueberhaupt (UPnP)?
  2. Hat der Anschluss eine ECHTE oeffentliche IPv4-Adresse?
     Dafuer wird die Adresse, die der Router als "aussen" meldet, mit der
     verglichen, die ein Dienst im Internet sieht. Weichen sie ab, sitzt der
     Anschluss hinter DS-Lite/CGNAT - dann hilft KEINE Portfreigabe.
  3. Laesst der Router eine selbsttaetige Portfreigabe zu?

Aufruf:   python tools/netz_pruefen.py
"""

from __future__ import annotations

import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rucurve.config import DEFAULT_GAME_PORT  # noqa: E402
from rucurve.net.internet import PublicIP  # noqa: E402
from rucurve.net.upnp import (  # noqa: E402
    PortMapper,
    _local_ip_towards,
    all_locations,
    discover_locations,
    fallback_locations,
    parse_services,
)


def head(text):
    print()
    print(text)
    print("-" * len(text))


def main(port=DEFAULT_GAME_PORT):
    auto_ok = False
    print("Ru-Curve - Netzwerkpruefung fuer das Spielen uebers Internet")
    print("Port: %d" % port)

    # -- 1. Router finden ------------------------------------------------
    head("1. Router (UPnP)")
    locations = discover_locations()
    if locations:
        print("  ueber die normale UPnP-Suche gefunden")
    else:
        print("  UPnP-Suche (Multicast) blieb stumm - klopfe direkt an ...")
        locations = fallback_locations()
        if locations:
            print("  direkt erreicht (die Suche selbst wird also geblockt,")
            print("  vermutlich von der Windows-Firewall)")
    if not locations:
        print("  NICHT GEFUNDEN.")
        print("  Der Router antwortet nicht auf UPnP. Entweder ist UPnP dort")
        print("  ganz abgeschaltet, oder eine Firewall blockt die Suche.")
        print("  Eine Freigabe von Hand geht trotzdem - weiter bei Schritt 2.")
        router_ip = ""
        service = None
    else:
        print("  gefunden: %s" % locations[0])
        router_ip = urllib.parse.urlparse(locations[0]).hostname or ""
        service = None
        for loc in locations:
            try:
                with urllib.request.urlopen(loc, timeout=4.0) as resp:
                    xml = resp.read().decode("utf-8", "replace")
            except OSError:
                continue
            svc = parse_services(xml, loc)
            if svc:
                service = svc[0]
                break
        print("  Dienst:   %s" % (service[0] if service else "keiner gefunden"))
        me = _local_ip_towards(router_ip) if router_ip else ""
        if me:
            print("  Dieser PC im Heimnetz: %s" % me)
            print("  -> genau dieses Geraet braucht die Freigabe")

    # -- 2. Echte oeffentliche IP? ---------------------------------------
    head("2. Hat der Anschluss eine echte oeffentliche IPv4?")
    mapper = PortMapper(port)
    router_wan = ""
    if service:
        router_wan = mapper._ask_external_ip(service[0], service[1])
    pub = PublicIP()
    pub.start()
    for _ in range(60):
        if pub.done:
            break
        time.sleep(0.25)

    print("  Router meldet aussen:  %s" % (router_wan or "unbekannt"))
    print("  Von aussen gesehen:    %s" % (pub.ip or "unbekannt"))

    verdict_ok = None
    if router_wan and pub.ip:
        if router_wan == pub.ip:
            verdict_ok = True
            print("  -> GLEICH. Echte oeffentliche IP, eine Portfreigabe wirkt.")
        else:
            verdict_ok = False
            print("  -> VERSCHIEDEN. Der Anschluss haengt hinter DS-Lite/CGNAT.")
            print("     Eine Portfreigabe im Router bringt hier NICHTS, weil die")
            print("     Adresse gar nicht dir allein gehoert. Loesung: ein VPN")
            print("     wie Tailscale, Radmin oder Hamachi - darin verhalten sich")
            print("     alle PCs wie im selben LAN und die LAN-Anleitung gilt.")
    else:
        print("  -> nicht sicher feststellbar (Router oder Internet nicht erreichbar)")

    # -- 3. Selbsttaetige Freigabe ---------------------------------------
    head("3. Laesst der Router eine selbsttaetige Freigabe zu?")
    if not service:
        print("  uebersprungen - kein UPnP-Dienst gefunden.")
    else:
        ok = False
        try:
            ok = mapper.open_port()
            auto_ok = ok
        except Exception as exc:                      # sehr defensiv
            mapper.message = str(exc)
        if ok:
            print("  JA - Port %d wurde eben geoeffnet." % port)
            print("  Beim Hosten macht das Spiel das von allein.")
            mapper.close()
            print("  (Testfreigabe wieder entfernt)")
        else:
            print("  NEIN.")
            print("  Grund: %s" % (mapper.message or "unbekannt"))

    # -- Fazit -----------------------------------------------------------
    head("Fazit")
    if verdict_ok is False:
        print("  Portfreigabe bringt an diesem Anschluss nichts (DS-Lite/CGNAT).")
        print("  Nimm ein VPN - siehe README, Abschnitt 'Uebers Internet spielen'.")
    elif verdict_ok:
        print("  Freunde von aussen verbinden sich mit:  %s:%d" % (pub.ip, port))
        if auto_ok:
            print("  Alles bereit - das Spiel oeffnet den Port beim Hosten selbst.")
        else:
            print("  Es fehlt noch die Freigabe. Im Router eintragen:")
            print("    TCP, Port %d aussen -> Port %d auf diesem PC" % (port, port))
            if router_ip:
                print("    Router-Oberflaeche: http://%s" % router_ip)
        print()
        print("  ACHTUNG: Diese oeffentliche Adresse wechselt bei vielen")
        print("  Anschluessen taeglich. Sie steht immer aktuell in der Lobby -")
        print("  von dort ablesen und weitergeben, nicht aufschreiben.")
    else:
        print("  Konnte nicht abschliessend geprueft werden.")
    print()


if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GAME_PORT
    main(p)
