"""Einfache Datentypen und Hilfsfunktionen fuer Pose und Fahrbefehle in der Ebene."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Pose2D:
    """Position und Ausrichtung des Roboters im Odometrie-Rahmen."""

    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0

    def distance_to(self, other: 'Pose2D') -> float:
        """Euklidische Distanz zu einer anderen Pose in Metern."""
        return math.hypot(other.x - self.x, other.y - self.y)

    def heading_to(self, other: 'Pose2D') -> float:
        """Richtung (Gierwinkel) von dieser Pose zur anderen Pose."""
        return math.atan2(other.y - self.y, other.x - self.x)


@dataclass(frozen=True)
class Velocity:
    """Fahrbefehl: vorwaerts in m/s, Drehung in rad/s (positiv = links)."""

    linear: float = 0.0
    angular: float = 0.0


STOP = Velocity()


@dataclass(frozen=True)
class BoneObservation:
    """Was die Knochenerkennung gerade sieht (relativ zum Roboter)."""

    detected: bool = False
    distance_m: float = 0.0
    bearing_rad: float = 0.0


NO_BONE = BoneObservation()


def normalize_angle(angle: float) -> float:
    """Bringt einen Winkel in den Bereich [-pi, pi]."""
    return math.atan2(math.sin(angle), math.cos(angle))


def clamp(value: float, limit: float) -> float:
    """Begrenzt einen Wert symmetrisch auf [-limit, limit]."""
    return max(-limit, min(limit, value))


def turn_towards(current_yaw: float, target_yaw: float, gain: float, max_rate: float) -> float:
    """P-Regler fuer die Drehrate, um von current_yaw nach target_yaw zu drehen."""
    return clamp(gain * normalize_angle(target_yaw - current_yaw), max_rate)
