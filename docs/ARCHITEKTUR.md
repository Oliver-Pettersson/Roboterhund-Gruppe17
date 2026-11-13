# ROS-2-Architektur des Roboterhunds

Stand: 13.11.2026. Dieses Dokument beschreibt die ROS-2-Pakete unter `workspace/src`. Der frühere Ablauf mit UDP und `such_driver` ist in [INTERFACES.md](INTERFACES.md) beschrieben und über `simulation_prototype.launch.py` weiterhin startbar.

## Überblick

```mermaid
flowchart LR
    Mic([Mikrofon]) --> Voice[voice_command]
    Cam([Kamera]) --> Camera[camera]
    Camera -- /camera/image_raw --> Gesture[gesture_command]
    Camera -- /camera/image_raw --> Bone[bone_detection]
    Panel[control_panel] -- /pren/dog_command --> Behavior

    Voice -- /pren/dog_command --> Behavior[dog_behavior]
    Gesture -- /pren/dog_command --> Behavior
    Bone -- /pren/bone_detection --> Behavior

    Behavior -- /cmd_vel, /pren/posture, /pren/dog_signal --> Robot[webots_bridge<br>oder Motortreiber]
    Robot -- /odom --> Behavior
    Behavior -- /pren/robot_state --> Panel
```

In der Simulation liefert `webots_bridge` `/odom` und `/pren/bone_detection` (simulierter Sichtkegel). Auf dem Roboter übernehmen Motortreiber und `bone_detection` diese Rolle. Alle anderen Nodes bleiben gleich.

## Pakete

| Paket | Inhalt |
| --- | --- |
| `pren_interfaces` | Messages: `DogCommand`, `BoneDetection`, `Posture`, `DogSignal`, `RobotState` |
| `pren_behavior` | `dog_behavior_node` mit `DogStateMachine` (Befehle), `SearchMission` (SUCH), `ComeHereManeuver` (HIER) |
| `pren_perception` | `camera_node`, `voice_command_node`, `gesture_command_node`, `bone_detection_node` |
| `pren_simulation` | Webots-Bridge (gestartet über `simulation/webots/controllers/pren_bridge`), `control_panel` |
| `pren_bringup` | Launch-Dateien, `config/*.yaml`, Suche nach Webots und Modellen |
| `pren_control` | Alter Stand (`such_driver`, `reset_gui`), nur noch für den Prototyp-Ablauf |

## Aufbau eines Nodes

Jeder Node ist eine dünne Hülle: Parameter lesen, Topics verbinden, Messages umwandeln. Die eigentliche Logik liegt in reinen Python-Klassen ohne ROS, die mit `pytest` ohne Hardware getestet werden.

| Node | Logik-Klassen |
| --- | --- |
| `dog_behavior_node` | `DogStateMachine`, `SearchMission`, `ComeHereManeuver` |
| `voice_command_node` | `NoiseGate`, `find_command`, `RepeatFilter`, `VoiceCommandDetector` (+ `VoskRecognizer`, `Microphone`) |
| `gesture_command_node` | `classify_hand`, `GestureDebouncer`, `GestureCommandDetector` (+ `HandLandmarkDetector`) |
| `bone_detection_node` | `locate_bone` (+ `YoloBoneDetector`) |
| `webots_bridge` | `DifferentialDrive`, `VisionCone`, `DogAppearance` (+ `WebotsWorld`) |

## Topics

| Topic | Typ | Von | An |
| --- | --- | --- | --- |
| `/pren/dog_command` | `pren_interfaces/DogCommand` | voice, gesture, control_panel | dog_behavior |
| `/pren/bone_detection` | `pren_interfaces/BoneDetection` | bone_detection bzw. webots_bridge | dog_behavior, control_panel |
| `/pren/robot_state` | `pren_interfaces/RobotState` | dog_behavior (20 Hz) | control_panel, webots_bridge |
| `/pren/posture` | `pren_interfaces/Posture` (latched) | dog_behavior | webots_bridge / Beine |
| `/pren/dog_signal` | `pren_interfaces/DogSignal` | dog_behavior | webots_bridge / Lautsprecher |
| `/cmd_vel` | `geometry_msgs/Twist` | dog_behavior (20 Hz) | webots_bridge / Motortreiber |
| `/odom` | `nav_msgs/Odometry` | webots_bridge / Odometrie | dog_behavior |
| `/camera/image_raw` | `sensor_msgs/Image` | camera | gesture_command, bone_detection |
| `/pren/voice/level` | `std_msgs/Float32` | voice_command | Diagnose (Schwelle einstellen) |
| `/pren/reset` | `std_msgs/Empty` | control_panel, Skript | dog_behavior, webots_bridge |

## Verhalten

| Befehl | Erlaubte Quelle | Reaktion |
| --- | --- | --- |
| HIER | Sprache | 0,5 m auf die Person zu, dann stehen |
| BRAV | Sprache | Signal `PRAISE`, Zustand bleibt |
| SITZ | Sprache, Geste | Stopp, Haltung `SIT` |
| SUCH | Sprache | Drehen, Suchbereich absuchen, Knochen anfahren, bellen, zurück, zum Schiedsrichter drehen |
| PLATZ | Geste | Stopp, Haltung `LIE` |
| AUF | Geste | Haltung `STAND` |

Während SUCH läuft, werden alle Befehle ignoriert. Befehle aus einer nicht erlaubten Quelle werden ignoriert (`enforce_command_sources` in `config/behavior.yaml`). Das Bedienfenster darf alle Befehle senden.

## Bauen, testen, starten

```powershell
pixi run build          # colcon build
pixi run test           # alle Unit-, Integrations- und Lint-Tests

# Simulation mit Sprache und Gesten
.\scripts\start_simulation.bat
# nur Simulation, Befehle über das Bedienfenster
cd workspace; . .\install\local_setup.ps1
ros2 launch pren_bringup simulation.launch.py voice:=false gesture:=false
# nur Wahrnehmung am Laptop (z. B. für T1/T2)
ros2 launch pren_bringup perception.launch.py
ros2 topic echo /pren/dog_command
```

## Modelle

Die Launch-Dateien suchen die Modelle zuerst unter `models/`, dann in den Prototyp-Ordnern:

| Modell | Neuer Ort | Bisheriger Ort |
| --- | --- | --- |
| Vosk `vosk-model-small-de-0.15` | `models/voice/` | `prototypes/voice_detection/models/` |
| MediaPipe `hand_landmarker.task` | `models/gesture/` | `prototypes/gesture_recognition/` |
| YOLO Knochen | `models/bone_detection/` | noch nicht trainiert |

## Offene Punkte

1. **Spracherkennung löst bei Hintergrundgesprächen aus.** Vosk mit Grammatik ordnet jedes Wort dem ähnlichsten Befehl zu. Beim Test lief am Laptop nebenher Sprache und wurde öfter als SUCH/SITZ/HIER erkannt. Vorschlag: Wort-Konfidenz von Vosk auswerten und eine Mindestkonfidenz einführen (eigener Schritt, mit T1-Messungen abstimmen).
2. **Picamera2-Backend** für `camera_node` auf dem Pi 5.
3. **YOLO-Modell** trainieren und `bone_detection_node` mit `ultralytics` (bzw. NCNN) in die Umgebung aufnehmen.
4. **Motortreiber-Node** für den echten Roboter (`/cmd_vel`, `/pren/posture` → Hardware, `/odom` zurück).
