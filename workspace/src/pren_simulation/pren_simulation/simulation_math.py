"""Reine Rechenfunktionen der Simulation: Antrieb, Sichtkegel und Knochenplatzierung."""

from dataclasses import dataclass
import math
import random


@dataclass(frozen=True)
class DifferentialDrive:
    """Geometrie des Pioneer 3-DX in der Webots-Welt."""

    wheel_radius_m: float = 0.0975
    wheel_base_m: float = 0.33
    max_wheel_speed: float = 12.3   # rad/s

    def wheel_speeds(self, linear: float, angular: float) -> tuple:
        """Rechnet Fahrbefehl (m/s, rad/s) in begrenzte Raddrehzahlen (links, rechts) um."""
        half_base = self.wheel_base_m / 2.0
        left = (linear - angular * half_base) / self.wheel_radius_m
        right = (linear + angular * half_base) / self.wheel_radius_m
        return self._limit(left), self._limit(right)

    def body_velocity(self, left: float, right: float) -> tuple:
        """Rechnet Raddrehzahlen in Fahrgeschwindigkeit (m/s) und Drehrate (rad/s) um."""
        linear = (left + right) / 2.0 * self.wheel_radius_m
        angular = (right - left) / self.wheel_base_m * self.wheel_radius_m
        return linear, angular

    def _limit(self, speed: float) -> float:
        return max(-self.max_wheel_speed, min(self.max_wheel_speed, speed))


@dataclass(frozen=True)
class VisionCone:
    """Vereinfachte Kamera: sieht alles innerhalb von Reichweite und Oeffnungswinkel."""

    range_m: float = 3.0
    half_angle_rad: float = math.radians(22.5)

    def observe(self, robot_x: float, robot_y: float, robot_yaw: float,
                target_x: float, target_y: float) -> tuple:
        """Gibt (sichtbar, Distanz, Winkel relativ zur Blickrichtung) zurueck."""
        distance = math.hypot(target_x - robot_x, target_y - robot_y)
        bearing = math.atan2(target_y - robot_y, target_x - robot_x) - robot_yaw
        bearing = math.atan2(math.sin(bearing), math.cos(bearing))
        visible = distance <= self.range_m and abs(bearing) <= self.half_angle_rad
        return visible, distance, bearing


def random_bone_position(rng: random.Random,
                         min_distance_m: float = 2.0,
                         max_distance_m: float = 4.0,
                         half_angle_rad: float = math.radians(12.0)) -> tuple:
    """Zufaellige Knochenposition (x, y) im Suchsektor vor dem Startfeld."""
    distance = rng.uniform(min_distance_m, max_distance_m)
    angle = rng.uniform(-half_angle_rad, half_angle_rad)
    return distance * math.cos(angle), distance * math.sin(angle)


def yaw_from_rotation_matrix(matrix: list) -> float:
    """Gierwinkel aus der 3x3-Rotationsmatrix, die Webots als flache Liste liefert."""
    return math.atan2(matrix[3], matrix[0])
