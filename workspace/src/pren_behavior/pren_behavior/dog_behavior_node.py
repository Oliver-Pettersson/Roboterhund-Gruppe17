"""
ROS-2-Node, der den DogStateMachine mit den Topics verbindet.

Der Node enthaelt keine Verhaltenslogik. Er uebersetzt nur Messages in die
Datentypen des Zustandsautomaten und zurueck.

Abonniert:
    /pren/dog_command    pren_interfaces/DogCommand   Befehle aus Sprache, Geste, GUI
    /pren/bone_detection pren_interfaces/BoneDetection
    /odom                nav_msgs/Odometry
    /pren/reset          std_msgs/Empty
Veroeffentlicht:
    /cmd_vel             geometry_msgs/Twist          mit control_rate_hz
    /pren/posture        pren_interfaces/Posture      bei Aenderung (latched)
    /pren/dog_signal     pren_interfaces/DogSignal    bei Ereignis
    /pren/robot_state    pren_interfaces/RobotState   mit control_rate_hz

Sicherheit: Kommt laenger als odom_timeout_s keine Odometrie, haelt der Hund an.
Knochenmeldungen, die aelter als bone_timeout_s sind, gelten als "kein Knochen".
"""

import math
from typing import Optional

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from pren_behavior.come_here import ComeHereParameters
from pren_behavior.commands import Command, CommandSource
from pren_behavior.dog_state_machine import (
    BehaviorParameters,
    DogStateMachine,
    Posture as PostureValue,
)
from pren_behavior.latest_reading import LatestReading
from pren_behavior.motion import BoneObservation, NO_BONE, Pose2D
from pren_behavior.search_mission import SearchParameters
from pren_interfaces.msg import BoneDetection, DogCommand, DogSignal, Posture, RobotState
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import Empty

LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)


def yaw_from_quaternion(z: float, w: float) -> float:
    """Gierwinkel aus einem Quaternion, das nur um die z-Achse dreht."""
    return 2.0 * math.atan2(z, w)


