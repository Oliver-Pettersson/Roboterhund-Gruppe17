"""
Rechnet eine Knochen-Box im Bild in Distanz und Winkel relativ zum Roboter um.

Annahmen (Lochkamera, ebener Boden):
    * Die Kamera ist in mounting_height_m ueber dem Boden montiert und um tilt_down_rad
      nach unten geneigt.
    * Der untere Rand der Box liegt auf dem Boden.
Winkel: positiv = links vom Roboter (wie BoneDetection.bearing_rad).
"""

from dataclasses import dataclass
import math
from typing import Optional


@dataclass(frozen=True)
class BoundingBox:
    """Achsenparallele Box in Pixeln (x, y = obere linke Ecke)."""

    x: float
    y: float
    width: float
    height: float
    confidence: float

    @property
    def bottom_center(self) -> tuple:
        """Mittelpunkt der Unterkante, dort beruehrt der Knochen den Boden."""
        return self.x + self.width / 2.0, self.y + self.height


@dataclass(frozen=True)
class CameraGeometry:
    """Bildgroesse, Oeffnungswinkel und Montage der Kamera."""

    image_width: int = 640
    image_height: int = 480
    horizontal_fov_rad: float = math.radians(66.0)   # Pi Camera Module 3 (Standard)
    vertical_fov_rad: float = math.radians(41.0)
    mounting_height_m: float = 0.25
    tilt_down_rad: float = math.radians(10.0)

    @property
    def focal_x(self) -> float:
        """Brennweite in Pixeln (horizontal)."""
        return (self.image_width / 2.0) / math.tan(self.horizontal_fov_rad / 2.0)

    @property
    def focal_y(self) -> float:
        """Brennweite in Pixeln (vertikal)."""
        return (self.image_height / 2.0) / math.tan(self.vertical_fov_rad / 2.0)


@dataclass(frozen=True)
class BoneLocation:
    """Lage des Knochens relativ zum Roboter."""

    distance_m: float
    bearing_rad: float


def locate_bone(box: BoundingBox, camera: CameraGeometry) -> Optional[BoneLocation]:
    """Distanz und Winkel zum Knochen oder None, wenn er nicht unter dem Horizont liegt."""
    u, v = box.bottom_center
    bearing = -math.atan((u - camera.image_width / 2.0) / camera.focal_x)
    angle_below_horizon = camera.tilt_down_rad + math.atan(
        (v - camera.image_height / 2.0) / camera.focal_y)
    if angle_below_horizon <= 0.0:
        return None
    ground_distance = camera.mounting_height_m / math.tan(angle_below_horizon)
    return BoneLocation(distance_m=ground_distance / math.cos(bearing), bearing_rad=bearing)
