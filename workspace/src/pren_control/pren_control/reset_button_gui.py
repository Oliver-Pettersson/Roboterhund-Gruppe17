"""Kompakte grafische Status- und Reset-Konsole fuer die PREN-Simulation."""

import threading
import tkinter as tk
from tkinter import ttk

import rclpy
from rclpy.node import Node
from std_msgs.msg import Empty, String
from nav_msgs.msg import Odometry
from geometry_msgs.msg import PointStamped


class ResetGuiNode(Node):
    """ROS 2 Node fuer GUI-Interaktion."""

    def __init__(self, update_callback):
        super().__init__("pren_reset_gui")
        self.update_callback = update_callback

        self.reset_pub = self.create_publisher(Empty, "/pren/reset", 10)

        self.create_subscription(String, "/pren/search_status", self.status_cb, 10)
        self.create_subscription(Odometry, "/odom", self.odom_cb, 10)
        self.create_subscription(PointStamped, "/pren/bone_detection", self.bone_cb, 10)
        self.create_subscription(String, "/pren/command", self.cmd_cb, 10)

        self.latest_status = "Warten auf Sprach-/Gestenbefehl"
        self.latest_pos = "x=0.00 m, y=0.00 m"
        self.latest_bone = "Nicht im Sichtfeld"
        self.latest_cmd = "Noch kein Befehl empfangen"

    def status_cb(self, msg: String):
        self.latest_status = msg.data
        self.update_callback()

    def odom_cb(self, msg: Odometry):
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        self.latest_pos = f"x={x:.2f} m, y={y:.2f} m"
        self.update_callback()

    def bone_cb(self, msg: PointStamped):
        if msg.point.z > 0.5:
            self.latest_bone = f"🎯 Erfasst ({msg.point.x:.2f} m, {msg.point.y * 57.3:.1f}°)"
        else:
            self.latest_bone = "Suche läuft / Nicht im Sichtfeld"
        self.update_callback()

    def cmd_cb(self, msg: String):
        self.latest_cmd = msg.data
        self.update_callback()

    def send_reset(self):
        self.get_logger().info("GUI: Reset-Befehl gesendet.")
        self.reset_pub.publish(Empty())


class ResetApp:
    def __init__(self, root, node: ResetGuiNode):
        self.root = root
        self.node = node

        self.root.title("PREN Simulator Control")
        self.root.geometry("380x240")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        # Style
        style = ttk.Style()
        style.theme_use("clam")

        main_frame = ttk.Frame(root, padding=14)
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_lbl = ttk.Label(
            main_frame,
            text="PREN Simulation Control Panel",
            font=("Segoe UI", 12, "bold"),
        )
        title_lbl.pack(pady=(0, 10))

        # Grosser Reset-Button
        reset_btn = tk.Button(
            main_frame,
            text="🔄  Setup Neustarten / Reset",
            font=("Segoe UI", 11, "bold"),
            bg="#1b5e20",
            fg="white",
            activebackground="#2e7d32",
            activeforeground="white",
            relief=tk.RAISED,
            cursor="hand2",
            command=self.on_reset_clicked,
            padx=10,
            pady=10,
        )
        reset_btn.pack(fill=tk.X, pady=(0, 12))

        # Live-Statusanzeige
        info_group = ttk.LabelFrame(main_frame, text="Live-Status", padding=10)
        info_group.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value="Phase: Warten auf Sprach-/Gestenbefehl")
        self.pos_var = tk.StringVar(value="Position: x=0.00 m, y=0.00 m")
        self.bone_var = tk.StringVar(value="Sichtkegel: Nicht im Sichtfeld")
        self.cmd_var = tk.StringVar(value="Letzter Befehl: Noch kein Befehl empfangen")

        ttk.Label(info_group, textvariable=self.status_var, font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=1)
        ttk.Label(info_group, textvariable=self.pos_var, font=("Segoe UI", 9)).pack(anchor=tk.W, pady=1)
        ttk.Label(info_group, textvariable=self.bone_var, font=("Segoe UI", 9)).pack(anchor=tk.W, pady=1)
        ttk.Label(info_group, textvariable=self.cmd_var, font=("Segoe UI", 9, "italic")).pack(anchor=tk.W, pady=1)

    def on_reset_clicked(self):
        self.node.send_reset()
        self.status_var.set("Phase: Zurücksetzen...")

    def update_ui(self):
        self.status_var.set(f"Phase: {self.node.latest_status}")
        self.pos_var.set(f"Position: {self.node.latest_pos}")
        self.bone_var.set(f"Sichtkegel: {self.node.latest_bone}")
        self.cmd_var.set(f"Letzter Befehl: «{self.node.latest_cmd}»")


def main(args=None):
    rclpy.init(args=args)

    root = tk.Tk()
    app = None

    def on_update():
        if app is not None:
            root.after(0, app.update_ui)

    node = ResetGuiNode(on_update)
    app = ResetApp(root, node)

    # ROS Spin in separatem Thread
    spin_thread = threading.Thread(target=lambda: rclpy.spin(node), daemon=True)
    spin_thread.start()

    try:
        root.mainloop()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
