"""Bridge ROS 2 velocity commands, odometry, bone detection, audio, reset, and Webots Pioneer devices."""

import math
import os
from pathlib import Path
import random
import threading
import time

try:
    import winsound
except ImportError:
    winsound = None

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PointStamped
from sensor_msgs.msg import JointState
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool, Empty

from controller import Supervisor, Speaker


# Pioneer 3-DX Parameter
WHEEL_RADIUS = 0.0975   # m
WHEEL_BASE = 0.33       # m
MAX_WHEEL_SPEED = 12.3  # rad/s

COMMAND_TIMEOUT = 0.5   # s

# Sichtkegel Parameter
CONE_RANGE = 3.0                      # m Reichweite
CONE_HALF_ANGLE = math.radians(22.5)  # 45 Grad Gesamtoeffnung


def normalize_angle(angle: float) -> float:
    """Normalize angle to [-pi, pi]."""
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


def play_audio_file(file_path: Path):
    """Play wave audio on host OS asynchronously (stops previous audio)."""
    if winsound is not None and file_path.exists():
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        threading.Thread(
            target=lambda: winsound.PlaySound(
                str(file_path),
                winsound.SND_FILENAME
            ),
            daemon=True,
        ).start()


def stop_audio():
    """Immediately stop any playing audio on host OS."""
    if winsound is not None:
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass


