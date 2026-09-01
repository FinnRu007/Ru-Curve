# Ru-Curve

Ein Partyspiel-Turnier fuer viele Leute an einem PC oder ueber LAN: **elf kurze
Minispiele** laufen hintereinander ab, nach jedem gibt es Punkte nach Platzierung,
und eine Rangliste zeigt jederzeit, wer vorn liegt. Eines der Minispiele ist
**Achtung die Kurve** - das Spiel, aus dem das Projekt entstanden ist; es laesst
sich auch weiterhin allein als klassisches Match spielen.

Der Trick, mit dem alles zusammenpasst: **jeder Spieler hat genau drei Tasten**
(links, Aktion, rechts). Damit koennen beliebig viele Leute an einer einzigen
Tastatur mitspielen, und dieselbe Steuerung funktioniert unveraendert uebers Netz.

## Starten

```bash
pip install -r requirements.txt
python tools/make_assets.py     # einmalig: Soundeffekte + Icon erzeugen
python main.py
```

Das Fenster ist frei skalierbar und startet passend zur Bildschirmgröße. Das
Spielfeld füllt das Fenster und passt sein Seitenverhältnis an – auf einem
größeren Bildschirm wird alles größer dargestellt. In den Einstellungen legt
`Spielfeld → Größe` fest, wie viel Fläche das Feld in Spiel-Einheiten hat
(kleiner = stärker gezoomt / alles größer). Hintergrundmusik ist aktuell
deaktiviert – nur Soundeffekte.

