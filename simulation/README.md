# PREN Webots-Simulation

Diese Dokumentation beschreibt die aktuelle Simulation des PREN-Roboterhunds und zeigt, wie eigene ROS-2-Programme mit der Simulation verbunden werden.

Die Simulation ist bewusst so aufgebaut, dass die eigentliche Roboterlogik möglichst unabhängig von Webots bleibt.

---

## Architektur

Die aktuelle Kommunikation sieht so aus:

```text
Eigener ROS-Node
z. B. circle_driver
        │
        │ /cmd_vel
        ▼
webots_bridge.py
        │
        ▼
Pioneer 3-DX in Webots
        │
        │ Encoder
        ▼
webots_bridge.py
        │
        │ /joint_states
        ▼
ROS 2
```

Die Aufgaben sind klar getrennt:

- **ROS-Nodes** enthalten die eigentliche Roboterlogik.
- **Webots** simuliert Roboter, Motoren, Sensoren und Umgebung.
- **`webots_bridge.py`** übersetzt zwischen ROS 2 und Webots.
- **`simulation.launch.py`** startet die Simulations-Infrastruktur.

Dadurch kann ein ROS-Programm später grundsätzlich auch mit dem echten Roboter verwendet werden, sofern dort dieselben ROS-Schnittstellen bereitgestellt werden.

---

## Voraussetzungen

Vor dem ersten Start müssen die Schritte aus dem Haupt-README durchgeführt worden sein:

1. Pixi installieren
2. `pixi install`
3. ROS-Kommunikation mit Talker/Listener testen
4. eigenen ROS-Workspace bauen

Zusätzlich wird **Webots R2025a** benötigt.

Die aktuelle Welt verwendet das Format:

```text
#VRML_SIM R2025a utf8
```

Standardmäßig erwartet das Launchfile Webots unter:

```text
%LOCALAPPDATA%\Programs\Webots
```

Falls Webots an einem anderen Ort installiert ist, kann `WEBOTS_HOME` gesetzt werden:

```powershell
$env:WEBOTS_HOME="C:\Pfad\zu\Webots"
```

---

## Ordnerstruktur

```text
simulation/
└── webots/
    ├── controllers/
    │   └── webots_bridge/
    │       └── webots_bridge.py
    ├── protos/
    └── worlds/
        └── pren_simulation.wbt

workspace/src/
├── pren_bringup/
│   └── launch/
│       └── simulation.launch.py
└── pren_control/
    └── pren_control/
        └── circle_driver.py
```

### `pren_simulation.wbt`

Die Webots-Welt.

Aktuell wird ein **Pioneer 3-DX** als Testplattform verwendet.

Der Roboter ist in der Welt mit

```text
controller "<extern>"
```

konfiguriert.

Das bedeutet, dass Webots den Python-Controller nicht selbst startet, sondern auf einen extern gestarteten Controller wartet.

### `webots_bridge.py`

Die Brücke zwischen ROS 2 und Webots.

Sie:

- verbindet sich mit dem simulierten Pioneer
- subscribed auf `/cmd_vel`
- rechnet `linear.x` und `angular.z` in linke und rechte Radgeschwindigkeiten um
- steuert die beiden Webots-Motoren
- liest die beiden simulierten Encoder
- publiziert die Encoderwerte auf `/joint_states`
- stoppt die Motoren, wenn länger als `0.5 s` kein neuer Fahrbefehl empfangen wurde

### `simulation.launch.py`

Das ROS-Launchfile startet:

1. Webots
2. `pren_simulation.wbt`
3. den externen Webots-Controller `webots_bridge.py`

Das eigentliche Fahr- oder Roboterprogramm wird **nicht** automatisch gestartet.

Dadurch kann man unterschiedliche ROS-Nodes unabhängig mit derselben Simulation testen.

---

## Simulation starten

### 1. Pixi-Umgebung aktivieren

Im Repository-Root:

```powershell
pixi shell
```