class WebotsBridge(Node):
    """Translate ROS commands to wheel speeds and publish sensor / detection states."""

    def __init__(self, sounds_dir: Path):
        super().__init__("webots_pioneer")
        self.sounds_dir = sounds_dir

        self.left_speed = 0.0
        self.right_speed = 0.0
        self.last_command_time = time.monotonic()

        self.effect_active = False
        self.bark_played = False
        self.last_detected_state = False
        self.reset_requested = False

        # -----------------------------------------------------
        # ROS -> Webots
        # -----------------------------------------------------
        self.create_subscription(
            Twist,
            "/cmd_vel",
            self.cmd_vel_callback,
            10,
        )

        self.create_subscription(
            Bool,
            "/pren/trigger_effect",
            self.trigger_effect_callback,
            10,
        )

        self.create_subscription(
            Bool,
            "/pren/final_signal",
            self.final_signal_callback,
            10,
        )

        self.create_subscription(
            Empty,
            "/pren/reset",
            self.reset_callback,
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

        self.odom_publisher = self.create_publisher(
            Odometry,
            "/odom",
            10,
        )

        self.bone_publisher = self.create_publisher(
            PointStamped,
            "/pren/bone_detection",
            10,
        )

        self.reset_done_publisher = self.create_publisher(
            Empty,
            "/pren/reset_done",
            10,
        )

        self.get_logger().info("PREN Webots bridge node started successfully.")

    def cmd_vel_callback(self, msg: Twist):
        """Convert a velocity command into bounded wheel speeds."""
        linear = msg.linear.x
        angular = msg.angular.z

        # Differential-Drive-Kinematik
        left = (linear - angular * WHEEL_BASE / 2.0) / WHEEL_RADIUS
        right = (linear + angular * WHEEL_BASE / 2.0) / WHEEL_RADIUS

        self.left_speed = max(-MAX_WHEEL_SPEED, min(MAX_WHEEL_SPEED, left))
        self.right_speed = max(-MAX_WHEEL_SPEED, min(MAX_WHEEL_SPEED, right))
        self.last_command_time = time.monotonic()

    def trigger_effect_callback(self, msg: Bool):
        """Toggle celebration visual and audio effects (barks only once)."""
        was_active = self.effect_active
        self.effect_active = msg.data

        # Flankenerkennung: Nur genau EINMAL beim Aktivieren bellen
        if self.effect_active and not was_active and not self.bark_played:
            self.get_logger().info("🦴 Knochen erreicht: Bellen (1x) und Lichteffekt aktiviert!")
            self.bark_played = True
            play_audio_file(self.sounds_dir / "dog_bark.wav")

        # Sobald Effekt abgeschaltet wird: Audio sofort stoppen
        elif not self.effect_active and was_active:
            self.get_logger().info("Feier beendet: Audio stummgeschaltet.")
            stop_audio()
            self.bark_played = False

    def final_signal_callback(self, msg: Bool):
        """Play final mission complete chime."""
        if msg.data:
            self.get_logger().info("🏁 Mission complete: Endsignal abgespielt.")
            play_audio_file(self.sounds_dir / "victory_chime.wav")

    def reset_callback(self, msg: Empty):
        """Handle reset command."""
        self.get_logger().info("🔄 Reset-Signal empfangen: Starte Zuruecksetzen...")
        self.reset_requested = True

    def update_watchdog(self):
        """Stop the simulated robot when velocity commands time out."""
        if time.monotonic() - self.last_command_time > COMMAND_TIMEOUT:
            self.left_speed = 0.0
            self.right_speed = 0.0

    def publish_encoders(self, left_position: float, right_position: float):
        """Publish wheel encoder states."""
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = ["left_wheel_joint", "right_wheel_joint"]
        msg.position = [left_position, right_position]
        self.encoder_publisher.publish(msg)

    def publish_odometry(self, x: float, y: float, yaw: float, v_lin: float, v_ang: float):
        """Publish robot odometry pose and twist."""
        msg = Odometry()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "odom"
        msg.child_frame_id = "base_link"

        msg.pose.pose.position.x = float(x)
        msg.pose.pose.position.y = float(y)
        msg.pose.pose.position.z = 0.0

        qz = math.sin(yaw / 2.0)
        qw = math.cos(yaw / 2.0)
        msg.pose.pose.orientation.z = qz
        msg.pose.pose.orientation.w = qw

        msg.twist.twist.linear.x = float(v_lin)
        msg.twist.twist.angular.z = float(v_ang)
        self.odom_publisher.publish(msg)

    def publish_bone_detection(self, distance: float, bearing: float, detected: bool):
        """Publish bone detection in robot frame."""
        msg = PointStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        msg.point.x = float(distance)
        msg.point.y = float(bearing)
        msg.point.z = 1.0 if detected else 0.0
        self.bone_publisher.publish(msg)


# =============================================================
# Webots Supervisor & Simulation Loop
# =============================================================

sounds_directory = Path(__file__).resolve().parents[2] / "sounds"

robot = Supervisor()
timestep = int(robot.getBasicTimeStep())

# Tastatur fuer interaktiven Reset (Taste 'R')
keyboard = robot.getKeyboard()
keyboard.enable(timestep)

# Motoren
left_motor = robot.getDevice("left wheel")
right_motor = robot.getDevice("right wheel")
left_motor.setPosition(float("inf"))
right_motor.setPosition(float("inf"))
left_motor.setVelocity(0.0)
right_motor.setVelocity(0.0)

# Encoder
left_encoder = robot.getDevice("left wheel sensor")
right_encoder = robot.getDevice("right wheel sensor")
left_encoder.enable(timestep)
right_encoder.enable(timestep)

# Lautsprecher
try:
    speaker = robot.getDevice("speaker")
except Exception:
    speaker = None

# Nodes fuer Knochen, Licht, Sichtkegel und Viewpoint
bone_node = robot.getFromDef("BONE")
light_node = robot.getFromDef("CELEBRATION_LIGHT")
vision_app_node = robot.getFromDef("VISION_CONE_APP")
viewpoint_node = robot.getFromDef("VIEWPOINT")
robot_self = robot.getSelf()


def center_camera():
    """Position camera elevated above start platform looking straight into the search area."""
    if viewpoint_node is not None:
        viewpoint_node.getField("position").setSFVec3f([-4.2, 0.0, 2.8])
        viewpoint_node.getField("orientation").setSFRotation([0.0, 1.0, 0.0, 0.40])
        fov_field = viewpoint_node.getField("fieldOfView")
        if fov_field is not None:
            fov_field.setSFFloat(0.95)


center_camera()


def place_bone_randomly():
    """Place bone randomly inside the 30-degree search sector."""
    if bone_node is not None:
        rand_r = random.uniform(2.0, 4.0)
        rand_theta = random.uniform(-math.radians(12.0), math.radians(12.0))
        bone_x = rand_r * math.cos(rand_theta)
        bone_y = rand_r * math.sin(rand_theta)
        bone_z = 0.025

        bone_node.getField("translation").setSFVec3f([bone_x, bone_y, bone_z])
        bone_node.resetPhysics()

        if light_node is not None:
            light_node.getField("location").setSFVec3f([bone_x, bone_y, 0.4])
            light_node.getField("intensity").setSFFloat(0.0)

        print(
            f"[WEBOTS-BRIDGE] 🦴 Knochen platziert: "
            f"x={bone_x:.2f} m, y={bone_y:.2f} m (Distanz: {rand_r:.2f} m, Winkel: {math.degrees(rand_theta):.1f}°)"
        )


# Initiale Platzierung
place_bone_randomly()

# -------------------------------------------------------------
# ROS Initialisierung
# -------------------------------------------------------------
rclpy.init()
node = WebotsBridge(sounds_directory)

prev_left_pos = left_encoder.getValue() if not math.isnan(left_encoder.getValue()) else 0.0
prev_right_pos = right_encoder.getValue() if not math.isnan(right_encoder.getValue()) else 0.0


def execute_simulation_reset():
    """Reset robot pose, stop audio, place bone at new position."""
    stop_audio()
    node.left_speed = 0.0
    node.right_speed = 0.0
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)

    # Roboter zurueck zum Startfeld (0, 0, 0.0975) mit 180 Grad Drehung (Blick zum Schiedsrichter)
    robot_self.getField("translation").setSFVec3f([0.0, 0.0, 0.0975])
    robot_self.getField("rotation").setSFRotation([0.0, 0.0, 1.0, 3.14159])
    robot_self.resetPhysics()

    # Knochen an neuer Position platzieren
    place_bone_randomly()

    # Sichtkegel zuruecksetzen auf Cyan
    if vision_app_node is not None:
        vision_app_node.getField("baseColor").setSFVec3f([0.0, 0.8, 1.0])
        vision_app_node.getField("emissiveColor").setSFVec3f([0.0, 0.25, 0.5])

    # Kamera auf Ausgangsposition zentrieren
    center_camera()

    # Zustaende zuruecksetzen
    node.effect_active = False
    node.bark_played = False
    node.last_detected_state = False

    # Reset-Bestaetigung an ROS senden
    node.reset_done_publisher.publish(Empty())
    node.get_logger().info("🔄 Simulation erfolgreich zurueckgesetzt!")
    node.reset_requested = False