Windows-Paket bauen: `build_exe.bat` doppelklicken → Ordner `dist/Ru-Curve/`
(darin `Ru-Curve.exe` starten) **und** `dist/Ru-Curve.zip` zum Weitergeben.
Der Build läuft im **Ordner-Modus** (`--onedir --noupx` + Versionsinfo) – das
löst bei Windows Defender deutlich seltener Fehlalarme aus als eine einzelne
`--onefile`-EXE. Schlägt Defender trotzdem an: es ist ein bekannter
PyInstaller-Fehlalarm, der komplette Quellcode liegt hier offen.
(Optionaler GitHub-Actions-Build: siehe „CI" unten.)

## Spielen

Im Hauptmenue **An einem PC spielen**, **Uber LAN hosten** oder **Uber LAN
beitreten** waehlen. In der Lobby stellst du Spieler, Bots, Namen und Farben ein.
Dann gibt es zwei Knoepfe:

* **TURNIER** - der Partymodus mit allen Minispielen (siehe unten)
* **Kurve starten** - nur Achtung die Kurve, wie bisher

Ueber LAN werden Hosts im Netzwerk automatisch gefunden; sonst die IP eintippen
(auch `IP:Port` fuer Portweiterleitung). Der Host bestimmt alle Einstellungen.

## LAN einrichten (wenn es nicht klappt)

**Auf dem Host-PC:** Hauptmenü → *Über LAN hosten*. Oben rechts in der Lobby
steht groß die Adresse, z. B. `192.168.178.47:51738` — genau die geben die
anderen ein. Der Host muss in der Lobby bleiben, bis alle drin sind.

**Auf den anderen PCs:** Hauptmenü → *Über LAN beitreten*. Gefundene Hosts
erscheinen automatisch in der Liste; sonst die Adresse eintippen (`IP` oder
`IP:Port`).

Häufige Stolpersteine und was die Meldung bedeutet:

| Meldung | Ursache | Lösung |
|---|---|---|
| **Verbindung abgelehnt** | Auf dem Ziel-PC läuft kein Host | Dort *Über LAN hosten* wählen und in der Lobby bleiben |
| **Keine Antwort** (Zeitüberschreitung) | Windows-Firewall blockt | Auf dem Host-PC `tools/firewall_freigeben.bat` als **Administrator** ausführen |
| **Adresse nicht gefunden** | IP vertippt | Adresse aus der Host-Lobby abschreiben |
| **Netzwerk nicht erreichbar** | verschiedene Netze | Beide ins selbe WLAN / an denselben Router |
| **Kein Host in der Liste** | UDP-Suche blockiert | Firewall freigeben — oder die IP von Hand eintippen, das geht immer |
| **Alle Ports belegt** | alte Ru-Curve-Instanz läuft noch | Im Task-Manager beenden |

Wichtig: Windows fragt beim ersten Hosten, ob das Programm ins Netzwerk darf —
dort **Zulassen** klicken (und den Haken bei *Privates Netzwerk* setzen). Wurde
das einmal abgelehnt, hilft `tools/firewall_freigeben.bat`.

Ist der Standard-Port belegt, weicht der Host automatisch auf den nächsten
freien aus (51738 … 51745) und zeigt ihn an — deshalb immer die Adresse aus der
Lobby verwenden statt sie zu raten.

## Das Turnier

Der Host legt fest, wie viele Minispiele gespielt werden (Standard 8) und welche
ueberhaupt vorkommen. Vor jedem Spiel gibt es eine kurze Erklaerung und einen
Countdown, danach wird gespielt, ausgewertet und Punkte verteilt:
**Platz 1 bekommt 10 Punkte**, der letzte Platz 1 - dazwischen linear. Bei
Gleichstand entscheidet, wer schneller war. Rechts laeuft immer die Gesamtrangliste
mit.

| # | Minispiel | Worum es geht |
|---|---|---|
| 1 | **Reaktion** | Eine deiner drei Tasten leuchtet auf - druecke sie so schnell wie moeglich. Zu frueh gedrueckt zaehlt als Fehler. |
| 2 | **Merken** | Eine Tastenfolge wird vorgespielt, du druckst sie nach. Jede Stufe wird laenger. |
| 3 | **Kopfrechnen** | 10 Aufgaben, je 5 Sekunden, drei Antworten auf deinen drei Tasten. |
| 4 | **Flaecheninhalt** | Rechteck, Dreieck, Kreis - Flaeche bestimmen, gleiche Regeln wie beim Kopfrechnen. |
| 5 | **Schaetzen** | Wie viele Punkte sind auf dem Feld? Vier Sekunden pro Bild. |
| 6 | **Ausreisser finden** | Ein Feld im Raster hat eine andere Farbe - in welchem Drittel liegt es? |
| 7 | **Haemmern** | Acht Sekunden lang so schnell wie moeglich auf die Tasten hauen. |
| 8 | **Stopp!** | Einen hin- und herlaufenden Zeiger moeglichst genau in der Mitte anhalten. |
| 9 | **Zeitgefuehl** | Druecken, wenn genau die geforderte Zeit vorbei ist - die Uhr verschwindet unterwegs. |
| 10 | **Zielen** | Maus-Spiel: Ziele anklicken. Sitzen mehrere an einem PC, ist jeder einzeln dran. |
| 11 | **Achtung die Kurve** | Eine kurze Runde des Originalspiels - wer am laengsten ueberlebt, gewinnt. |

Wie das ueber LAN zusammenlaeuft: der Host wuerfelt die Aufgaben aus und schickt
sie an alle, jede Maschine spielt ihre eigenen Leute und meldet das Ergebnis
zurueck, der Host vergibt die Punkte. Bei Achtung die Kurve rechnet der Host die
komplette Runde und schickt Schnappschuesse - dort ist er die einzige Wahrheit.

## Steuerung

Menü **Steuerung**: bis zu sechs lokale Spieler-Slots, jeweils frei belegbare
Tasten für *Links / Rechts / Aktion*, Name, Farbe und Powerup-Auswahl. Diese drei
Tasten steuern alles: bei Achtung die Kurve lenken sie und lösen das Powerup aus,
in den Minispielen sind sie die drei Antwortmöglichkeiten.
Doppelbelegungen werden rot markiert. (Hardware-Tastaturen erkennen oft nur
~6 Tasten gleichzeitig – für viele Spieler an einem PC ggf. mehrere Rechner per
LAN koppeln.)

## Einstellungen

Menü **Einstellungen** – in sechs aufklappbare Bereiche sortiert (Bereich
anklicken zum Auf-/Zuklappen), jeder Wert als Schieberegler **und** Zahlenfeld:

* **System** – Spielfeld-Größe, Fenstergröße, Vollbild
* **Sound** – Lautstärke der Soundeffekte
* **Spiel** – Geschwindigkeit, Lenkradius, Linienbreite, Lücken-Abstand und
  -Größe, Punkte pro Gegner, Zielpunktzahl, Countdown, Zeitlimit,
  Selbstkollision
* **Turnier** – Anzahl der Minispiele, Punkte für Platz 1, Reihenfolge mischen
  und ein An/Aus-Schalter für jedes einzelne Minispiel
* **Bots** – Anzahl beim Start, Stärke (0 = harmlos, 1.0 = sehr stark)
* **Powerups** – jedes Powerup einzeln: An/Aus, Wirkdauer, Stärke, Ladungen pro
  Runde und Abklingzeit; dazu „Alle an" / „Alle aus"

Gespeichert wird alles in `%APPDATA%/Ru-Curve/config.json`.

## Powerups (bei Achtung die Kurve)

Jeder Spieler wählt in der Lobby sein Powerup, die dritte Taste löst es aus.
Ganz oben in der Liste steht **Zufällig** – dann wird zu Beginn *jeder* Runde
neu ausgewürfelt (nur aus den aktivierten). Bots spielen standardmäßig auf
„Zufällig". Welches Powerup man tatsächlich bekommen hat, steht im HUD neben
den Punkten; beim Auslösen wird der Name kurz eingeblendet.

Die Leiste oben zeigt für **jeden** Spieler Name, Punkte, das aktuelle Powerup,
die verbleibenden Ladungen (Punkte bzw. „×N", sonst „leer"), die Abklingzeit und
ein rotes **RAUS**, sobald jemand ausgeschieden ist. Passen nicht alle Karten
nebeneinander, bricht die Leiste in mehrere Zeilen um – es wird nie etwas
weggelassen.

| Powerup | Wirkung |
|---|---|
| Speed-Schub | kurz deutlich schneller |
| Wendig | lenkt kurzzeitig viel enger |
| Dünne Linie | eigene Linie wird schmaler |
| Geist | fliegt kurz durch alle Linien, zieht keine Spur |
| Schutzschild | fängt einen Crash ab, danach kurz unverwundbar |
| Sprung | springt sofort ein Stück nach vorne |
| Extra-Lücke | reißt sofort eine große Lücke in die eigene Spur |
| Eckig | nur noch 90°-Ecken, jeder Tastendruck knickt ab |
| Gegner bremsen | alle anderen werden langsamer |
| Gegner-Linien dick | die Linien aller anderen werden breiter |
| Gegner verdrehen | vertauscht bei allen anderen links und rechts |
| Farben umkehren | invertiert für alle den ganzen Bildschirm |
| Nebel | verdunkelt das Feld, man sieht nur um sich herum |
| Radiergummi | löscht alle bisherigen Linien auf dem Feld |

## Nach der Runde

Wenn eine Runde vorbei ist, bleibt das Spielfeld stehen – man sieht, wo alle
hergefahren sind. Erst ein **Klick** (oder Leertaste) führt zum Zwischenstand.
Der ist scrollbar (Mausrad / Pfeiltasten) und zeigt ab zehn Spielern zwei
Spalten, damit auch große Runden komplett lesbar bleiben.

## Tests

```bash
python tests/test_core.py        # Simulation, Kollision, Spawns, Punkte, Powerup, Protokoll
python tests/test_net.py         # Host <-> Client über Loopback
python tests/test_smoke_app.py   # ganzer Menü->Lobby->Spiel->Scoreboard-Durchlauf, headless
python tests/test_party.py       # ein komplettes Turnier durch alle 11 Minispiele
python tests/test_party_net.py   # Turnier ueber echte Sockets (Host + Client)
python tests/test_lan_robust.py  # belegte Ports, Fehlermeldungen, Hostsuche
python tests/test_party_join.py  # Lobby -> TURNIER: Mitspieler kommt wirklich mit
python tests/shots.py            # rendert alle Szenen als PNG nach tests/_shots/
python tests/shots_party.py      # rendert jedes Minispiel nach tests/_shots_party/
```

## Projektstruktur

```
main.py                Startpunkt
rucurve/
  app.py               Fenster + Hauptschleife + Szenenverwaltung
  config.py            GameSettings + Tastenbelegung + JSON
  session.py           Match-/Rundenmodell
  theme.py  colors.py
  audio.py             nur Soundeffekte (Musik deaktiviert)
  game/                world.py (Simulation), curve.py, collision.py, powerups.py, bots.py
  net/                 protocol.py, host.py, client.py, discovery.py
  party/               Turnier-Modus
    base.py            MiniGame-Basis, Spieler, Ergebnisse, Netz-Haken
    tournament.py      Reihenfolge, Punktevergabe, Rangliste
    quiz.py            gemeinsame Basis der Multiple-Choice-Spiele
    ui.py              dunkle Party-Optik (Tastenkappen, Rangliste, Banner)
    registry.py        Liste aller Minispiele
    games/             reflex.py, quizzes.py, aim.py, curve_game.py
  scenes/              menu, lobby, settings_scene, controls, game, scoreboard,
                       join (+ Client-Lobby), client_game, arena_render,
                       tournament (Turnier-Ablauf)
  ui/widgets.py        handgemachte Widgets (Button, Slider, Zahlenfeld, ...)
tools/make_assets.py   erzeugt Soundeffekte + Icon prozedural
tools/firewall_freigeben.bat   gibt Ru-Curve in der Windows-Firewall frei
```

## CI (optional)

Der GitHub-Actions-Workflow liegt als `ci/build.yml.txt` bei (baut Tests + .exe).
Zum Aktivieren:

```bash
gh auth refresh -s workflow
mkdir -p .github/workflows && git mv ci/build.yml.txt .github/workflows/build.yml
git commit -m "CI aktivieren" && git push
```