### 2. ROS-Workspace laden

```powershell
cd workspace
. .\install\local_setup.ps1
```

Falls der Workspace noch nicht gebaut wurde oder ROS-Code geändert wurde:

```powershell
colcon build --merge-install
. .\install\local_setup.ps1
```

### 3. Simulation starten

```powershell
ros2 launch pren_bringup simulation.launch.py
```

Das Launchfile startet Webots und anschließend automatisch den externen Controller.

**Webots sollte vorher geschlossen sein.**

Die Simulation verwendet aktuell fest den Port:

```text
1234
```

Wenn bereits eine andere Webots-Instanz diesen Port verwendet, kann die Verbindung zum externen Controller fehlschlagen.

---

## Eigenes ROS-Programm in der Simulation starten

Das eigentliche ROS-Programm wird in einem separaten Terminal gestartet.

### Neues Terminal vorbereiten

```powershell
cd C:\Pfad\zum\Roboterhund-Gruppe17
pixi shell
cd workspace
. .\install\local_setup.ps1
```

Danach kann jeder gebaute ROS-Node gestartet werden.

Beispiel:

```powershell
ros2 run pren_control circle_driver
```

Der `circle_driver` kennt Webots nicht.

Er publiziert nur ROS-Nachrichten auf:

```text
/cmd_vel
```

`webots_bridge.py` empfängt diese Nachrichten und setzt sie in Motorbefehle für den simulierten Roboter um.

---

## `circle_driver` verwenden

Standardstart:

```powershell
ros2 run pren_control circle_driver
```

Standardparameter:

```text
radius       = 1.0 m
linear_speed = 0.2 m/s
```

Mit anderem Radius:

```powershell
ros2 run pren_control circle_driver --ros-args -p radius:=0.5
```

Mit Radius und Geschwindigkeit:

```powershell
ros2 run pren_control circle_driver --ros-args -p radius:=1.5 -p linear_speed:=0.3
```

Der Zusammenhang im Node ist:

```text
omega = v / r
```

mit:

- `v` = lineare Geschwindigkeit
- `r` = Kreisradius
- `omega` = Winkelgeschwindigkeit

Der Node publiziert daraus eine `geometry_msgs/msg/Twist`-Nachricht auf `/cmd_vel`.

---

## Aktuelle ROS-Topics

Bei laufender Simulation sind vor allem diese Topics relevant:

### `/cmd_vel`

Typ:

```text
geometry_msgs/msg/Twist
```

Richtung:

```text
ROS → Webots
```

Beispielinhalt:

```yaml
linear:
  x: 0.2
angular:
  z: 0.2
```

`linear.x` ist die Vorwärtsgeschwindigkeit in `m/s`.

`angular.z` ist die Drehgeschwindigkeit um die Hochachse in `rad/s`.

### `/joint_states`

Typ:

```text
sensor_msgs/msg/JointState
```

Richtung:

```text
Webots → ROS
```

Aktuell werden darin die beiden Radencoder publiziert:

```text
left_wheel_joint
right_wheel_joint
```

Die Positionen sind Raddrehwinkel in Radiant.

---

## Topics untersuchen

Alle Topics anzeigen:

```powershell
ros2 topic list
```

Informationen zu `/cmd_vel`:

```powershell
ros2 topic info /cmd_vel
```

Fahrbefehle live anzeigen:

```powershell
ros2 topic echo /cmd_vel
```

Encoderwerte live anzeigen:

```powershell
ros2 topic echo /joint_states
```

---

## Roboter ohne eigenes Programm manuell steuern

Zum Testen kann direkt auf `/cmd_vel` publiziert werden.

Geradeaus mit `0.2 m/s`:

```powershell
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2}, angular: {z: 0.0}}"
```

Auf der Stelle drehen:

```powershell
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0}, angular: {z: 0.5}}"
```

Mit `Ctrl+C` wird der Publisher beendet.

