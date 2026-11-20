"""Minimale Welt fuer Tests: Roboter mit Differentialantrieb und Knochen mit Sichtkegel."""

from dataclasses import dataclass, field
import math
import random

from pren_behavior.motion import BoneObservation, normalize_angle, Pose2D, Velocity

# Wie in der Webots-Simulation: Start im Ursprung mit Blick zum Schiedsrichter (180 Grad).
START_POSE = Pose2D(0.0, 0.0, math.pi)


@dataclass
class SimulatedWorld:
    """Integriert Fahrbefehle und liefert, was eine Kamera vom Knochen sehen wuerde."""

    pose: Pose2D = START_POSE
    bone_x: float = 3.0
    bone_y: float = 0.3
    view_range_m: float = 3.0
    view_half_angle_rad: float = math.radians(22.5)
    # Messfehler der Kamera: Rauschen auf Winkel und Distanz, Anteil verpasster Bilder
    bearing_noise_rad: float = 0.0
    distance_noise_m: float = 0.0
    dropout_probability: float = 0.0
    rng: random.Random = field(default_factory=lambda: random.Random(0))

    def drive(self, velocity: Velocity, dt: float) -> None:
        """Bewegt den Roboter fuer dt Sekunden mit dem Fahrbefehl."""
        yaw = self.pose.yaw + velocity.angular * dt
        self.pose = Pose2D(
            x=self.pose.x + velocity.linear * math.cos(yaw) * dt,
            y=self.pose.y + velocity.linear * math.sin(yaw) * dt,
            yaw=normalize_angle(yaw),
        )

    def observe_bone(self) -> BoneObservation:
        """Knochen relativ zum Roboter, falls er im Sichtkegel liegt."""
        distance = math.hypot(self.bone_x - self.pose.x, self.bone_y - self.pose.y)
        bearing = normalize_angle(
            math.atan2(self.bone_y - self.pose.y, self.bone_x - self.pose.x) - self.pose.yaw)
        visible = distance <= self.view_range_m and abs(bearing) <= self.view_half_angle_rad
        if not visible or self.rng.random() < self.dropout_probability:
            return BoneObservation()
        return BoneObservation(
            detected=True,
            distance_m=max(0.0, distance + self.rng.gauss(0.0, self.distance_noise_m)),
            bearing_rad=bearing + self.rng.gauss(0.0, self.bearing_noise_rad),
        )
