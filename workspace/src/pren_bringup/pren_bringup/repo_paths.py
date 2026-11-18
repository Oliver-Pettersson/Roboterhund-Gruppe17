"""Findet Repository, Webots-Installation und Simulationsdateien fuer die Launch-Dateien."""

import os
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    """Sucht vom Startordner aufwaerts den Ordner mit pixi.toml und simulation/webots."""
    for directory in (start, *start.parents):
        if (directory / 'pixi.toml').exists() and (directory / 'simulation' / 'webots').exists():
            return directory
    raise RuntimeError(f'Repository-Root nicht gefunden (gesucht ab {start}).')


def find_webots_home(environ=os.environ) -> Path:
    """Webots-Ordner aus WEBOTS_HOME oder den ueblichen Installationsorten."""
    candidates = []
    if environ.get('WEBOTS_HOME'):
        candidates.append(Path(environ['WEBOTS_HOME']))
    if environ.get('LOCALAPPDATA'):
        candidates.append(Path(environ['LOCALAPPDATA']) / 'Programs' / 'Webots')
    candidates.append(Path(environ.get('ProgramFiles', 'C:/Program Files')) / 'Webots')

    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError('Webots nicht gefunden. WEBOTS_HOME setzen oder Webots installieren.')


def find_file(root: Path, file_name: str) -> Path:
    """Erste Datei mit diesem Namen unterhalb von root."""
    for match in root.rglob(file_name):
        return match
    raise RuntimeError(f'{file_name} wurde unter {root} nicht gefunden.')


VOSK_MODEL_NAME = 'vosk-model-small-de-0.15'
HAND_MODEL_NAME = 'hand_landmarker.task'


def find_first_existing(repo_root: Path, candidates) -> Path:
    """Erster vorhandener Pfad (relativ zum Repository) aus der Liste."""
    for relative in candidates:
        path = repo_root / relative
        if path.exists():
            return path
    searched = ', '.join(str(Path(c)) for c in candidates)
    raise RuntimeError(f'Nicht gefunden unter {repo_root}: {searched}')


def find_vosk_model(repo_root: Path) -> Path:
    """Ordner des deutschen Vosk-Modells (neuer Ort zuerst, dann Prototyp-Ordner)."""
    return find_first_existing(repo_root, [
        f'models/voice/{VOSK_MODEL_NAME}',
        f'prototypes/voice_detection/models/{VOSK_MODEL_NAME}',
        f'VoiceDetection/models/{VOSK_MODEL_NAME}',
    ])


def find_hand_model(repo_root: Path) -> Path:
    """MediaPipe-Modell fuer Handpunkte (neuer Ort zuerst, dann Prototyp-Ordner)."""
    return find_first_existing(repo_root, [
        f'models/gesture/{HAND_MODEL_NAME}',
        f'prototypes/gesture_recognition/{HAND_MODEL_NAME}',
        f'GestureRecognition/{HAND_MODEL_NAME}',
    ])


def webots_environment(environ, webots_home: Path) -> dict:
    """
    Umgebung fuer den Webots-Simulator ohne die Pixi/Conda-Eintraege.

    Webots bringt ein eigenes Qt mit. Unter Pixi zeigen PATH und QT_PLUGIN_PATH auf
    das Qt der ROS-Umgebung; Webots laedt dann fremde Qt-Plugins und stuerzt beim
    Start ab (Windows-Fehler 0xC0000374). Deshalb werden alle Variablen entfernt,
    die in die Pixi-Umgebung zeigen, und PATH wird um deren Ordner bereinigt.
    """
    prefix = os.path.normcase(environ.get('CONDA_PREFIX', ''))

    def points_into_pixi(value: str) -> bool:
        return bool(prefix) and prefix in os.path.normcase(value)

    clean = {name: value for name, value in environ.items()
             if name.upper() != 'PATH' and not points_into_pixi(value)}
    path = environ.get('PATH', environ.get('Path', ''))
    clean['PATH'] = os.pathsep.join(
        entry for entry in path.split(os.pathsep) if entry and not points_into_pixi(entry))
    clean['WEBOTS_HOME'] = str(webots_home)
    return clean
