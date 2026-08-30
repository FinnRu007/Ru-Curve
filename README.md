# Ru-Curve

Ein Kurvenspiel im Stil von **Achtung die Kurve** / *Curve Fever* -
zusammen an **einem PC** (geteilte Tastatur) oder über **LAN**.

Man ist ein Punkt, der eine Linie hinter sich herzieht und ab und zu kurz eine
Lücke lässt. Gelenkt wird mit zwei benachbarten Tasten (links / rechts), eine
dritte Taste löst das gewählte **Powerup** aus. Raus ist, wer den Rand oder eine
Linie berührt. Nach jeder Runde gibt es platzabhängige Punkte; wer die
Zielpunktzahl erreicht, gewinnt das Match.

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

* **An einem PC** – Lobby öffnen, Spieler (`+ Spieler`) und/oder Bots (`+ Bot`)
  hinzufügen, `Start`.
* **Über LAN hosten** – öffnet einen Host; die eigene IP steht in der Lobby.
* **Über LAN beitreten** – gefundene Hosts werden automatisch gelistet, sonst
  IP-Adresse eintippen. Der Host bestimmt alle Einstellungen.

Der Host rechnet die Simulation, die Clients senden nur ihre Tasteneingaben und
zeigen den vom Host geschickten Spielstand an.

## Steuerung

Menü **Steuerung**: bis zu sechs lokale Spieler-Slots, jeweils frei belegbare
Tasten für *Links / Rechts / Powerup*, Name, Farbe und Powerup-Auswahl.
Doppelbelegungen werden rot markiert. (Hardware-Tastaturen erkennen oft nur
~6 Tasten gleichzeitig – für viele Spieler an einem PC ggf. mehrere Rechner per
LAN koppeln.)

## Einstellungen

Menü **Einstellungen** – in fünf aufklappbare Bereiche sortiert (Bereich
anklicken zum Auf-/Zuklappen), jeder Wert als Schieberegler **und** Zahlenfeld:

* **System** – Spielfeld-Größe, Fenstergröße, Vollbild
* **Sound** – Lautstärke der Soundeffekte
* **Spiel** – Geschwindigkeit, Lenkradius, Linienbreite, Lücken-Abstand und
  -Größe, Punkte pro Gegner, Zielpunktzahl, Countdown, Zeitlimit,
  Selbstkollision
* **Bots** – Anzahl beim Start, Stärke (0 = harmlos, 1.0 = sehr stark)
* **Powerups** – jedes Powerup einzeln: An/Aus, Wirkdauer, Stärke, Ladungen pro
  Runde und Abklingzeit; dazu „Alle an" / „Alle aus"

Gespeichert wird alles in `%APPDATA%/Ru-Curve/config.json`.

## Powerups

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
python tests/shots.py            # rendert alle Szenen als PNG nach tests/_shots/
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
  scenes/              menu, lobby, settings_scene, controls, game, scoreboard,
                       join (+ Client-Lobby), client_game, arena_render
  ui/widgets.py        handgemachte Widgets (Button, Slider, Zahlenfeld, ...)
tools/make_assets.py   erzeugt Soundeffekte + Icon prozedural
```

## CI (optional)

Der GitHub-Actions-Workflow liegt als `ci/build.yml.txt` bei (baut Tests + .exe).
Zum Aktivieren:

```bash
gh auth refresh -s workflow
mkdir -p .github/workflows && git mv ci/build.yml.txt .github/workflows/build.yml
git commit -m "CI aktivieren" && git push
```