Der Watchdog in `webots_bridge.py` setzt die Radgeschwindigkeiten spätestens nach `0.5 s` ohne neue `/cmd_vel`-Nachricht auf `0`.

---

## Änderungen und Build-Verhalten

### ROS-Package geändert

Beispiele:

```text
workspace/src/pren_control/...
workspace/src/pren_bringup/...
```

Dann neu bauen:

```powershell
cd workspace
colcon build --merge-install
. .\install\local_setup.ps1
```

### Nur Webots-Datei geändert

Beispiele:

```text
simulation/webots/controllers/webots_bridge/webots_bridge.py
simulation/webots/worlds/pren_simulation.wbt
```

Dann ist kein `colcon build` notwendig.

Die Simulation einfach beenden und erneut starten:

```powershell
ros2 launch pren_bringup simulation.launch.py
```

---

## Ein neues ROS-Testprogramm hinzufügen

Neue Fahr- oder Steuerungslogik sollte grundsätzlich als ROS-Node in einem passenden ROS-Package implementiert werden und **nicht direkt in `webots_bridge.py`**.

Beispiel:

```text
workspace/src/pren_control/pren_control/my_driver.py
```

Ein Node, der den Roboter bewegen soll, publiziert normalerweise auf:

```text
/cmd_vel
```

Damit das Python-Programm über `ros2 run` gestartet werden kann, muss es im `setup.py` des Packages als `console_script` eingetragen werden.

Beispiel:

```python
entry_points={
    "console_scripts": [
        "circle_driver = pren_control.circle_driver:main",
        "my_driver = pren_control.my_driver:main",
    ],
},
```

Danach:

```powershell
cd workspace
colcon build --merge-install
. .\install\local_setup.ps1
```

Start:

```powershell
ros2 run pren_control my_driver
```

Die Simulation selbst muss dabei bereits mit

```powershell
ros2 launch pren_bringup simulation.launch.py
```

laufen.

---

## Was gehört wohin?

```text
workspace/src/pren_control/
```

Eigentliche Fahr- und Steuerungslogik.

```text
workspace/src/pren_bringup/
```

Launchfiles zum Starten von mehreren Komponenten bzw. der Infrastruktur.

```text
simulation/webots/controllers/webots_bridge/
```

Nur die Schnittstelle zwischen ROS und der simulierten Hardware.

```text
simulation/webots/worlds/
```

Webots-Welten.

Diese Trennung ist wichtig: Ein ROS-Node soll möglichst nicht wissen, ob er gerade einen simulierten oder später einen echten Roboter steuert.

---

## Typischer Entwicklungsablauf

### Terminal 1 – Simulation

```powershell
cd C:\Pfad\zum\Roboterhund-Gruppe17
pixi shell
cd workspace
. .\install\local_setup.ps1
ros2 launch pren_bringup simulation.launch.py
```

### Terminal 2 – eigenes Programm

```powershell
cd C:\Pfad\zum\Roboterhund-Gruppe17
pixi shell
cd workspace
. .\install\local_setup.ps1
ros2 run pren_control circle_driver
```

### Terminal 3 – Debugging

```powershell
cd C:\Pfad\zum\Roboterhund-Gruppe17
pixi shell
cd workspace
. .\install\local_setup.ps1
ros2 topic echo /joint_states
```

---

## Aktueller Simulationsstand

Aktuell funktioniert:

- Start von Webots über ROS Launch
- externer Webots-Controller
- ROS → Webots über `/cmd_vel`
- Webots → ROS über `/joint_states`
- Differential-Drive-Ansteuerung des Pioneer 3-DX
- Encoder-Ausgabe
- Watchdog für Fahrbefehle
- unabhängige ROS-Testprogramme wie `circle_driver`

Spätere Erweiterungen können zum Beispiel sein:

- `/odom`
- IMU
- Kamera
- Bumper/Kontaktsensor
- eigener Roboter statt Pioneer 3-DX
- Bone Detection und Suchlogik
