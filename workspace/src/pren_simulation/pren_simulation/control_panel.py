"""
Kleines Bedienfenster fuer Simulation und Tests.

Sendet Befehle (Quelle "gui") und Reset und zeigt den Zustand des Hundes an. Damit
laesst sich das Verhalten auch ohne Mikrofon und Kamera ausprobieren.
"""

import math
import threading
import tkinter as tk
from tkinter import ttk

from nav_msgs.msg import Odometry
from pren_interfaces.msg import BoneDetection, DogCommand, RobotState
import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty

COMMAND_BUTTONS = [
    ('HIER', DogCommand.HIER),
    ('BRAV', DogCommand.BRAV),
    ('SITZ', DogCommand.SITZ),
    ('SUCH', DogCommand.SUCH),
    ('PLATZ', DogCommand.PLATZ),
    ('AUF', DogCommand.AUF),
]
COMMAND_NAMES = {value: name for name, value in COMMAND_BUTTONS}


def describe_state(state: RobotState) -> str:
    """Einzeiliger Text zum Zustand des Hundes."""
    lock = ' (gesperrt)' if state.busy else ''
    return f'{state.state}{lock}: {state.activity}'


def describe_last_command(state: RobotState) -> str:
    """Letzter angenommener Befehl mit Quelle."""
    if state.last_command == 0:
        return 'noch keiner'
    name = COMMAND_NAMES.get(state.last_command, str(state.last_command))
    return f'{name} ({state.last_command_source})'


def describe_bone(detection: BoneDetection) -> str:
    """Kurzer Text zur Knochenerkennung."""
    if not detection.detected:
        return 'nicht im Blick'
    return f'{detection.distance_m:.2f} m, {math.degrees(detection.bearing_rad):.0f} Grad'


class ControlPanelNode(Node):
    """ROS-Seite des Bedienfensters."""

    def __init__(self):
        super().__init__('control_panel')
        self._command_pub = self.create_publisher(DogCommand, '/pren/dog_command', 10)
        self._reset_pub = self.create_publisher(Empty, '/pren/reset', 10)
        self.state = RobotState()
        self.bone = BoneDetection()
        self.position = (0.0, 0.0)
        self.create_subscription(RobotState, '/pren/robot_state', self._on_state, 10)
        self.create_subscription(BoneDetection, '/pren/bone_detection', self._on_bone, 10)
        self.create_subscription(Odometry, '/odom', self._on_odometry, 10)

    def send_command(self, command: int) -> None:
        """Sendet einen Befehl mit Quelle GUI."""
        self._command_pub.publish(
            DogCommand(command=command, source=DogCommand.SOURCE_GUI, confidence=1.0))

    def send_reset(self) -> None:
        """Setzt Simulation und Verhalten zurueck."""
        self._reset_pub.publish(Empty())

    def _on_state(self, msg: RobotState) -> None:
        self.state = msg

    def _on_bone(self, msg: BoneDetection) -> None:
        self.bone = msg

    def _on_odometry(self, msg: Odometry) -> None:
        self.position = (msg.pose.pose.position.x, msg.pose.pose.position.y)


class ControlPanelWindow:
    """Tkinter-Fenster mit Befehlsknoepfen, Reset und Statusanzeige."""

    REFRESH_MS = 100

    def __init__(self, root: tk.Tk, node: ControlPanelNode):
        self._root = root
        self._node = node
        root.title('PREN Bedienfeld')
        root.attributes('-topmost', True)

        frame = ttk.Frame(root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        buttons = ttk.LabelFrame(frame, text='Befehl senden', padding=8)
        buttons.pack(fill=tk.X)
        for index, (label, command) in enumerate(COMMAND_BUTTONS):
            ttk.Button(buttons, text=label, width=8,
                       command=lambda c=command: node.send_command(c)).grid(
                row=index // 3, column=index % 3, padx=3, pady=3)

        ttk.Button(frame, text='Reset (Startfeld, neuer Knochen)',
                   command=node.send_reset).pack(fill=tk.X, pady=8)

        status = ttk.LabelFrame(frame, text='Zustand', padding=8)
        status.pack(fill=tk.BOTH, expand=True)
        self._lines = {key: tk.StringVar() for key in ('state', 'command', 'bone', 'position')}
        for key, title in (('state', 'Hund'), ('command', 'Letzter Befehl'),
                           ('bone', 'Knochen'), ('position', 'Position')):
            row = ttk.Frame(status)
            row.pack(fill=tk.X)
            ttk.Label(row, text=f'{title}:', width=14).pack(side=tk.LEFT)
            ttk.Label(row, textvariable=self._lines[key]).pack(side=tk.LEFT)

        self._refresh()

    def _refresh(self) -> None:
        node = self._node
        self._lines['state'].set(describe_state(node.state))
        self._lines['command'].set(describe_last_command(node.state))
        self._lines['bone'].set(describe_bone(node.bone))
        self._lines['position'].set(f'x={node.position[0]:.2f} m, y={node.position[1]:.2f} m')
        self._root.after(self.REFRESH_MS, self._refresh)


def main(args=None):
    """Startet das Bedienfenster."""
    rclpy.init(args=args)
    node = ControlPanelNode()
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
    root = tk.Tk()
    ControlPanelWindow(root, node)
    try:
        root.mainloop()
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
