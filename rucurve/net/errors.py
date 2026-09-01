"""Netzwerkfehler in verstaendliche Saetze uebersetzen.

Windows meldet Dinge wie "[WinError 10061] Es konnte keine Verbindung
hergestellt werden" - das hilft niemandem weiter. Hier steht stattdessen, was
zu tun ist.
"""

from __future__ import annotations


def friendly(error, ip: str = "", port: int = 0) -> tuple[str, str]:
    """(Kurzmeldung, Tipp) fuer einen Verbindungsfehler."""
    text = str(error or "").lower()
    ziel = "%s:%d" % (ip, port) if ip else "dem Host"

    if "10013" in text or "permission denied" in text or "zugriff verweigert" in text:
        return ("Zugriff verweigert",
                "Eine Firewall oder ein Virenscanner blockt Ru-Curve. Dort "
                "freigeben oder tools/firewall_freigeben.bat als Administrator "
                "ausfuehren.")
    if "10061" in text or "refused" in text or "abgelehnt" in text:
        return ("Verbindung abgelehnt von " + ziel,
                "Auf dem anderen PC laeuft kein Spiel. Dort im Hauptmenue "
                "'Uber LAN hosten' waehlen und in der Lobby bleiben.")
    if "timed out" in text or "10060" in text or "timeout" in text:
        return ("Keine Antwort von " + ziel,
                "Meist blockiert die Windows-Firewall. Auf dem Host-PC "
                "tools/firewall_freigeben.bat als Administrator ausfuehren - "
                "oder pruefen, ob beide im selben WLAN sind.")
    if "11001" in text or "getaddrinfo" in text or "not known" in text:
        return ("Adresse nicht gefunden: " + (ip or "?"),
                "IP-Adresse pruefen. Sie steht beim Host in der Lobby oben.")
    if "10065" in text or "unreachable" in text or "erreichbar" in text:
        return ("Netzwerk nicht erreichbar",
                "Beide Rechner muessen im selben Netz sein (gleiches WLAN "
                "oder gleicher Router).")
    return ("Verbindung fehlgeschlagen", str(error or "unbekannter Fehler"))


def host_problem(error) -> tuple[str, str]:
    """(Kurzmeldung, Tipp), wenn der Host nicht starten konnte."""
    text = str(error or "").lower()
    if "10048" in text or "in use" in text or "belegt" in text or "kein freier port" in text:
        return ("Alle Ports belegt",
                "Es laeuft vermutlich noch eine alte Ru-Curve-Instanz. "
                "Im Task-Manager beenden und neu starten.")
    if "10013" in text or "permission" in text or "zugriff" in text:
        return ("Firewall blockt den Host",
                "tools/firewall_freigeben.bat als Administrator ausfuehren.")
    return ("Host konnte nicht starten", str(error or "unbekannter Fehler"))
