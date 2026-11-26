# Roboterhund – PREN Gruppe 17

Gemeinsames Repository für die PREN-Prototypen, die Webots-Simulation und den zukünftigen ROS-2-Workspace des Roboterhunds.

## Voraussetzungen

- Windows 11
- [Pixi](https://pixi.sh/) 0.79 oder neuer

## ROS 2 Jazzy einrichten

Die RoboStack-Abhängigkeiten sind zentral in `pixi.toml` definiert und in `pixi.lock` gesperrt.

```powershell
pixi install
pixi run ros2 --help
```

Auf diesem Windows-System verwendet die Umgebung Cyclone DDS und bindet die lokale Discovery explizit an das Loopback-Interface. Dadurch kommunizieren lokale ROS-2-Prozesse zuverlässig trotz VPN- und virtueller Netzwerkadapter. Für Kommunikation mit einem externen Rechner oder Roboter muss diese localhost-spezifische DDS-Konfiguration angepasst werden.

## Struktur

| Pfad | Inhalt |
| --- | --- |
| `testnachweis/` | Testskripte T1–T3a (Sprache, Gesten, Kamera) und Ergebnisse |
| `workspace/src/` | ROS-2-Pakete: Interfaces, Wahrnehmung, Verhalten, Simulation und Bringup |
| `simulation/webots/` | Bestehende Webots-Welten, Controller und PROTO-Modelle |
| `models/` | Lokale Modelle (Vosk, MediaPipe, YOLO), nicht versioniert; Bezug in den README-Dateien |
| `config/` | Projektweite Konfigurationen |
| `scripts/` | Hilfsskripte für Entwicklung und Betrieb |
| `docs/` | Projektdokumentation |

Generierte Pixi-Umgebungen, ROS-Buildartefakte, Caches sowie große Modelle und Datasets werden nicht versioniert.

## Aktueller Stand

- **ROS 2 Jazzy unter Windows:** Lauffähig über Pixi/RoboStack mit Cyclone DDS. Vosk, MediaPipe und sounddevice sind in derselben Pixi-Umgebung installiert.
- **ROS-2-Pakete** (`workspace/src`): Sprache, Gesten, Kamera, Knochenerkennung, Verhalten und Simulation laufen als eigene Nodes und sprechen über typisierte Messages aus `pren_interfaces`. Aufbau, Topics und Verhalten: [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md).
- **Befehle:** HIER, BRAV, SITZ, SUCH per Sprache; SITZ, PLATZ, AUF per Geste. Während SUCH läuft, werden alle anderen Befehle ignoriert.
- **Simulation:** Webots mit Pioneer 3-DX. SUCH dreht zum Suchbereich, sucht den zufällig platzierten Knochen, bellt, kehrt zurück und setzt sich mit einem Abschlusston. Haltung und Lob werden als Text im 3D-Fenster angezeigt. Ein Bedienfenster sendet alle Befehle und setzt die Welt zurück.
- **Tests:** `pixi run test` führt Unit-Tests, einen ROS-Integrationstest und die Linter aus.
- **Prototypen entfernt (25.11.2026):** Die früheren Sprach- und Gesten-Prototypen (`prototypes/`, eigene venvs, UDP) und der alte Ablauf mit `such_driver` (Paket `pren_control`) sind gelöscht; ihre Logik steckt in `pren_perception` und `pren_behavior`. Die Testskripte T1–T3a liegen unter `testnachweis/`.

## Schnellstart Simulation

```powershell
# Baut den Workspace und startet Webots, Bridge, Verhalten, Bedienfenster, Sprache und Gesten:
.\scripts\start_simulation.bat

# Bauen und testen:
pixi run build
pixi run test

# Simulation während der Laufzeit zurücksetzen:
.\scripts\reset_simulation.bat
```

## Detaillierte Dokumentation

* 📖 **[Simulations-Handbuch & Setup-Guide](simulation/README.md)** – Vollständige Anleitung zur Installation von Pixi, Webots und den Python-Virtual-Environments, Fehlerbehebung, FSM-Ablauf und Parametern.
* 🧩 **[ROS-2-Architektur](docs/ARCHITEKTUR.md)** – Pakete, Nodes, Topics, Verhalten, Bauen und Testen.
* 🛰️ **[Schnittstellen des Prototyp-Ablaufs](docs/INTERFACES.md)** – UDP-Bridge und `such_driver` (historisch, entfernt; aktueller Stand in ARCHITEKTUR.md).

