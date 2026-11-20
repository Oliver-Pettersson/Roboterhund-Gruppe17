"""
Verbindet die Webots-Simulation mit ROS 2. Ersetzt in der Simulation Motortreiber und Kamera.

Abonniert:
    /cmd_vel             geometry_msgs/Twist
    /pren/posture        pren_interfaces/Posture
    /pren/robot_state    pren_interfaces/RobotState
    /pren/dog_signal     pren_interfaces/DogSignal
    /pren/reset          std_msgs/Empty
Veroeffentlicht:
    /odom                nav_msgs/Odometry           (Ground Truth aus Webots)
    /joint_states        sensor_msgs/JointState      (Radencoder)
    /pren/bone_detection pren_interfaces/BoneDetection (simulierter Sichtkegel)
    /pren/reset_done     std_msgs/Empty

Gestartet wird die Datei von Webots ueber
simulation/webots/controllers/pren_bridge/pren_bridge.py.
"""

import math
from pathlib import Path
import random
import time

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from pren_interfaces.msg import BoneDetection, DogSignal, Posture, RobotState
from pren_simulation.dog_appearance import DogAppearance
from pren_simulation.simulation_math import (
    DifferentialDrive,
    random_bone_position,
    VisionCone,
    yaw_from_rotation_matrix,
)
from pren_simulation.sound_player import SoundPlayer
from pren_simulation.webots_world import WebotsWorld
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from sensor_msgs.msg import JointState
from std_msgs.msg import Empty

COMMAND_TIMEOUT_S = 0.5   # ohne neuen Fahrbefehl bleibt der Roboter stehen
LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)


class WebotsBridgeNode(Node):
    """ROS-Seite der Bridge: nimmt Befehle entgegen und veroeffentlicht Sensordaten."""

    def __init__(self):
        super().__init__('webots_bridge')
        self.appearance = DogAppearance()
        self.reset_requested = False
        self.pending_signals = []
        self._velocity = (0.0, 0.0)
        self._velocity_received_at = -math.inf

        self.create_subscription(Twist, '/cmd_vel', self._on_cmd_vel, 10)
        self.create_subscription(Posture, '/pren/posture', self._on_posture, LATCHED)
        self.create_subscription(RobotState, '/pren/robot_state', self._on_robot_state, 10)
        self.create_subscription(DogSignal, '/pren/dog_signal', self._on_signal, 10)
        self.create_subscription(Empty, '/pren/reset', self._on_reset, 10)

        self._odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self._joint_pub = self.create_publisher(JointState, '/joint_states', 10)
        self._bone_pub = self.create_publisher(BoneDetection, '/pren/bone_detection', 10)
        self._reset_done_pub = self.create_publisher(Empty, '/pren/reset_done', 10)

    def requested_velocity(self, now: float) -> tuple:
        """Letzter Fahrbefehl (linear, angular) oder Stillstand nach Timeout."""
        if now - self._velocity_received_at > COMMAND_TIMEOUT_S:
            return 0.0, 0.0
        return self._velocity

    # ---------------------------------------------------------- Eingaenge

    def _on_cmd_vel(self, msg: Twist) -> None:
        self._velocity = (msg.linear.x, msg.angular.z)
        self._velocity_received_at = time.monotonic()

    def _on_posture(self, msg: Posture) -> None:
        self.appearance.posture = msg.posture

    def _on_robot_state(self, msg: RobotState) -> None:
        self.appearance.activity = msg.activity

    def _on_signal(self, msg: DogSignal) -> None:
        self.pending_signals.append(msg.signal)

    def _on_reset(self, _msg: Empty) -> None:
        self.reset_requested = True

    # ---------------------------------------------------------- Ausgaenge

    def publish_odometry(self, x: float, y: float, yaw: float,
                         linear: float, angular: float) -> None:
        """Veroeffentlicht die Roboterpose."""
        msg = Odometry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'odom'
        msg.child_frame_id = 'base_link'
        msg.pose.pose.position.x = x
        msg.pose.pose.position.y = y
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
        msg.twist.twist.linear.x = linear
        msg.twist.twist.angular.z = angular
        self._odom_pub.publish(msg)

    def publish_wheel_positions(self, left: float, right: float) -> None:
        """Veroeffentlicht die Encoderwerte der Raeder."""
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = ['left_wheel_joint', 'right_wheel_joint']
        msg.position = [left, right]
        self._joint_pub.publish(msg)

    def publish_bone(self, visible: bool, distance: float, bearing: float) -> None:
        """Veroeffentlicht, was der simulierte Sichtkegel vom Knochen sieht."""
        msg = BoneDetection()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'
        msg.detected = visible
        msg.distance_m = float(distance) if visible else 0.0
        msg.bearing_rad = float(bearing) if visible else 0.0
        msg.confidence = 1.0 if visible else 0.0
        self._bone_pub.publish(msg)

    def publish_reset_done(self) -> None:
        """Meldet, dass die Welt zurueckgesetzt ist."""
        self._reset_done_pub.publish(Empty())


