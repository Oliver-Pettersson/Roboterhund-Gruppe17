"""Start Webots and connect the external PREN simulation controller."""

import os
from pathlib import Path

from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction


WEBOTS_PORT = 1234


def find_repo_root() -> Path:
    """Find the repository containing both Pixi and Webots project files."""
    search_locations = [
        Path.cwd(),
        Path(__file__).resolve().parent,
    ]

    for start in search_locations:
        for directory in [start, *start.parents]:
            if (
                (directory / 'pixi.toml').exists()
                and (directory / 'simulation' / 'webots').exists()
            ):
                return directory

    raise RuntimeError(
        'PREN Repository-Root konnte nicht gefunden werden.'
    )


def find_executable(root: Path, filename: str) -> Path:
    """Return the first executable with *filename* below *root*."""
    matches = list(root.rglob(filename))

    if not matches:
        raise RuntimeError(
            f'{filename} wurde unter {root} nicht gefunden.'
        )

    return matches[0]


def generate_launch_description():
    """Build the ROS launch description for Webots and its controller."""
    repo_root = find_repo_root()

    # Webots Installation
    default_webots_home = (
        Path(os.environ['LOCALAPPDATA'])
        / 'Programs'
        / 'Webots'
    )

    webots_home = Path(
        os.environ.get(
            'WEBOTS_HOME',
            str(default_webots_home),
        )
    )

    if not webots_home.exists():
        raise RuntimeError(
            f'Webots wurde nicht gefunden: {webots_home}'
        )

    webots_exe = find_executable(
        webots_home,
        'webots.exe',
    )

    webots_controller_exe = find_executable(
        webots_home,
        'webots-controller.exe',
    )

    # Projektdateien
    world_file = (
        repo_root
        / 'simulation'
        / 'webots'
        / 'worlds'
        / 'pren_simulation.wbt'
    )

    controller_file = (
        repo_root
        / 'simulation'
        / 'webots'
        / 'controllers'
        / 'webots_bridge'
        / 'webots_bridge.py'
    )

    if not world_file.exists():
        raise RuntimeError(
            f'Webots-Welt nicht gefunden: {world_file}'
        )

    if not controller_file.exists():
        raise RuntimeError(
            f'Webots-Controller nicht gefunden: {controller_file}'
        )

    # Webots starten
    webots = ExecuteProcess(
        cmd=[
            str(webots_exe),
            f'--port={WEBOTS_PORT}',
            '--mode=realtime',
            str(world_file),
        ],
        output='screen',
    )

    # Externen Controller starten
    webots_controller = ExecuteProcess(
        cmd=[
            str(webots_controller_exe),
            f'--port={WEBOTS_PORT}',
            str(controller_file),
        ],
        output='screen',
        additional_env={
            'WEBOTS_HOME': str(webots_home),
        },
    )

    return LaunchDescription([
        webots,

        TimerAction(
            period=3.0,
            actions=[
                webots_controller,
            ],
        ),
    ])
