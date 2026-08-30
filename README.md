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

Das Fenster ist frei skalierbar und startet passend zur Bildschirmgröße
(gespeicherte Größe wird auf den Bildschirm begrenzt). Hintergrundmusik ist
aktuell deaktiviert – nur Soundeffekte.

Windows-.exe bauen: `build_exe.bat` doppelklicken → `dist/Ru-Curve.exe`.
(GitHub Actions baut die .exe bei jedem Push nach `main` als Artifact.)

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

Menü **Einstellungen** – alles frei justierbar, um das Gameplay zu tunen:
Geschwindigkeit, Lenkradius, Linienbreite, Lücken-Abstand und -Größe,
Powerup-Dauer / -Stärke / -Ladungen / -Abklingzeit, Punkte pro Gegner,
Zielpunktzahl, Countdown, Zeitlimit, Selbstkollision, Arena-Größe, Anzahl und
Stärke der Bots, Lautstärken, Fenstergröße / Vollbild. Wird als
`%APPDATA%/Ru-Curve/config.json` gespeichert.

## Powerups

Am Anfang wählt jeder Spieler sein Powerup (dritte Taste aktiviert es):

| Powerup          | Wirkung                                        | Status |
|------------------|------------------------------------------------|--------|
| Speed-Schub      | kurz deutlich schneller                        | fertig |
| Dünne Linie      | eigene Linie kurz halb so breit                | fertig |
| Geist            | kurz durch alle Linien (zieht keine Spur)      | fertig |
| Gegner bremsen   | alle anderen kurz langsamer                    | fertig |
| Eckig            | 90°-Kurven                                     | geplant |
| Extra-Lücke      | erzwingt sofort eine große Lücke               | geplant |

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
  theme.py  colors.py  audio.py
  audio.py             nur Soundeffekte (Musik deaktiviert)
  game/                world.py (Simulation), curve.py, collision.py, powerups.py, bots.py
  net/                 protocol.py, host.py, client.py, discovery.py
  scenes/              menu, lobby, settings_scene, controls, game, scoreboard,
                       join (+ Client-Lobby), client_game, arena_render
  ui/widgets.py        handgemachte Widgets (Button, Slider, Zahlenfeld, ...)
tools/make_assets.py   erzeugt Sounds/Musik/Icon prozedural
```
