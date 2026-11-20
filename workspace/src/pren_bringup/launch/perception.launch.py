"""
Startet die Wahrnehmung: Kamera, Gestenerkennung und Spracherkennung.

Allein nutzbar (z. B. fuer die Tests T1 und T2 am Laptop) oder eingebunden in
simulation.launch.py.

Aufruf:
    ros2 launch pren_bringup perception.launch.py
    ros2 launch pren_bringup perception.launch.py voice:=false
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from pren_bringup.repo_paths import find_hand_model, find_repo_root, find_vosk_model


def generate_launch_description():
    repo_root = find_repo_root(Path.cwd())
    config = str(Path(get_package_share_directory('pren_bringup')) / 'config' /
                 'perception.yaml')
    gesture_enabled = IfCondition(LaunchConfiguration('gesture'))

    camera = Node(
        package='pren_perception', executable='camera_node', name='camera',
        parameters=[config], output='screen', condition=gesture_enabled,
    )
    gesture_command = Node(
        package='pren_perception', executable='gesture_command_node', name='gesture_command',
        parameters=[config, {'model_path': str(find_hand_model(repo_root))}],
        output='screen', condition=gesture_enabled,
    )
    voice_command = Node(
        package='pren_perception', executable='voice_command_node', name='voice_command',
        parameters=[config, {'model_path': str(find_vosk_model(repo_root))}],
        output='screen', condition=IfCondition(LaunchConfiguration('voice')),
    )

    return LaunchDescription([
        DeclareLaunchArgument('voice', default_value='true',
                              description='Spracherkennung starten.'),
        DeclareLaunchArgument('gesture', default_value='true',
                              description='Kamera und Gestenerkennung starten.'),
        camera,
        gesture_command,
        voice_command,
    ])
