"""PREN Such-Treiber: Autonome Suche des Knochens im 30-Grad-Sektor, Feier und Rueckkehr.

Integriert mit Voice- und Gesture-Recognition ueber ROS 2 Topic (/pren/command) und UDP (127.0.0.1:9876).
Startet im Startfeld um 180 Grad abgewandt vom Suchfeld. Reagiert auf 'Such', fuehrt die Suche
vollstaendig durch (ohne Unterbrechung durch andere Befehle) und kehrt anschliessend autonom zurueck.
"""

from enum import Enum
import json
import math
import socket
import threading
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, PointStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool, Empty, String


def normalize_angle(angle: float) -> float:
    """Normalize angle to [-pi, pi]."""
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


class SearchState(Enum):
    IDLE = "Warten auf Befehl (Startfeld, 180°)"
    TURN_TO_SEARCH = "180°-Drehung zum Suchbereich"
    SECTOR_SWEEP = "Suchbereich scannen (30°-Sektor Sweep)"
    APPROACH_BONE = "Knochen im Sichtkegel: Anfahrt auf Ziel"
    CELEBRATE = "Knochen erreicht: Signal & Spezialeffekt"
    RETURN_HOME = "Autonome Rueckfahrt zum Startfeld (0, 0)"
    MISSION_COMPLETE = "Zurueck im Startfeld: Mission beendet (180°)"


