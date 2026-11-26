# Handmodell (MediaPipe)

Die Gestenerkennung (`gesture_command_node`, Testskript T2) nutzt das MediaPipe-Modell
`hand_landmarker.task` (ca. 8 MB). Es wird nicht in Git versioniert.

Einrichten: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
herunterladen und hier als `models/gesture/hand_landmarker.task` ablegen.

Die Launch-Dateien und Testskripte finden das Modell dort automatisch
(`pren_bringup/repo_paths.py`).