class SimulationLoop:
    """Verbindet Webots-Welt und ROS-Node in jedem Simulationsschritt."""

    def __init__(self, world: WebotsWorld, node: WebotsBridgeNode, sounds: SoundPlayer):
        self._world = world
        self._node = node
        self._sounds = sounds
        self._drive = DifferentialDrive()
        self._cone = VisionCone()
        self._rng = random.Random()
        self._wheel_speeds = (0.0, 0.0)

    def run(self) -> None:
        """Laeuft, bis Webots beendet wird."""
        self._world.center_camera()
        self._place_bone_randomly()
        while self._world.step():
            rclpy.spin_once(self._node, timeout_sec=0.0)
            now = time.monotonic()
            if self._node.reset_requested or self._world.reset_key_pressed():
                self._reset()
            self._drive_robot(now)
            self._publish_sensors()
            self._update_effects(now)

    def _drive_robot(self, now: float) -> None:
        left, right = self._drive.wheel_speeds(*self._node.requested_velocity(now))
        self._world.set_wheel_speeds(left, right)
        self._wheel_speeds = (left, right)

    def _publish_sensors(self) -> None:
        self._node.publish_wheel_positions(*self._world.wheel_positions())

        position, orientation = self._world.robot_position_and_orientation()
        x, y = position[0], position[1]
        yaw = yaw_from_rotation_matrix(orientation)
        self._node.publish_odometry(x, y, yaw, *self._drive.body_velocity(*self._wheel_speeds))

        bone = self._world.bone_position()
        if bone is not None:
            visible, distance, bearing = self._cone.observe(x, y, yaw, *bone)
            self._node.publish_bone(visible, distance, bearing)
            self._world.highlight_vision_cone(visible)

    def _update_effects(self, now: float) -> None:
        appearance = self._node.appearance
        for signal in self._node.pending_signals:
            sound = appearance.on_signal(signal, now)
            if sound:
                self._sounds.play(sound)
        self._node.pending_signals.clear()
        self._world.set_light_intensity(appearance.light_intensity(now))
        self._world.show_status(appearance.status_text(now))

    def _reset(self) -> None:
        self._sounds.stop()
        self._world.move_robot_to_start()
        self._place_bone_randomly()
        self._world.center_camera()
        self._node.appearance.reset()
        self._node.pending_signals.clear()
        self._node.reset_requested = False
        self._node.publish_reset_done()
        self._node.get_logger().info('Simulation zurueckgesetzt.')

    def _place_bone_randomly(self) -> None:
        x, y = random_bone_position(self._rng)
        self._world.place_bone(x, y)
        self._node.get_logger().info(f'Knochen liegt bei x={x:.2f} m, y={y:.2f} m.')


def main(sounds_dir: Path) -> None:
    """Startet die Bridge. Muss aus einem Webots-Controller aufgerufen werden."""
    from controller import Supervisor  # nur verfuegbar, wenn Webots den Prozess startet

    world = WebotsWorld(Supervisor())
    rclpy.init()
    node = WebotsBridgeNode()
    sounds = SoundPlayer(sounds_dir)
    try:
        SimulationLoop(world, node, sounds).run()
    finally:
        sounds.stop()
        world.set_wheel_speeds(0.0, 0.0)
        node.destroy_node()
        rclpy.try_shutdown()
