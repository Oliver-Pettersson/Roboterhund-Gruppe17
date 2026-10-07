# Prototypen

Dieser Ordner enthält eigenständig ausführbare Versuche aus der frühen PREN-Entwicklung. Sie bleiben bewusst von ROS 2 entkoppelt, bis Schnittstellen und Paketgrenzen festgelegt sind.

## Gesture Recognition

`gesture_recognition/` erkennt die Wettbewerbs-Handgesten mit MediaPipe und OpenCV. Installation, Ausführung und Tests sind in der zugehörigen README beschrieben.

## Voice Detection

`voice_detection/` erkennt deutsche Sprachkommandos offline mit Vosk. Python-Abhängigkeiten stehen in `requirements.txt`; das Sprachmodell wird lokal unter `models/` abgelegt und nicht in Git versioniert.
