"""
Startet die Simulation: Webots, ROS-Bridge, Verhalten, Wahrnehmung und Bedienfenster.

Aufruf:
    ros2 launch pren_bringup simulation.launch.py
    ros2 launch pren_bringup simulation.launch.py voice:=false gesture:=false
    ros2 launch pren_bringup simulation.launch.py control_panel:=false
    # fuer automatische Tests: Webots minimiert, ohne Darstellung, eigener Port
    ros2 launch pren_bringup simulation.launch.py webots_gui:=false webots_port:=1240
"""

import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    OpaqueFunction,
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

HEADLESS_WEBOTS_OPTIONS = ['--minimize', '--no-rendering', '--batch']


def webots_processes(context):
    """Webots und den Bridge-Controller mit dem gewaehlten Port starten."""
    port = LaunchConfiguration('webots_port').perform(context)
    show_gui = LaunchConfiguration('webots_gui').perform(context).lower() == 'true'
    webots_home = find_webots_home()
    simulation_dir = find_repo_root(Path.cwd()) / 'simulation' / 'webots'

    webots = ExecuteProcess(
        cmd=[str(find_file(webots_home, 'webots.exe')), f'--port={port}', '--mode=realtime',
             *([] if show_gui else HEADLESS_WEBOTS_OPTIONS),
             str(simulation_dir / 'worlds' / 'pren_simulation.wbt')],
        # Webots ohne Pixi-Umgebung starten, sonst laedt es fremde Qt-Plugins und stuerzt ab.
        env=webots_environment(os.environ, webots_home),
        output='screen',
    )
    webots_bridge = ExecuteProcess(
        cmd=[str(find_file(webots_home, 'webots-controller.exe')), f'--port={port}',
             str(simulation_dir / 'controllers' / 'pren_bridge' / 'pren_bridge.py')],
        additional_env={'WEBOTS_HOME': str(webots_home)},
        output='screen',
    )
    # Webots braucht einen Moment, bis der externe Controller verbinden kann.
    return [webots, TimerAction(period=3.0, actions=[webots_bridge])]


def generate_launch_description():
    bringup_dir = Path(get_package_share_directory('pren_bringup'))

    dog_behavior = Node(
        package='pren_behavior',
        executable='dog_behavior_node',
        name='dog_behavior',
        parameters=[str(bringup_dir / 'config' / 'behavior.yaml')],
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
        DeclareLaunchArgument('webots_gui', default_value='true',
                              description='false: Webots minimiert und ohne Darstellung.'),
        DeclareLaunchArgument('webots_port', default_value='1234',
                              description='Port, ueber den Bridge und Webots sprechen.'),
        OpaqueFunction(function=webots_processes),
        TimerAction(period=4.0, actions=[dog_behavior, control_panel, perception]),
    ])
