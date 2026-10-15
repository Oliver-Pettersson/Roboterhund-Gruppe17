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
| `prototypes/` | Eigenständige Gesture- und Voice-Prototypen; noch keine ROS-2-Nodes |
| `workspace/src/` | Vorgesehene ROS-2-Pakete für Wahrnehmung, Steuerung, Interfaces, Simulation und Bringup |
| `simulation/webots/` | Bestehende Webots-Welten, Controller und PROTO-Modelle |
| `models/bone_detection/` | Ablagehinweise für lokale Bone-Detection-Modelle |
| `config/` | Projektweite Konfigurationen |
| `scripts/` | Hilfsskripte für Entwicklung und Betrieb |
| `docs/` | Projektdokumentation |

Generierte Pixi-Umgebungen, ROS-Buildartefakte, Caches sowie große Modelle und Datasets werden nicht versioniert.

## Aktueller Stand

- **ROS 2 Jazzy unter Windows:** Lauffähig über Pixi/RoboStack mit Cyclone DDS.
- **Integrierte Gesamtsimulation (Merged Pipeline):**
  - **180°-Startposition:** Der Roboter startet im Startfeld um $180^\circ$ abgewandt vom Suchbereich (Blick zum Schiedsrichter / Interaktionsbereich).
  - **Sprach- & Gestensteuerung:** `prototypes/voice_detection` (Vosk) und `prototypes/gesture_recognition` (MediaPipe) starten parallel und übertragen Kommandos nahtlos über UDP (Port 9876) und ROS 2 (`/pren/command`).
  - **Befehl «SUCH»:** Bei Sprachbefehl «Such» dreht sich der Roboter um $180^\circ$ zum Suchfeld. Während der gesamten Suche werden alle weiteren Befehle gesperrt, bis die Mission beendet ist.
  - **Suchfahrt & 2x Geschwindigkeit:** Roboter bewegt sich mit doppelter Geschwindigkeit ($0.36\,\text{m/s}$ Suchfahrt, $0.44\,\text{m/s}$ Rückfahrt).
  - **Brauner Knochen & Zufallsplatzierung:** Der Knochen ist braun gefärbt und wird bei jedem Start zufällig im $30^\circ$-Sektor platziert.
  - **Zentrierte Kamera:** Die Webots-Kameraperspektive ist erhöht und zentriert über dem Startfeld ausgerichtet mit direktem Blick in den Suchsektor.
  - **Fund & Rückkehr:** Nach Erreichen des Knochens ertönt genau ein Beller mit Lichteffekt, gefolgt von autonomer Rückfahrt ins Startfeld mit $180^\circ$-Drehung zurück zum Schiedsrichter und Freigabe für Folgekommandos.
  - **Simulator Control Panel:** Kompakte GUI mit grossem Setup-Reset-Button und Live-Statusanzeige (Phase, Position, Sichtkegel, letzter empfangener Befehl).

## Schnellstart Simulation

```powershell
# 1-Klick Start der Gesamtsimulation (Webots, Bridge, Such-Treiber, Control-Panel, Voice & Gestures):
.\scripts\start_simulation.bat

# Oder via PowerShell:
.\scripts\start_simulation.ps1

# Simulation während der Laufzeit zurücksetzen:
.\scripts\reset_simulation.bat
```

## Detaillierte Dokumentation

* 📖 **[Simulations-Handbuch & Setup-Guide](simulation/README.md)** – Vollständige Anleitung zur Installation von Pixi, Webots und den Python-Virtual-Environments, Fehlerbehebung, FSM-Ablauf und Parametern.
* 🛰️ **[Schnittstellenspezifikation](docs/INTERFACES.md)** – ROS-2-Topics, Message-Typen, UDP-Socket-Bridge und Hardware-Mapping.

