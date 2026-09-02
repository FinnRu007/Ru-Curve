"""Automatische Portfreigabe im Router (UPnP / IGD) - fuer Spielen uebers Internet.

Damit Freunde ausserhalb des eigenen WLANs beitreten koennen, muss der Router
den Spiel-Port nach innen durchreichen. Fast alle Heimrouter (FritzBox, Speedport,
Vodafone Station ...) koennen das per UPnP von selbst - man muss es nur fragen.

Ablauf:
  1. Per SSDP (UDP-Multicast) nach dem Internet-Gateway suchen.
  2. Dessen Beschreibungs-XML holen und die Steuer-Adresse des
     WANIPConnection- bzw. WANPPPConnection-Dienstes heraussuchen.
  3. Dort per SOAP AddPortMapping aufrufen (und beim Beenden wieder loeschen).

Alles ohne Fremdbibliotheken und komplett fehlertolerant: klappt es nicht,
laeuft das Spiel im LAN einfach weiter.
"""

from __future__ import annotations

import re
import socket
import threading
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
SEARCH_TARGETS = (
    "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
    "urn:schemas-upnp-org:service:WANIPConnection:1",
    "urn:schemas-upnp-org:service:WANPPPConnection:1",
    "upnp:rootdevice",
)
WAN_SERVICES = (
    "urn:schemas-upnp-org:service:WANIPConnection:1",
    "urn:schemas-upnp-org:service:WANIPConnection:2",
    "urn:schemas-upnp-org:service:WANPPPConnection:1",
)

_NS = {"d": "urn:schemas-upnp-org:device-1-0"}


# --------------------------------------------------------------------------- #
def discover_locations(timeout: float = 2.5) -> list:
    """Adressen der Beschreibungs-XMLs aller gefundenen Router."""
    found = []
    for target in SEARCH_TARGETS:
        msg = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: %s:%d\r\n"
            'MAN: "ssdp:discover"\r\n'
            "MX: 2\r\n"
            "ST: %s\r\n\r\n" % (SSDP_ADDR, SSDP_PORT, target)
        ).encode("ascii")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        try:
            sock.sendto(msg, (SSDP_ADDR, SSDP_PORT))
            while True:
                try:
                    data, _addr = sock.recvfrom(4096)
                except socket.timeout:
                    break
                loc = parse_location(data.decode("utf-8", "replace"))
                if loc and loc not in found:
                    found.append(loc)
        except OSError:
            pass
        finally:
            sock.close()
        if found:
            break
    return found


def parse_location(response: str) -> str | None:
    """LOCATION-Zeile aus einer SSDP-Antwort ziehen."""
    for line in response.splitlines():
        if line.lower().startswith("location:"):
            return line.split(":", 1)[1].strip()
    return None


def parse_services(xml_text: str, base_url: str) -> list:
    """(serviceType, absolute controlURL) fuer alle WAN-Dienste im XML."""
    out = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return out
    # Namensraum kann fehlen oder abweichen - beide Wege versuchen
    for svc in root.iter():
        tag = svc.tag.rsplit("}", 1)[-1]
        if tag != "service":
            continue
        stype = ctrl = None
        for child in svc:
            ctag = child.tag.rsplit("}", 1)[-1]
            if ctag == "serviceType":
                stype = (child.text or "").strip()
            elif ctag == "controlURL":
                ctrl = (child.text or "").strip()
        if stype in WAN_SERVICES and ctrl:
            out.append((stype, urllib.parse.urljoin(base_url, ctrl)))
    return out


def _soap(control_url: str, service_type: str, action: str, body: str,
          timeout: float = 4.0) -> str:
    envelope = (
        '<?xml version="1.0"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
        's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
        "<s:Body><u:%s xmlns:u=\"%s\">%s</u:%s></s:Body></s:Envelope>"
        % (action, service_type, body, action)
    ).encode("utf-8")
    req = urllib.request.Request(
        control_url, data=envelope,
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPAction": '"%s#%s"' % (service_type, action),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        # Router melden den Grund als SOAP-Fault im Rumpf der 500er-Antwort
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        raise UpnpError(soap_fault(detail) or ("HTTP %s" % exc.code)) from None


class UpnpError(Exception):
    """Der Router hat die Anfrage abgelehnt - mit lesbarer Begruendung."""


def soap_fault(xml_text: str) -> str:
    """Fehlercode + Beschreibung aus einer SOAP-Fault-Antwort ziehen."""
    code = re.search(r"<errorCode>\s*(\d+)\s*</errorCode>", xml_text or "")
    desc = re.search(r"<errorDescription>([^<]*)</errorDescription>", xml_text or "")
    if not code:
        return ""
    return "%s %s" % (code.group(1), (desc.group(1) if desc else "").strip())


def _local_ip_towards(host: str) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, 80))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