try:
    while robot.step(timestep) != -1:
        # Tastatur-Reset pruefen (Taste 'R' in Webots)
        key = keyboard.getKey()
        if key in (ord('R'), ord('r')):
            node.reset_requested = True

        # Reset ausfuehren, falls angefordert
        if node.reset_requested:
            execute_simulation_reset()

        # ROS-Nachrichten abarbeiten
        rclpy.spin_once(node, timeout_sec=0)
        node.update_watchdog()

        # Motoren ansteuern
        left_motor.setVelocity(node.left_speed)
        right_motor.setVelocity(node.right_speed)

        # Encoder lesen
        left_pos = left_encoder.getValue()
        right_pos = right_encoder.getValue()
        if math.isnan(left_pos):
            left_pos = 0.0
        if math.isnan(right_pos):
            right_pos = 0.0

        node.publish_encoders(left_pos, right_pos)

        # Pose des Roboters (aus Supervisor Ground Truth fuer praezise Odometrie)
        robot_pos = robot_self.getPosition()
        rot_mat = robot_self.getOrientation()
        rx, ry = robot_pos[0], robot_pos[1]
        robot_yaw = math.atan2(rot_mat[3], rot_mat[0])

        # Geschwindigkeit
        v_lin = (node.left_speed + node.right_speed) / 2.0 * WHEEL_RADIUS
        v_ang = (node.right_speed - node.left_speed) / WHEEL_BASE * WHEEL_RADIUS
        node.publish_odometry(rx, ry, robot_yaw, v_lin, v_ang)

        # ---------------------------------------------------------
        # Sichtkegel-Berechnung zum Knochen
        # ---------------------------------------------------------
        if bone_node is not None:
            bone_cur_pos = bone_node.getPosition()
            bx, by = bone_cur_pos[0], bone_cur_pos[1]

            dx = bx - rx
            dy = by - ry
            dist_to_bone = math.hypot(dx, dy)
            world_bearing = math.atan2(dy, dx)
            rel_bearing = normalize_angle(world_bearing - robot_yaw)

            # Pruefen, ob Knochen im Sichtkegel liegt (Reichweite & Winkel)
            in_cone = (dist_to_bone <= CONE_RANGE) and (abs(rel_bearing) <= CONE_HALF_ANGLE)

            node.publish_bone_detection(dist_to_bone, rel_bearing, in_cone)

            # Visueller Sichtkegel: Farbe dynamisch anpassen
            if vision_app_node is not None and in_cone != node.last_detected_state:
                node.last_detected_state = in_cone
                if in_cone:
                    # Gold-gelber Erfolgs-Look bei Erkennung
                    vision_app_node.getField("baseColor").setSFVec3f([1.0, 0.85, 0.0])
                    vision_app_node.getField("emissiveColor").setSFVec3f([0.7, 0.5, 0.0])
                else:
                    # Cyan-Blau beim Scannen
                    vision_app_node.getField("baseColor").setSFVec3f([0.0, 0.8, 1.0])
                    vision_app_node.getField("emissiveColor").setSFVec3f([0.0, 0.25, 0.5])

        # ---------------------------------------------------------
        # Spezialeffekt (Licht)
        # ---------------------------------------------------------
        if light_node is not None:
            if node.effect_active:
                pulse = 5.0 + 3.0 * math.sin(time.monotonic() * 10.0)
                light_node.getField("intensity").setSFFloat(pulse)
            else:
                light_node.getField("intensity").setSFFloat(0.0)

finally:
    stop_audio()
    left_motor.setVelocity(0.0)
    right_motor.setVelocity(0.0)
    node.destroy_node()
    rclpy.shutdown()