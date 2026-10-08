# Roboterhund – PREN Gruppe 17

Gemeinsames Repository für den PREN-Roboterhund der Gruppe 17.

Das Repository enthält aktuell:

- die ROS-2-Entwicklungsumgebung mit Pixi/RoboStack
- die Webots-Simulation
- erste ROS-2-Pakete und Testprogramme
- bestehende Gesture- und Voice-Prototypen
- die vorgesehene Struktur für Wahrnehmung, Steuerung, Interfaces und Bringup

## Voraussetzungen

Die aktuelle Entwicklungsumgebung ist für **Windows 11 (win-64)** eingerichtet.

Benötigt werden:

- Git
- Pixi
- Webots R2025a für die Simulation

ROS 2 muss **nicht separat installiert** werden. ROS 2 Jazzy und die benötigten ROS-Werkzeuge werden über Pixi/RoboStack installiert.

---

## 1. Repository klonen

```powershell
git clone https://github.com/Oliver-Pettersson/Roboterhund-Gruppe17.git
cd Roboterhund-Gruppe17
```

Alle folgenden Pixi-Befehle werden normalerweise im Repository-Root ausgeführt:

```text
Roboterhund-Gruppe17/
├── pixi.toml
├── pixi.lock
├── workspace/
├── simulation/
├── prototypes/
└── ...
```

---

## 2. Pixi installieren

Falls Pixi noch nicht installiert ist, kann es unter Windows mit dem offiziellen Installer installiert werden:

```powershell
powershell -ExecutionPolicy Bypass -c "irm -useb https://pixi.sh/install.ps1 | iex"
```

Danach das Terminal neu öffnen und prüfen:

```powershell
pixi --version
```

Dokumentation: https://pixi.sh/

---

## 3. ROS 2 Jazzy über Pixi installieren

Die benötigten Abhängigkeiten sind bereits zentral in `pixi.toml` definiert und durch `pixi.lock` reproduzierbar festgelegt.

Im Repository-Root:

```powershell
pixi install
```

Dadurch wird unter `.pixi/` die lokale Entwicklungsumgebung erzeugt.

Die aktuell verwendeten Hauptabhängigkeiten sind:

- ROS 2 Jazzy Desktop
- ROS Development Tools
- Cyclone DDS als ROS Middleware

Die `.pixi/`-Umgebung wird nicht in Git eingecheckt.

### Pixi-Umgebung aktivieren

```powershell
pixi shell
```

Wenn die Umgebung aktiv ist, erscheint in PowerShell beispielsweise:

```text
(roboterhund-gruppe17) PS C:\...\Roboterhund-Gruppe17>
```

ROS 2 testen:

```powershell
ros2 --help
```

---

## 4. ROS-2-Kommunikation testen

Nach einer neuen Installation sollte zuerst geprüft werden, ob zwei lokale ROS-Prozesse miteinander kommunizieren können.

### Terminal 1 – Talker

Im Repository-Root:

```powershell
pixi shell
ros2 run demo_nodes_cpp talker
```

Der Talker sollte fortlaufend Meldungen wie diese ausgeben:

```text
Publishing: 'Hello World: 1'
Publishing: 'Hello World: 2'
...
```

### Terminal 2 – Listener

Ein zweites PowerShell-Fenster öffnen:

```powershell
cd C:\Pfad\zum\Roboterhund-Gruppe17
pixi shell
ros2 run demo_nodes_cpp listener
```

Der Listener sollte die Nachrichten des Talkers empfangen:

```text
I heard: [Hello World: 1]
I heard: [Hello World: 2]
...
```

Optional kann geprüft werden, ob das Topic sichtbar ist:

```powershell
ros2 topic list --no-daemon
```

Dabei sollte unter anderem erscheinen:

```text
/chatter
```

### Falls Talker und Listener sich nicht sehen

Die Pixi-Konfiguration verwendet absichtlich:

- `rmw_cyclonedds_cpp`
- `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`
- das Windows-Loopback-Interface für Cyclone DDS

Diese Konfiguration verhindert auf den Entwicklungsrechnern Probleme mit VPN- und virtuellen Netzwerkadaptern.

Falls die Kommunikation trotzdem nicht funktioniert:

```powershell
ros2 daemon stop
```

Danach Talker und Listener neu starten und zur Kontrolle verwenden:

```powershell
ros2 topic list --no-daemon
```