# --------------------------------------------------------------------------- #
class PortMapper:
    """Oeffnet einen Port im Router und raeumt ihn beim Beenden wieder auf."""

    def __init__(self, port: int, description: str = "Ru-Curve") -> None:
        self.port = port
        self.description = description
        self.status = "idle"        # idle | suchen | ok | fehlgeschlagen
        self.message = ""
        self.external_ip = ""
        self._service = None        # (serviceType, controlURL)
        self._mapped = False
        self._thread: threading.Thread | None = None

    # -- im Hintergrund, damit das Menue nicht haengt -------------------
    def start(self) -> None:
        self.status = "suchen"
        self._thread = threading.Thread(target=self._run, name="upnp", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            ok = self.open_port()
        except Exception as exc:                       # sehr defensiv
            self.status = "fehlgeschlagen"
            self.message = str(exc)
            return
        if ok:
            self.status = "ok"
            self.message = "Router hat Port %d geoeffnet" % self.port
        else:
            self.status = "fehlgeschlagen"
            self.message = self.message or "Router antwortet nicht auf UPnP"

    # -- die eigentliche Arbeit ----------------------------------------
    def open_port(self) -> bool:
        for location in discover_locations():
            try:
                with urllib.request.urlopen(location, timeout=4.0) as resp:
                    xml_text = resp.read().decode("utf-8", "replace")
            except (urllib.error.URLError, OSError, ValueError):
                continue
            for stype, ctrl in parse_services(xml_text, location):
                host = urllib.parse.urlparse(ctrl).hostname or ""
                me = _local_ip_towards(host) if host else ""
                if not me:
                    continue
                body = (
                    "<NewRemoteHost></NewRemoteHost>"
                    "<NewExternalPort>%d</NewExternalPort>"
                    "<NewProtocol>TCP</NewProtocol>"
                    "<NewInternalPort>%d</NewInternalPort>"
                    "<NewInternalClient>%s</NewInternalClient>"
                    "<NewEnabled>1</NewEnabled>"
                    "<NewPortMappingDescription>%s</NewPortMappingDescription>"
                    "<NewLeaseDuration>0</NewLeaseDuration>"
                    % (self.port, self.port, me, self.description)
                )
                try:
                    _soap(ctrl, stype, "AddPortMapping", body)
                except Exception as exc:
                    self.message = _short_soap_error(exc)
                    self.external_ip = self._ask_external_ip(stype, ctrl)
                    continue
                self._service = (stype, ctrl)
                self._mapped = True
                self.external_ip = self._ask_external_ip(stype, ctrl)
                return True
        return False

    def _ask_external_ip(self, stype, ctrl) -> str:
        try:
            answer = _soap(ctrl, stype, "GetExternalIPAddress", "")
        except Exception:
            return ""
        m = re.search(r"<NewExternalIPAddress>([^<]*)</NewExternalIPAddress>", answer)
        return m.group(1).strip() if m else ""

    def close(self) -> None:
        if not self._mapped or not self._service:
            return
        stype, ctrl = self._service
        body = (
            "<NewRemoteHost></NewRemoteHost>"
            "<NewExternalPort>%d</NewExternalPort>"
            "<NewProtocol>TCP</NewProtocol>" % self.port
        )
        try:
            _soap(ctrl, stype, "DeletePortMapping", body, timeout=2.5)
        except Exception:
            pass
        self._mapped = False


def _short_soap_error(exc) -> str:
    """Router-Fehler in einen Satz uebersetzen, der weiterhilft."""
    text = str(exc)
    if text.startswith("403") or "not available action" in text.lower()             or "Forbidden" in text:
        return ("Router erlaubt keine selbsttaetigen Portfreigaben. "
                "FritzBox: Internet > Freigaben > Portfreigaben > Haken bei "
                "'Selbststaendige Portfreigaben fuer dieses Geraet erlauben'.")
    if text.startswith("718") or "718" in text:
        return "Port ist im Router schon fuer ein anderes Geraet vergeben."
    if text.startswith("725") or "OnlyPermanentLeases" in text:
        return "Router erlaubt nur dauerhafte Freigaben - bitte von Hand anlegen."
    if text.startswith("402"):
        return "Router hat die Anfrage nicht verstanden (402)."
    if "401" in text or "Unauthorized" in text:
        return "Router verlangt eine Anmeldung fuer UPnP."
    if "timed out" in text.lower():
        return "Router antwortet nicht rechtzeitig."
    return text[:110]
