"""Integrationstest: dog_behavior_node ueber echte ROS-Topics ansprechen."""

import math
import time

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from pren_behavior.dog_behavior_node import DogBehaviorNode, yaw_from_quaternion
from pren_interfaces.msg import DogCommand, DogSignal, Posture, RobotState
import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile


class BehaviorHarness(Node):
    """Spielt Sprache, Geste und Odometrie und hoert auf die Ausgaben des Verhaltens."""

    def __init__(self):
        super().__init__('behavior_test_harness')
        self.command_pub = self.create_publisher(DogCommand, '/pren/dog_command', 10)
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.states, self.postures, self.signals, self.velocities = [], [], [], []
        self.odometry_running = True
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(RobotState, '/pren/robot_state', self.states.append, 10)
        self.create_subscription(Posture, '/pren/posture', self.postures.append, latched)
        self.create_subscription(DogSignal, '/pren/dog_signal', self.signals.append, 10)
        self.create_subscription(Twist, '/cmd_vel', self.velocities.append, 10)
        self.create_timer(0.05, self.publish_start_pose)

    def publish_start_pose(self):
        if not self.odometry_running:
            return
        odom = Odometry()
        odom.pose.pose.orientation.z = math.sin(math.pi / 2)
        odom.pose.pose.orientation.w = math.cos(math.pi / 2)
        self.odom_pub.publish(odom)

    def send(self, command: int, source: str):
        self.command_pub.publish(DogCommand(command=command, source=source, confidence=1.0))


# Eigene ROS-Domain, damit der Test nicht mit einer laufenden Simulation spricht.
TEST_DOMAIN_ID = 87


@pytest.fixture
def ros():
    rclpy.init(domain_id=TEST_DOMAIN_ID)
    behavior, harness = DogBehaviorNode(), BehaviorHarness()
    executor = SingleThreadedExecutor()
    executor.add_node(behavior)
    executor.add_node(harness)

    def spin_until(condition, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.05)
            if condition():
                return True
        return False

    yield harness, spin_until
    executor.shutdown()
    behavior.destroy_node()
    harness.destroy_node()
    rclpy.shutdown()


def test_publishes_standing_state_after_start(ros):
    harness, spin_until = ros

    assert spin_until(lambda: harness.states)
    assert harness.states[-1].state == 'STANDING'
    assert not harness.states[-1].busy


def test_gesture_platz_changes_posture_to_lie(ros):
    harness, spin_until = ros
    spin_until(lambda: harness.states)

    harness.send(DogCommand.PLATZ, DogCommand.SOURCE_GESTURE)

    assert spin_until(lambda: harness.postures and harness.postures[-1].posture == Posture.LIE)
    assert spin_until(lambda: harness.states[-1].state == 'LYING')
    assert harness.states[-1].last_command == DogCommand.PLATZ
    assert harness.states[-1].last_command_source == 'gesture'


def test_voice_brav_sends_praise_signal(ros):
    harness, spin_until = ros
    spin_until(lambda: harness.states)

    harness.send(DogCommand.BRAV, DogCommand.SOURCE_VOICE)

    assert spin_until(lambda: any(s.signal == DogSignal.PRAISE for s in harness.signals))


def test_voice_platz_is_ignored(ros):
    harness, spin_until = ros
    spin_until(lambda: harness.states)

    harness.send(DogCommand.PLATZ, DogCommand.SOURCE_VOICE)
    spin_until(lambda: False, timeout=0.5)

    assert harness.states[-1].state == 'STANDING'


def test_voice_such_marks_robot_busy(ros):
    harness, spin_until = ros
    spin_until(lambda: harness.states)

    harness.send(DogCommand.SUCH, DogCommand.SOURCE_VOICE)

    assert spin_until(lambda: harness.states[-1].busy)
    assert harness.states[-1].state == 'SEARCHING'


def test_unknown_command_is_dropped(ros):
    harness, spin_until = ros
    spin_until(lambda: harness.states)

    harness.send(99, DogCommand.SOURCE_VOICE)
    spin_until(lambda: False, timeout=0.3)

    assert harness.states[-1].last_command == 0


def test_yaw_from_quaternion_matches_rotation_about_z():
    angle = 2.0
    assert yaw_from_quaternion(math.sin(angle / 2), math.cos(angle / 2)) == pytest.approx(angle)


def test_robot_stops_when_odometry_stops(ros):
    harness, spin_until = ros
    spin_until(lambda: harness.states)
    harness.send(DogCommand.SUCH, DogCommand.SOURCE_VOICE)
    assert spin_until(lambda: harness.velocities and harness.velocities[-1].angular.z != 0.0)

    harness.odometry_running = False
    spin_until(lambda: False, timeout=1.0)

    last = harness.velocities[-1]
    assert last.linear.x == 0.0 and last.angular.z == 0.0


def test_robot_drives_on_when_odometry_returns(ros):
    harness, spin_until = ros
    spin_until(lambda: harness.states)
    harness.send(DogCommand.SUCH, DogCommand.SOURCE_VOICE)
    harness.odometry_running = False
    spin_until(lambda: False, timeout=1.0)

    harness.odometry_running = True

    assert spin_until(lambda: harness.velocities[-1].angular.z != 0.0)
