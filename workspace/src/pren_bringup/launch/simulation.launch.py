"""
Startet die Simulation: Webots, ROS-Bridge, Verhalten, Wahrnehmung und Bedienfenster.

Aufruf:
    ros2 launch pren_bringup simulation.launch.py
    ros2 launch pren_bringup simulation.launch.py voice:=false gesture:=false
    ros2 launch pren_bringup simulation.launch.py control_panel:=false
"""

import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from pren_bringup.repo_paths import (
    find_file,
    find_repo_root,
    find_webots_home,
    webots_environment,
)

WEBOTS_PORT = 1234


def generate_launch_description():
    repo_root = find_repo_root(Path.cwd())
    webots_home = find_webots_home()
    webots_env = {'WEBOTS_HOME': str(webots_home)}
    simulation_dir = repo_root / 'simulation' / 'webots'
    bringup_dir = Path(get_package_share_directory('pren_bringup'))
    behavior_config = bringup_dir / 'config' / 'behavior.yaml'

    webots = ExecuteProcess(
        cmd=[str(find_file(webots_home, 'webots.exe')), f'--port={WEBOTS_PORT}',
             '--mode=realtime', str(simulation_dir / 'worlds' / 'pren_simulation.wbt')],
        # Webots ohne Pixi-Umgebung starten, sonst laedt es fremde Qt-Plugins und stuerzt ab.
        env=webots_environment(os.environ, webots_home),
        output='screen',
    )
    webots_bridge = ExecuteProcess(
        cmd=[str(find_file(webots_home, 'webots-controller.exe')), f'--port={WEBOTS_PORT}',
             str(simulation_dir / 'controllers' / 'pren_bridge' / 'pren_bridge.py')],
        additional_env=webots_env,
        output='screen',
    )
    dog_behavior = Node(
        package='pren_behavior',
        executable='dog_behavior_node',
        name='dog_behavior',
        parameters=[str(behavior_config)],
        output='screen',
    )
    control_panel = Node(
        package='pren_simulation',
        executable='control_panel',
        output='screen',
        condition=IfCondition(LaunchConfiguration('control_panel')),
    )

    perception = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(bringup_dir / 'launch' / 'perception.launch.py')),
        launch_arguments={'voice': LaunchConfiguration('voice'),
                          'gesture': LaunchConfiguration('gesture')}.items(),
    )

    return LaunchDescription([
        DeclareLaunchArgument('control_panel', default_value='true',
                              description='Bedienfenster mit Befehlsknoepfen starten.'),
        DeclareLaunchArgument('voice', default_value='true',
                              description='Spracherkennung (Mikrofon) starten.'),
        DeclareLaunchArgument('gesture', default_value='true',
                              description='Kamera und Gestenerkennung starten.'),
        webots,
        # Webots braucht einen Moment, bis der externe Controller verbinden kann.
        TimerAction(period=3.0, actions=[webots_bridge]),
        TimerAction(period=4.0, actions=[dog_behavior, control_panel, perception]),
    ])
