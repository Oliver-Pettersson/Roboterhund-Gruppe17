"""Tests fuer die Umrechnung Knochen-Box -> Distanz und Winkel."""

import math

from pren_perception.bone.bone_localizer import BoundingBox, CameraGeometry, locate_bone
import pytest

CAMERA = CameraGeometry(image_width=640, image_height=480,
                        horizontal_fov_rad=math.radians(66.0),
                        vertical_fov_rad=math.radians(41.0),
                        mounting_height_m=0.25, tilt_down_rad=math.radians(10.0))


def box_with_bottom_at(u: float, v: float) -> BoundingBox:
    return BoundingBox(x=u - 10.0, y=v - 8.0, width=20.0, height=8.0, confidence=0.9)


def pixel_row_for_distance(distance_m: float) -> float:
    """Bildzeile, in der ein Punkt auf dem Boden in dieser Distanz erscheint."""
    angle_below_horizon = math.atan(CAMERA.mounting_height_m / distance_m)
    return CAMERA.image_height / 2 + CAMERA.focal_y * math.tan(
        angle_below_horizon - CAMERA.tilt_down_rad)


@pytest.mark.parametrize('distance', [0.5, 1.0, 2.0, 3.0])
def test_bone_straight_ahead_gives_distance_and_zero_bearing(distance):
    location = locate_bone(box_with_bottom_at(320, pixel_row_for_distance(distance)), CAMERA)

    assert location.distance_m == pytest.approx(distance, rel=1e-6)
    assert location.bearing_rad == pytest.approx(0.0)


def test_bone_left_in_image_has_positive_bearing():
    location = locate_bone(box_with_bottom_at(100, 400), CAMERA)

    assert location.bearing_rad > 0.0


def test_bone_at_image_edge_has_half_field_of_view_bearing():
    location = locate_bone(box_with_bottom_at(640, 400), CAMERA)

    assert location.bearing_rad == pytest.approx(-math.radians(33.0), abs=1e-6)


def test_lower_in_image_means_closer():
    near = locate_bone(box_with_bottom_at(320, 470), CAMERA)
    far = locate_bone(box_with_bottom_at(320, 300), CAMERA)

    assert near.distance_m < far.distance_m


def test_point_above_horizon_cannot_be_located():
    assert locate_bone(box_with_bottom_at(320, 0), CAMERA) is None


def test_bottom_center_of_box():
    assert BoundingBox(10, 20, 30, 40, 0.5).bottom_center == (25.0, 60.0)


def test_yolo_detector_reports_missing_model(tmp_path):
    from pren_perception.bone.yolo_bone_detector import YoloBoneDetector

    with pytest.raises(FileNotFoundError):
        YoloBoneDetector(tmp_path / 'knochen.pt')
