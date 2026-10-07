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

Die vorhandenen Prototypen und die Webots-Simulation wurden unverändert in diese Struktur übernommen. Die vorgesehenen ROS-2-Paketverzeichnisse sind zunächst Platzhalter; eine Migration der Prototypen in ROS-2-Nodes ist ausdrücklich noch nicht erfolgt.
