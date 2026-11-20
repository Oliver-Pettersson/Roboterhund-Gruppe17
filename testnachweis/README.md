# Testnachweis Informatik (Bericht Kapitel 7)

Drei Tests mit Laptop-Kamera und -Mikrofon. Sie nutzen den Code aus
`workspace/src/pren_perception` mit den Parametern aus `pren_bringup/config/perception.yaml`,
also denselben Stand wie die ROS-Nodes in der Simulation.

| Test | Start (Doppelklick) | Dauer |
| --- | --- | --- |
| T1 Sprache | `scripts\test_sprache.bat` | ca. 10 min |
| T2 Gesten | `scripts\test_gesten.bat` | ca. 10 min |
| T3a Kamera | `scripts\test_kamera.bat` | ca. 10 min |

Vorher die Simulation beenden (das Skript baut zuerst den Workspace). Schlaegt der Build
fehl, fragt das Skript, ob es mit dem bestehenden Build weitermachen soll. Ohne Build
starten: im cmd zuerst `set PREN_KEIN_BUILD=1`, dann das Skript aufrufen.

Vor dem ersten Test pruefen, ob Mikrofon und Kamera laufen (ca. 30 s, ohne Bedienung):
`pixi run cmd /c "cd workspace && call .\install\local_setup.bat && cd ..\testnachweis && python selbsttest.py"`

- **T1:** Zuerst ein Pegeltest ("Hallo" im Testabstand, Pegel muss ueber der Schwelle liegen).
  Dann Block ruhig, dann Block mit Laerm (Video mit Stimmengewirr neben dem Laptop).
  Pro Block HIER, BRAV, SITZ, SUCH je 5-mal und 5 aehnliche Woerter. Im Terminal: Enter, Wort sagen.
- **T2:** Bloecke 0,5 m, 1 m und 2 m. SITZ (offene Hand), PLATZ (Zeigefinger nach unten),
  AUF (Zeigefinger nach oben) je 5-mal plus 3 neutrale Bewegungen. Bedienung im Kamerafenster
  mit der Leertaste.
- **T3a:** Drei Messungen: 3 m quer, 5 m quer und 5 m laengs (Spitze zur Kamera, schwierigster
  Fall, weil der Knochen von vorne verkuerzt erscheint). Knochen hinlegen, im Kamerafenster
  S druecken, beide sichtbaren Enden anklicken. CSV, Zusammenfassung und Fotoname enthalten
  die Ausrichtung.

Ergebnisse: `testnachweis/ergebnisse/` mit CSV pro Versuch, Zusammenfassung als `.md` und
Fotos (T3a). Keine Ton- oder Videoaufnahmen.

Optionen:

- Nachtest einzelner Sprachbefehle: `scripts\test_sprache.bat --befehle BRAV` (mehrere:
  `--befehle BRAV,SUCH`). Pro Block 5-mal jeder Befehl und 2 aehnliche Woerter (fuer BRAV:
  "brauchen" und "bravo"), Anzahl mit `--nicht-befehle N`. Die Dateien heissen dann
  `t1_sprache_nachtest_BRAV_...`. Die Spalte `gesagt` zeigt das gesprochene Wort.
- Nachtest einzelner Gesten: `scripts\test_gesten.bat --kamera 1 --gesten SITZ,NEUTRAL`.
  Pro Distanz jede gewaehlte Geste 5-mal (`--wiederholungen`), nur einzelne Distanzen mit
  z. B. `--distanzen 1,2`. Die Dateien heissen dann `t2_gesten_nachtest_SITZ_NEUTRAL_...`.
  In der Zusammenfassung steht die verwendete Glaettung (SITZ seit 20.11. strenger: 7 von 8 Bildern).
- Externe Webcam statt Laptop-Kamera: `scripts\test_gesten.bat --kamera 1` bzw.
  `scripts\test_kamera.bat --kamera 1` (0 = Laptop-Kamera). perception.yaml bleibt dabei unveraendert.
- Anderes Mikrofon, per Index oder Teil des Namens: `scripts\test_sprache.bat --device C922`
  (Liste der Mikrofone: `pixi run python -m sounddevice`).

Die Kameras werden zuerst mit DirectShow geoeffnet. Mit dem Windows-Standard (MSMF) braucht
z. B. eine Logitech C922 fast eine Minute zum Oeffnen.