class SuchDriver(Node):
    """FSM-basierter Suchknoten fuer den PREN Roboterhund mit 2x Speed, 180°-Initialdrehung & UDP-Bridge."""

    def __init__(self):
        super().__init__("such_driver")

        # Parameter (2x Speed: 0.36 m/s Suche, 0.44 m/s Rueckkehr)
        self.declare_parameter("auto_start", False)
        self.declare_parameter("search_speed", 0.36)
        self.declare_parameter("sweep_angle_deg", 18.0)
        self.declare_parameter("sweep_period_sec", 3.0)
        self.declare_parameter("contact_distance", 0.32)
        self.declare_parameter("return_speed", 0.44)

        self.auto_start = self.get_parameter("auto_start").value
        self.search_speed = float(self.get_parameter("search_speed").value)
        self.sweep_amp_rad = math.radians(float(self.get_parameter("sweep_angle_deg").value))
        self.sweep_period = float(self.get_parameter("sweep_period_sec").value)
        self.contact_distance = float(self.get_parameter("contact_distance").value)
        self.return_speed = float(self.get_parameter("return_speed").value)

        # Roboter Zustand (startet standardmaessig in IDLE)
        self.state = SearchState.TURN_TO_SEARCH if self.auto_start else SearchState.IDLE
        self.start_time = time.monotonic()
        self.state_enter_time = time.monotonic()
        self.mission_finished = False

        self.robot_x = 0.0
        self.robot_y = 0.0
        self.robot_yaw = math.pi  # Roboter startet um 180 Grad weggedreht
        self.has_odom = False

        # Knochen-Detektion
        self.bone_detected = False
        self.bone_dist = 999.0
        self.bone_bearing = 0.0

        # Letzter Befehl und State-Broadcasting (fuer zentralisierten Zustand aller 3 Apps)
        self.last_command = "KEIN"
        self.state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.state_targets = [("127.0.0.1", 9878), ("127.0.0.1", 9879)]

        # ROS Schnittstellen
        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.effect_pub = self.create_publisher(Bool, "/pren/trigger_effect", 10)
        self.final_signal_pub = self.create_publisher(Bool, "/pren/final_signal", 10)
        self.status_pub = self.create_publisher(String, "/pren/search_status", 10)
        self.command_pub = self.create_publisher(String, "/pren/command", 10)
        self.state_pub = self.create_publisher(String, "/pren/robot_state", 10)

        self.create_subscription(Odometry, "/odom", self.odom_callback, 10)
        self.create_subscription(PointStamped, "/pren/bone_detection", self.bone_callback, 10)
        self.create_subscription(Empty, "/pren/reset", self.reset_callback, 10)
        self.create_subscription(Empty, "/pren/reset_done", self.reset_callback, 10)
        self.create_subscription(String, "/pren/command", self.command_callback, 10)

        # UDP Bridge Server (empfaengt Voice- & Gesture-Befehle von externen Prozessen auf Port 9876)
        self._start_udp_listener()

        # Regelkreis Timer (20 Hz)
        self.timer = self.create_timer(0.05, self.control_loop)

        self.get_logger().info("=============================================================")
        self.get_logger().info(" PREN Such-Treiber initialisiert (Geschwindigkeit 2x: 0.36 m/s)")
        self.get_logger().info(" Startposition: 180° abgewandt vom Suchfeld (Blick zum Schiri)")
        self.get_logger().info(" Wartet auf Befehle ('Such', 'Sitz', 'Platz', 'Auf', 'Hier')")
        self.get_logger().info(" UDP-Listener auf 127.0.0.1:9876 fuer Voice- & Gestensteuerung aktiv")
        self.get_logger().info("=============================================================")

    def _start_udp_listener(self):
        """Hintergrundthread fuer UDP-Befehle von Voice- und Gestenerkennung."""
        def udp_worker():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", 9876))
                self.get_logger().info("✅ [UDP 9876] Empfaenger erfolgreich an 127.0.0.1:9876 gebunden.")
            except Exception as exc:
                self.get_logger().error(f"❌ [UDP 9876] Fehler beim Binden von Port 9876: {exc}")
                return

            while rclpy.ok():
                try:
                    data, _ = sock.recvfrom(1024)
                    if not data:
                        continue
                    cmd_str = data.decode("utf-8", errors="ignore").strip().upper()
                    if cmd_str:
                        self.get_logger().info(f"📡 [UDP EMPFANGEN] '{cmd_str}'")
                        # Befehl auch auf ROS-Topic spiegeln
                        ros_cmd = String()
                        ros_cmd.data = cmd_str
                        self.command_pub.publish(ros_cmd)
                        # Direkt verarbeiten
                        self.handle_command(cmd_str)
                except Exception:
                    if not rclpy.ok():
                        break
                    time.sleep(0.05)
            sock.close()

        thread = threading.Thread(target=udp_worker, daemon=True)
        thread.start()

    def odom_callback(self, msg: Odometry):
        self.robot_x = msg.pose.pose.position.x
        self.robot_y = msg.pose.pose.position.y

        # Quaternion to Yaw
        qz = msg.pose.pose.orientation.z
        qw = msg.pose.pose.orientation.w
        self.robot_yaw = 2.0 * math.atan2(qz, qw)
        self.has_odom = True

    def bone_callback(self, msg: PointStamped):
        self.bone_dist = msg.point.x
        self.bone_bearing = msg.point.y
        self.bone_detected = (msg.point.z > 0.5)

    def command_callback(self, msg: String):
        """Unified command handler via ROS topic."""
        self.handle_command(msg.data)

    def handle_command(self, cmd_raw: str):
        """Zentrale Auswertung aller Sprach-, Gesten- und GUI-Befehle."""
        cmd_str = cmd_raw.strip().upper()
        self.last_command = cmd_str
        self.get_logger().info(f"[KOMMANDO] '{cmd_str}' empfangen (Status: {self.state.name})")

        # -------------------------------------------------------------
        # SUCH-SPERRE: Waehrend die Suche laeuft, werden saemtliche Befehle ignoriert!
        # "When the 'Such' Befehl by VoiceRecognition is given the robot will complete
        #  this command before reacting to anything else."
        # -------------------------------------------------------------
        search_active_states = (
            SearchState.TURN_TO_SEARCH,
            SearchState.SECTOR_SWEEP,
            SearchState.APPROACH_BONE,
            SearchState.CELEBRATE,
            SearchState.RETURN_HOME,
        )

        if self.state in search_active_states:
            self.get_logger().warn(
                f"🔒 [SUCHE AKTIV] Befehl '{cmd_str}' wird ignoriert! "
                f"Roboter beendet zuerst die Suchmission ({self.state.value})."
            )
            return

        # -------------------------------------------------------------
        # Befehle im IDLE- oder MISSION_COMPLETE-Zustand verarbeiten:
        # -------------------------------------------------------------
        if cmd_str in ("SUCH", "START"):
            self.get_logger().info("📢 «SUCH» erhalten! Starte Suchmission: Roboter dreht sich um 180°...")
            self.start_time = time.monotonic()
            self.mission_finished = False
            self.transition_to(SearchState.TURN_TO_SEARCH)

        elif cmd_str == "SITZ":
            self.get_logger().info("🐕 Befehl «SITZ»: Roboter nimmt Sitz-Haltung ein.")
            self._publish_status_feedback("SITZ: Roboter sitzt")

        elif cmd_str == "PLATZ":
            self.get_logger().info("🐕 Befehl «PLATZ»: Roboter legt sich ab.")
            self._publish_status_feedback("PLATZ: Roboter liegt")

        elif cmd_str == "AUF":
            self.get_logger().info("🐕 Befehl «AUF»: Roboter steht auf und ist sprungbereit.")
            self._publish_status_feedback("AUF: Roboter steht bereit")

        elif cmd_str == "HIER":
            self.get_logger().info("🐕 Befehl «HIER»: Roboter richtet Aufmerksamkeit auf Schiedsrichter.")
            self._publish_status_feedback("HIER: Roboter aufmerksam")

        elif cmd_str == "STOP":
            self.get_logger().info("⏹️ Roboter gestoppt.")
            self.transition_to(SearchState.IDLE)
            self.cmd_pub.publish(Twist())

    def _publish_status_feedback(self, text: str):
        msg = String()
        msg.data = text
        self.status_pub.publish(msg)

    def reset_callback(self, msg: Empty):
        """Reset internal search state machine back to start (IDLE)."""
        self.get_logger().info("=============================================================")
        self.get_logger().info(" 🔄 [SUCH-DRIVER] Reset empfangen: Zurueck in Ausgangslage!")
        self.get_logger().info("=============================================================")

        # Spezialeffekt sofort ausschalten
        eff_msg = Bool()
        eff_msg.data = False
        self.effect_pub.publish(eff_msg)

        # Variablen zuruecksetzen
        self.last_command = "RESET"
        self.bone_detected = False
        self.bone_dist = 999.0
        self.bone_bearing = 0.0
        self.mission_finished = False
        self.start_time = time.monotonic()

        # Stop-Befehl senden
        stop_cmd = Twist()
        self.cmd_pub.publish(stop_cmd)

        # Zustand zuruecksetzen (Warten auf Befehl)
        self.transition_to(SearchState.TURN_TO_SEARCH if self.auto_start else SearchState.IDLE)

    def broadcast_robot_state(self):
        """Zentralen Roboter-Zustand per UDP (Port 9878 Voice, 9879 Gesten) und ROS broadcasten."""
        is_busy = self.state in (
            SearchState.TURN_TO_SEARCH,
            SearchState.SECTOR_SWEEP,
            SearchState.APPROACH_BONE,
            SearchState.CELEBRATE,
            SearchState.RETURN_HOME,
        )
        state_dict = {
            "state": self.state.name,
            "label": self.state.value,
            "busy": is_busy,
            "robot_x": round(self.robot_x, 2),
            "robot_y": round(self.robot_y, 2),
            "robot_yaw": round(self.robot_yaw, 3),
            "bone_detected": bool(self.bone_detected),
            "last_command": self.last_command,
            "timestamp": time.time(),
        }
        raw_json = json.dumps(state_dict)
        payload = raw_json.encode("utf-8")

        for target in self.state_targets:
            try:
                self.state_sock.sendto(payload, target)
            except Exception:
                pass

        ros_state = String()
        ros_state.data = raw_json
        self.state_pub.publish(ros_state)

    def transition_to(self, new_state: SearchState):
        old_state = self.state
        self.state = new_state
        self.state_enter_time = time.monotonic()
        self.get_logger().info(f"[FSM] {old_state.name} -> {new_state.name}")

        # Statusmeldung veroeffentlichen
        status_msg = String()
        status_msg.data = new_state.value
        self.status_pub.publish(status_msg)

        # Zustandsuebergangs-Aktionen:
        # 1. Eintritt in CELEBRATE -> Effekt GENAU EINMAL aktivieren
        if new_state == SearchState.CELEBRATE:
            eff_msg = Bool()
            eff_msg.data = True
            self.effect_pub.publish(eff_msg)

        # 2. Verlassen von CELEBRATE -> Effekt GENAU EINMAL ausschalten
        elif old_state == SearchState.CELEBRATE:
            eff_msg = Bool()
            eff_msg.data = False
            self.effect_pub.publish(eff_msg)

        # State sofort an alle 3 Anwendungen broadcasten
        self.broadcast_robot_state()

    def control_loop(self):
        if not self.has_odom:
            return

        self.broadcast_robot_state()
        cmd = Twist()
        now = time.monotonic()

        # ---------------------------------------------------------
        # FSM: IDLE
        # ---------------------------------------------------------
        if self.state == SearchState.IDLE:
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0

        # ---------------------------------------------------------
        # FSM: TURN_TO_SEARCH (180°-Drehung zum Suchbereich)
        # ---------------------------------------------------------
        elif self.state == SearchState.TURN_TO_SEARCH:
            # Roboter startete bei yaw ~ pi (Blick nach -X zum Schiri).
            # Ziel: yaw = 0.0 (Blick nach +X in den 30°-Suchsektor).
            yaw_error = normalize_angle(0.0 - self.robot_yaw)
            if abs(yaw_error) < math.radians(5.0):
                cmd.linear.x = 0.0
                cmd.angular.z = 0.0
                self.get_logger().info("✅ 180°-Drehung vollendet! Starte Such-Scan im 30°-Sektor...")
                self.transition_to(SearchState.SECTOR_SWEEP)
                return

            cmd.linear.x = 0.0
            cmd.angular.z = max(-2.0, min(2.0, 2.5 * yaw_error))

        # ---------------------------------------------------------
        # FSM: SECTOR_SWEEP (Systematisches Absuchen des 30°-Sektors, 2x Speed)
        # ---------------------------------------------------------
        elif self.state == SearchState.SECTOR_SWEEP:
            # Pruefen, ob Knochen im Sichtkegel aufgetaucht ist
            if self.bone_detected and self.bone_dist > 0.0:
                self.get_logger().info(
                    f"🎯 KNOCHEN IM SICHTKEGEL ERKANNT! "
                    f"Distanz: {self.bone_dist:.2f} m, Relativwinkel: {math.degrees(self.bone_bearing):.1f}°"
                )
                self.transition_to(SearchState.APPROACH_BONE)
                return

            # Vorwaertsbewegung mit sinusfoermigem Suchpendeln im 30°-Sektor
            t = now - self.state_enter_time
            target_yaw = self.sweep_amp_rad * math.sin(2.0 * math.pi * t / self.sweep_period)
            yaw_error = normalize_angle(target_yaw - self.robot_yaw)

            cmd.linear.x = self.search_speed
            cmd.angular.z = max(-2.0, min(2.0, 3.0 * yaw_error))

            # Falls der Roboter das Ende des 5m-Felds erreicht ohne Fund, umkehren
            if self.robot_x > 4.6:
                cmd.linear.x = 0.0
                cmd.angular.z = 1.5

        # ---------------------------------------------------------
        # FSM: APPROACH_BONE (Gezielte Anfahrt auf den Knochen, 2x Speed)
        # ---------------------------------------------------------
        elif self.state == SearchState.APPROACH_BONE:
            if self.bone_detected:
                # Knochen anvisieren
                bearing_err = self.bone_bearing
                cmd.angular.z = max(-2.0, min(2.0, 3.5 * bearing_err))

                # Geschwindigkeit drosseln, je naeher der Roboter kommt
                dist_err = self.bone_dist - self.contact_distance
                if dist_err > 0.1:
                    cmd.linear.x = max(0.12, min(self.search_speed, 0.4 * dist_err + 0.12))
                else:
                    cmd.linear.x = 0.10

                # Knochen erreicht (Beruehrungsabstand)
                if self.bone_dist <= self.contact_distance:
                    self.get_logger().info(
                        f"🦴 KNOCHEN ERREICHT! (Abstand: {self.bone_dist:.2f} m)"
                    )
                    self.transition_to(SearchState.CELEBRATE)
                    return
            else:
                # Knochen kurzzeitig ausser Sicht: vorsichtig mit reduzierter Geschwindigkeit weiter
                cmd.linear.x = 0.12
                cmd.angular.z = 0.0

        # ---------------------------------------------------------
        # FSM: CELEBRATION (Stopp, Bellen & Lichteffekt)
        # ---------------------------------------------------------
        elif self.state == SearchState.CELEBRATE:
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0

            # 2.2 Sekunden Feier (Bellen erfolgt genau einmal bei Zustandseintritt)
            if now - self.state_enter_time > 2.2:
                self.get_logger().info("Fund gemeldet. Beginne autonome Rueckfahrt zum Startfeld...")
                self.transition_to(SearchState.RETURN_HOME)
                return

        # ---------------------------------------------------------
        # FSM: RETURN_HOME (Autonome Rueckkehr zu (0, 0), 2x Speed)
        # ---------------------------------------------------------
        elif self.state == SearchState.RETURN_HOME:
            dx = 0.0 - self.robot_x
            dy = 0.0 - self.robot_y
            dist_home = math.hypot(dx, dy)

            # Im Startfeld angekommen (< 15 cm vom Ursprung)
            if dist_home <= 0.15:
                # Wieder 180 Grad Drehung zum Schiedsrichter (yaw ~ pi)
                referee_yaw = math.pi
                ref_err = normalize_angle(referee_yaw - self.robot_yaw)
                if abs(ref_err) < math.radians(10.0):
                    cmd.linear.x = 0.0
                    cmd.angular.z = 0.0
                    self.transition_to(SearchState.MISSION_COMPLETE)
                    return
                else:
                    cmd.linear.x = 0.0
                    cmd.angular.z = max(-1.8, min(1.8, 2.5 * ref_err))
            else:
                target_yaw_home = math.atan2(dy, dx)
                yaw_err_home = normalize_angle(target_yaw_home - self.robot_yaw)

                # Zuerst auf Startpunkt eindrehen
                if abs(yaw_err_home) > math.radians(25.0):
                    cmd.linear.x = 0.0
                    cmd.angular.z = max(-2.0, min(2.0, 3.0 * yaw_err_home))
                else:
                    # Vorwaerts fahren mit Rueckkehrgeschwindigkeit (0.44 m/s)
                    speed = max(0.12, min(self.return_speed, 0.5 * dist_home + 0.10))
                    cmd.linear.x = speed
                    cmd.angular.z = max(-1.5, min(1.5, 2.5 * yaw_err_home))

        # ---------------------------------------------------------
        # FSM: MISSION_COMPLETE (Endquittung & Stopp im Startfeld)
        # ---------------------------------------------------------
        elif self.state == SearchState.MISSION_COMPLETE:
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0

            if not self.mission_finished:
                self.mission_finished = True
                fin_msg = Bool()
                fin_msg.data = True
                self.final_signal_pub.publish(fin_msg)

                elapsed = now - self.start_time
                self.get_logger().info("=============================================================")
                self.get_logger().info(" 🏁 PREN SUCHE ERFOLGREICH ABGESCHLOSSEN!")
                self.get_logger().info(f" Gesamtzeit: {elapsed:.1f} s")
                self.get_logger().info(" Roboter steht im Startfeld mit Blick zum Schiedsrichter.")
                self.get_logger().info(" Such-Sperre aufgehoben. Bereit fuer naechste Sprach-/Gesten-Befehle.")
                self.get_logger().info("=============================================================")

            # Nach 1.5 Sekunden automatisch zurueck in IDLE wechseln:
            # Damit kann der "Such"-Befehl sofort erneut gegeben werden!
            if now - self.state_enter_time > 1.5:
                self.get_logger().info("🔄 Auto-Reset: Roboter ist nun wieder im Zustand IDLE (bereit fuer 'Such').")
                self.transition_to(SearchState.IDLE)

        self.cmd_pub.publish(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = SuchDriver()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        stop_cmd = Twist()
        node.cmd_pub.publish(stop_cmd)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