**Wichtig:** Die aktuelle DDS-Konfiguration ist bewusst auf den lokalen Rechner beschränkt. Sobald ROS 2 später zwischen Laptop, Raspberry Pi oder einem anderen Rechner kommunizieren soll, muss diese Konfiguration angepasst werden.

---

## 5. Eigenen ROS-2-Workspace bauen

Die eigenen ROS-Pakete liegen unter:

```text
workspace/src/
```

Aktuell existieren unter anderem:

```text
workspace/src/
├── pren_control/
├── pren_bringup/
├── pren_perception/
├── pren_interfaces/
└── pren_simulation/
```

Zum Bauen:

```powershell
cd workspace
colcon build --merge-install
```

Danach muss der gebaute Workspace in das aktuelle Terminal geladen werden:

```powershell
. .\install\local_setup.ps1
```

Anschließend kennt ROS die eigenen Packages, zum Beispiel:

```powershell
ros2 pkg list | Select-String pren_
```

### Warum `local_setup.ps1`?

ROS 2 selbst wurde bereits durch `pixi shell` geladen.

Darum wird für unseren eigenen Workspace nur

```powershell
. .\install\local_setup.ps1
```

verwendet.

`install\setup.ps1` versucht zusätzlich die darunterliegende ROS-Installation erneut zu laden und kann in der Pixi/RoboStack-Umgebung zu falschen Prefix-Pfaden führen.

### Nach Änderungen am ROS-Code

Wenn Dateien innerhalb eines ROS-Packages geändert wurden:

```powershell
cd workspace
colcon build --merge-install
. .\install\local_setup.ps1
```

Danach kann der aktualisierte Node gestartet werden.

---

## 6. Beispiel: `circle_driver`

`pren_control` enthält aktuell einen einfachen Test-Node namens `circle_driver`.

Start:

```powershell
ros2 run pren_control circle_driver
```

Der Node publiziert Fahrbefehle auf:

```text
/cmd_vel
```

Standardmäßig fährt der Roboter mit:

- Kreisradius: `1.0 m`
- Geschwindigkeit: `0.2 m/s`

Parameter können beim Start mitgegeben werden:

```powershell
ros2 run pren_control circle_driver --ros-args -p radius:=0.5
```

oder:

```powershell
ros2 run pren_control circle_driver --ros-args -p radius:=1.5 -p linear_speed:=0.3
```

Parameter können auch während der Laufzeit geändert werden:

```powershell
ros2 param set /circle_driver radius 2.0
```

---

## 7. Projektstruktur

| Pfad | Inhalt |
| --- | --- |
| `prototypes/` | Bestehende Gesture- und Voice-Prototypen; aktuell noch eigenständig |
| `workspace/src/pren_control/` | ROS-Steuerungslogik und Test-Nodes |
| `workspace/src/pren_bringup/` | ROS-Launchfiles, unter anderem für die Simulation |
| `workspace/src/pren_perception/` | Vorgesehene ROS-Nodes für Kamera, Gesten, Sprache und Objekterkennung |
| `workspace/src/pren_interfaces/` | Vorgesehene eigene Messages/Services, falls benötigt |
| `workspace/src/pren_simulation/` | Vorgesehene ROS-spezifische Simulationskomponenten |
| `simulation/` | Webots-Simulation und Simulationsdokumentation |
| `models/bone_detection/` | Ablage für Bone-Detection-Modelle und zugehörige Hinweise |
| `config/` | Projektweite Konfigurationen |
| `scripts/` | Hilfsskripte |
| `docs/` | Projektdokumentation |

Generierte Pixi-Umgebungen, ROS-Buildartefakte, Caches, große Modelle, Datasets und Rosbags werden nicht versioniert.

---

## 8. Aktueller Stand

Folgende Grundlagen funktionieren bereits:

- ROS 2 Jazzy unter Windows über Pixi/RoboStack
- Cyclone DDS für zuverlässige lokale Kommunikation
- Talker/Listener-Test
- ROS-Workspace mit `colcon`
- Webots-Simulation
- ROS → Webots über `/cmd_vel`
- Webots → ROS über `/joint_states`
- eigener Beispiel-Node `circle_driver`

Die bestehenden Voice- und Gesture-Prototypen befinden sich weiterhin unter `prototypes/` und werden später kontrolliert in die ROS-Architektur integriert.

Die detaillierte Anleitung zur Simulation befindet sich unter:

```text
simulation/README.md
```
