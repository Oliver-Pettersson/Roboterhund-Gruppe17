"""Tests fuer Antrieb, Sichtkegel und Knochenplatzierung."""

import math
import random

from pren_simulation.simulation_math import (
    DifferentialDrive,
    random_bone_position,
    VisionCone,
    yaw_from_rotation_matrix,
)
import pytest


def test_straight_driving_turns_both_wheels_equally():
    left, right = DifferentialDrive().wheel_speeds(0.3, 0.0)
    assert left == pytest.approx(right)
    assert left > 0.0


def test_turning_left_makes_right_wheel_faster():
    left, right = DifferentialDrive().wheel_speeds(0.0, 1.0)
    assert right > 0.0 > left


def test_wheel_speeds_are_limited():
    drive = DifferentialDrive()
    left, right = drive.wheel_speeds(10.0, 0.0)
    assert left == right == drive.max_wheel_speed


@pytest.mark.parametrize('linear, angular', [(0.3, 0.0), (0.0, 1.2), (0.2, -0.5)])
def test_body_velocity_is_inverse_of_wheel_speeds(linear, angular):
    drive = DifferentialDrive()
    assert drive.body_velocity(*drive.wheel_speeds(linear, angular)) == \
        pytest.approx((linear, angular))


def test_cone_sees_target_straight_ahead():
    visible, distance, bearing = VisionCone().observe(0.0, 0.0, 0.0, 2.0, 0.0)
    assert visible
    assert distance == pytest.approx(2.0)
    assert bearing == pytest.approx(0.0)


def test_cone_reports_bearing_positive_to_the_left():
    _, _, bearing = VisionCone().observe(0.0, 0.0, 0.0, 2.0, 0.5)
    assert bearing > 0.0


@pytest.mark.parametrize('target', [(4.0, 0.0), (-2.0, 0.0), (1.0, 1.0)])
def test_cone_misses_target_out_of_range_or_angle(target):
    visible, _, _ = VisionCone().observe(0.0, 0.0, 0.0, *target)
    assert not visible


def test_cone_respects_robot_heading():
    visible, _, _ = VisionCone().observe(0.0, 0.0, math.pi, -2.0, 0.0)
    assert visible


def test_random_bone_lies_inside_search_sector():
    rng = random.Random(17)
    for _ in range(200):
        x, y = random_bone_position(rng)
        assert 2.0 <= math.hypot(x, y) <= 4.0
        assert abs(math.atan2(y, x)) <= math.radians(12.0) + 1e-9


def test_yaw_from_rotation_matrix():
    yaw = 2.5
    matrix = [math.cos(yaw), -math.sin(yaw), 0.0,
              math.sin(yaw), math.cos(yaw), 0.0,
              0.0, 0.0, 1.0]
    assert yaw_from_rotation_matrix(matrix) == pytest.approx(yaw)