class DogBehaviorNode(Node):
    """Verbindet DogStateMachine mit ROS."""

    def __init__(self):
        super().__init__('dog_behavior')
        self._machine = DogStateMachine(self._read_parameters())
        # Ohne frische Odometrie wird angehalten, alte Knochenmeldungen werden verworfen.
        self._pose = LatestReading[Pose2D](self.get_parameter('odom_timeout_s').value)
        self._bone = LatestReading[BoneObservation](self.get_parameter('bone_timeout_s').value)
        self._published_posture: Optional[PostureValue] = None

        self._cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self._posture_pub = self.create_publisher(Posture, '/pren/posture', LATCHED)
        self._signal_pub = self.create_publisher(DogSignal, '/pren/dog_signal', 10)
        self._state_pub = self.create_publisher(RobotState, '/pren/robot_state', 10)

        self.create_subscription(DogCommand, '/pren/dog_command', self._on_command, 10)
        self.create_subscription(BoneDetection, '/pren/bone_detection', self._on_bone, 10)
        self.create_subscription(Odometry, '/odom', self._on_odometry, 10)
        self.create_subscription(Empty, '/pren/reset', self._on_reset, 10)

        rate_hz = self.get_parameter('control_rate_hz').value
        self.create_timer(1.0 / rate_hz, self._control_step)
        self.get_logger().info('Verhalten bereit, warte auf Befehle.')

    # ------------------------------------------------------------ Parameter

    def _read_parameters(self) -> BehaviorParameters:
        search_defaults = SearchParameters()
        come_defaults = ComeHereParameters()
        self.declare_parameter('control_rate_hz', 20.0)
        self.declare_parameter('enforce_command_sources', True)
        self.declare_parameter('odom_timeout_s', 0.5)
        self.declare_parameter('bone_timeout_s', 0.5)
        self.declare_parameter('search.search_speed', search_defaults.search_speed)
        self.declare_parameter('search.return_speed', search_defaults.return_speed)
        self.declare_parameter('search.contact_distance_m', search_defaults.contact_distance_m)
        self.declare_parameter('search.search_area_length_m',
                               search_defaults.search_area_length_m)
        self.declare_parameter('search.celebrate_duration_s',
                               search_defaults.celebrate_duration_s)
        self.declare_parameter('come_here.distance_m', come_defaults.distance_m)
        self.declare_parameter('come_here.speed', come_defaults.speed)

        def value(name: str) -> float:
            return self.get_parameter(name).value

        return BehaviorParameters(
            enforce_command_sources=value('enforce_command_sources'),
            search=SearchParameters(
                search_speed=value('search.search_speed'),
                return_speed=value('search.return_speed'),
                contact_distance_m=value('search.contact_distance_m'),
                search_area_length_m=value('search.search_area_length_m'),
                celebrate_duration_s=value('search.celebrate_duration_s'),
            ),
            come_here=ComeHereParameters(
                distance_m=value('come_here.distance_m'),
                speed=value('come_here.speed'),
            ),
        )

    # ------------------------------------------------------------- Eingaenge

    def _on_command(self, msg: DogCommand) -> None:
        try:
            command = Command(msg.command)
            source = CommandSource(msg.source)
        except ValueError:
            self.get_logger().warning(
                f'Unbekannter Befehl {msg.command} von Quelle "{msg.source}" verworfen.')
            return

        result = self._machine.handle_command(command, source)
        if result.accepted:
            self.get_logger().info(f'Befehl {command.name} ({source.value}) angenommen.')
        else:
            self.get_logger().info(f'Befehl {command.name} ({source.value}) ignoriert: '
                                   f'{result.reason}')

    def _on_bone(self, msg: BoneDetection) -> None:
        observation = BoneObservation(detected=msg.detected, distance_m=msg.distance_m,
                                      bearing_rad=msg.bearing_rad)
        self._bone.update(observation, self._now())

    def _on_odometry(self, msg: Odometry) -> None:
        pose = msg.pose.pose
        self._pose.update(
            Pose2D(x=pose.position.x, y=pose.position.y,
                   yaw=yaw_from_quaternion(pose.orientation.z, pose.orientation.w)),
            self._now())

    def _on_reset(self, _msg: Empty) -> None:
        self.get_logger().info('Reset: Verhalten in Ausgangszustand.')
        self._machine.reset()
        self._bone.clear()

    # ----------------------------------------------------------- Regelschritt

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def _control_step(self) -> None:
        now = self._now()
        pose = self._pose.get(now)
        if pose is None:
            # Ohne aktuelle Position kann der Hund nicht sicher fahren: anhalten.
            self._cmd_vel_pub.publish(Twist())
            if self._pose.ever_received:
                self.get_logger().warning('Keine aktuelle Odometrie, Hund haelt an.',
                                          throttle_duration_sec=2.0)
            return

        output = self._machine.update(pose, self._bone.get(now, NO_BONE), now)

        twist = Twist()
        twist.linear.x = output.velocity.linear
        twist.angular.z = output.velocity.angular
        self._cmd_vel_pub.publish(twist)

        if output.posture != self._published_posture:
            self._posture_pub.publish(Posture(posture=int(output.posture)))
            self._published_posture = output.posture

        for signal in output.signals:
            self.get_logger().info(f'Signal {signal.name}')
            self._signal_pub.publish(DogSignal(signal=int(signal)))

        self._publish_state()

    def _publish_state(self) -> None:
        machine = self._machine
        state = RobotState()
        state.header.stamp = self.get_clock().now().to_msg()
        state.state = machine.state.name
        state.activity = machine.activity
        state.busy = machine.is_busy
        state.posture = int(machine.posture)
        state.last_command = int(machine.last_command or 0)
        state.last_command_source = (machine.last_command_source.value
                                     if machine.last_command_source else '')
        self._state_pub.publish(state)

    def stop_robot(self) -> None:
        """Sendet einen Stopp-Befehl, z. B. beim Beenden."""
        self._cmd_vel_pub.publish(Twist())


def main(args=None):
    """Startet den dog_behavior-Node."""
    rclpy.init(args=args)
    node = DogBehaviorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop_robot()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
