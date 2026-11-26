# Sprachmodell (Vosk)

Die Spracherkennung (`voice_command_node`, Testskript T1) nutzt das kleine deutsche
Vosk-Modell. Es ist ca. 45 MB gross (entpackt ca. 90 MB) und wird nicht in Git versioniert.

Einrichten:

1. https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip herunterladen.
2. Hier entpacken, sodass der Ordner `models/voice/vosk-model-small-de-0.15/` entsteht.

Die Launch-Dateien und Testskripte finden das Modell dort automatisch
(`pren_bringup/repo_paths.py`).
