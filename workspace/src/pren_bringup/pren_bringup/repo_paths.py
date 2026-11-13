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
