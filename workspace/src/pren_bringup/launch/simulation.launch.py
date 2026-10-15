"""Master Launch File: Start Webots, Bridge, Such-Treiber, Control-Panel, Voice- & Gesture-Prototypes.

Unified PREN Simulation Pipeline (Gruppe 17):
- Webots R2025a mit zentrierter Kameraposition ueber dem Startfeld
- Supervisor-gesteuerte Pioneer 3-DX Bridge mit 30°-Sichtkegel
- Autonomer Such-Treiber (Startet 180° abgewandt, wartet auf Befehl, 2x Geschwindigkeit)
- Grafisches Simulator-Control-Panel (Reset & Live-Status)
- Sprachsteuerung (Vosk German Offline Engine)
- Gestensteuerung (MediaPipe 3D Hand Landmarks)
"""

import os
from pathlib import Path
import sys

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, TimerAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


WEBOTS_PORT = 1234


def find_repo_root() -> Path:
    search_locations = [
        Path.cwd(),
        Path(__file__).resolve().parent,
    ]

    for start in search_locations:
        for directory in [start, *start.parents]:
            if (
                (directory / "pixi.toml").exists()
                and (directory / "simulation" / "webots").exists()
            ):
                return directory

    raise RuntimeError("PREN Repository-Root konnte nicht gefunden werden.")


def find_executable(root: Path, filename: str) -> Path:
    matches = list(root.rglob(filename))

    if not matches:
        raise RuntimeError(f"{filename} wurde unter {root} nicht gefunden.")

    return matches[0]


def generate_launch_description():
    repo_root = find_repo_root()

    # Launch-Argumente
    launch_voice_arg = DeclareLaunchArgument(
        "launch_voice",
        default_value="true",
        description="Spracherkennungsprototyp parallel zur Simulation starten.",
    )

    launch_gesture_arg = DeclareLaunchArgument(
        "launch_gesture",
        default_value="true",
        description="Gestenerkennungsprototyp parallel zur Simulation starten.",
    )

    # Webots Installation
    default_webots_home = (
        Path(os.environ["LOCALAPPDATA"])
        / "Programs"
        / "Webots"
    )

    webots_home = Path(
        os.environ.get(
            "WEBOTS_HOME",
            str(default_webots_home),
        )
    )

    if not webots_home.exists():
        fallback_webots = (
            Path(os.environ.get("ProgramFiles", "C:/Program Files"))
            / "Webots"
        )
        if fallback_webots.exists():
            webots_home = fallback_webots
        else:
            raise RuntimeError(f"Webots wurde nicht gefunden: {webots_home}")

    webots_exe = find_executable(webots_home, "webots.exe")
    webots_controller_exe = find_executable(webots_home, "webots-controller.exe")

    # Projektdateien
    world_file = (
        repo_root
        / "simulation"
        / "webots"
        / "worlds"
        / "pren_simulation.wbt"
    )

    controller_file = (
        repo_root
        / "simulation"
        / "webots"
        / "controllers"
        / "webots_bridge"
        / "webots_bridge.py"
    )

    if not world_file.exists():
        raise RuntimeError(f"Webots-Welt nicht gefunden: {world_file}")

    if not controller_file.exists():
        raise RuntimeError(f"Webots-Controller nicht gefunden: {controller_file}")

    # 1. Webots Simulator starten
    webots = ExecuteProcess(
        cmd=[
            str(webots_exe),
            f"--port={WEBOTS_PORT}",
            "--mode=realtime",
            str(world_file),
        ],
        output="screen",
        additional_env={
            "WEBOTS_HOME": str(webots_home),
        },
    )

    # 2. Externen Bridge-Controller starten
    webots_controller = ExecuteProcess(
        cmd=[
            str(webots_controller_exe),
            f"--port={WEBOTS_PORT}",
            str(controller_file),
        ],
        output="screen",
        additional_env={
            "WEBOTS_HOME": str(webots_home),
        },
    )

    # 3. Autonomen Such-Treiber starten (startet in IDLE, nimmt alle Befehle an)
    such_driver_node = Node(
        package="pren_control",
        executable="such_driver",
        output="screen",
        parameters=[
            {"auto_start": False},
            {"search_speed": 0.36},
            {"return_speed": 0.44},
        ],
    )

    # 4. Simulator Control-Panel (Reset & Live-Status)
    reset_gui_node = Node(
        package="pren_control",
        executable="reset_gui",
        output="screen",
    )

    # 5. Voice Control Prototyp
    voice_py = repo_root / "prototypes" / "voice_detection" / ".venv" / "Scripts" / "python.exe"
    if not voice_py.exists():
        voice_py = Path(sys.executable)
    voice_script = repo_root / "prototypes" / "voice_detection" / "voice_control.py"

    voice_process = ExecuteProcess(
        cmd=[
            str(voice_py),
            "-E",
            str(voice_script),
        ],
        cwd=str(repo_root / "prototypes" / "voice_detection"),
        output="screen",
        additional_env={
            "PYTHONPATH": "",
            "PYTHONHOME": "",
        },
        condition=IfCondition(LaunchConfiguration("launch_voice")),
    )

    # 6. Gesture Control Prototyp
    gesture_py = repo_root / "prototypes" / "gesture_recognition" / ".venv" / "Scripts" / "python.exe"
    if not gesture_py.exists():
        gesture_py = Path(sys.executable)
    gesture_script = repo_root / "prototypes" / "gesture_recognition" / "gesture_control.py"

    gesture_process = ExecuteProcess(
        cmd=[
            str(gesture_py),
            "-E",
            str(gesture_script),
        ],
        cwd=str(repo_root / "prototypes" / "gesture_recognition"),
        output="screen",
        additional_env={
            "PYTHONPATH": "",
            "PYTHONHOME": "",
        },
        condition=IfCondition(LaunchConfiguration("launch_gesture")),
    )

    return LaunchDescription([
        launch_voice_arg,
        launch_gesture_arg,

        webots,

        TimerAction(
            period=3.0,
            actions=[webots_controller],
        ),

        TimerAction(
            period=4.5,
            actions=[such_driver_node],
        ),

        TimerAction(
            period=5.0,
            actions=[reset_gui_node],
        ),

        TimerAction(
            period=5.5,
            actions=[voice_process],
        ),

        TimerAction(
            period=6.0,
            actions=[gesture_process],
        ),
    ])