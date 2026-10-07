import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import JointState

from controller import Robot


# Pioneer 3-DX
WHEEL_RADIUS = 0.0975   # m
WHEEL_BASE = 0.33       # m
MAX_WHEEL_SPEED = 12.3  # rad/s

COMMAND_TIMEOUT = 0.5   # s


class WebotsBridge(Node):

    def __init__(self):
        super().__init__("webots_pioneer")

        self.left_speed = 0.0
        self.right_speed = 0.0

        self.last_command_time = time.monotonic()

        # -----------------------------------------------------
        # ROS -> Webots
        # -----------------------------------------------------

        self.create_subscription(
            Twist,
            "/cmd_vel",
            self.cmd_vel_callback,
            10,
        )

        # -----------------------------------------------------
        # Webots -> ROS
        # -----------------------------------------------------

        self.encoder_publisher = self.create_publisher(
            JointState,
            "/joint_states",
            10,
        )

        self.get_logger().info(
            "Webots bridge started"
        )

    def cmd_vel_callback(self, msg):

        linear = msg.linear.x
        angular = msg.angular.z

        # Differential-Drive-Kinematik
        left = (
            linear - angular * WHEEL_BASE / 2.0
        ) / WHEEL_RADIUS

        right = (
            linear + angular * WHEEL_BASE / 2.0
        ) / WHEEL_RADIUS

        self.left_speed = max(
            -MAX_WHEEL_SPEED,
            min(MAX_WHEEL_SPEED, left),
        )

        self.right_speed = max(
            -MAX_WHEEL_SPEED,
            min(MAX_WHEEL_SPEED, right),
        )

        self.last_command_time = time.monotonic()

    def update_watchdog(self):

        if (
            time.monotonic() - self.last_command_time
            > COMMAND_TIMEOUT
        ):
            self.left_speed = 0.0
            self.right_speed = 0.0

    def publish_encoders(
        self,
        left_position,
        right_position,
    ):

        msg = JointState()

        msg.header.stamp = (
            self.get_clock().now().to_msg()
        )

        msg.name = [
            "left_wheel_joint",
            "right_wheel_joint",
        ]

        msg.position = [
            left_position,
            right_position,
        ]

        self.encoder_publisher.publish(msg)


# =============================================================
# Webots
# =============================================================

robot = Robot()

timestep = int(
    robot.getBasicTimeStep()
)

# -------------------------------------------------------------
# Motoren
# -------------------------------------------------------------

left_motor = robot.getDevice(
    "left wheel"
)

right_motor = robot.getDevice(
    "right wheel"
)

left_motor.setPosition(float("inf"))
right_motor.setPosition(float("inf"))

left_motor.setVelocity(0.0)
right_motor.setVelocity(0.0)

# -------------------------------------------------------------
# Encoder
# -------------------------------------------------------------

left_encoder = robot.getDevice(
    "left wheel sensor"
)

right_encoder = robot.getDevice(
    "right wheel sensor"
)

left_encoder.enable(timestep)
right_encoder.enable(timestep)

# -------------------------------------------------------------
# ROS
# -------------------------------------------------------------

rclpy.init()

node = WebotsBridge()

try:

    while robot.step(timestep) != -1:

        # ROS-Nachrichten empfangen
        rclpy.spin_once(
            node,
            timeout_sec=0,
        )

        node.update_watchdog()

        # Motoren ansteuern
        left_motor.setVelocity(
            node.left_speed
        )

        right_motor.setVelocity(
            node.right_speed
        )

        # Encoder aus Webots lesen
        left_position = (
            left_encoder.getValue()
        )

        right_position = (
            right_encoder.getValue()
        )

        # Encoder über ROS veröffentlichen
        node.publish_encoders(
            left_position,
            right_position,
        )

finally:

    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    node.destroy_node()

    rclpy.shutdown()