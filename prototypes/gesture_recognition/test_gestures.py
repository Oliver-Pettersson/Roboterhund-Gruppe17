#!/usr/bin/env python3
"""
Unit tests for GestureClassifier and GestureSmoother using synthetic landmark fixtures.
Verifies all 3 PREN gestures ('Up' / AUF, 'Down' / PLATZ, 'Sit' / SITZ) and edge cases.
"""

from dataclasses import dataclass
import pytest
from gesture_classifier import GestureClassifier, GestureSmoother, GestureType


@dataclass
class Point3D:
    x: float
    y: float
    z: float = 0.0


def create_hand(
    wrist=(0.5, 0.7),
    thumb=((0.45, 0.65), (0.42, 0.60), (0.40, 0.58), (0.38, 0.56)),
    index=((0.48, 0.55), (0.48, 0.45), (0.48, 0.38), (0.48, 0.30)),
    middle=((0.51, 0.54), (0.51, 0.43), (0.51, 0.36), (0.51, 0.28)),
    ring=((0.54, 0.55), (0.54, 0.45), (0.54, 0.39), (0.54, 0.32)),
    pinky=((0.57, 0.57), (0.57, 0.50), (0.57, 0.45), (0.57, 0.40))
):
    """Generate 21-landmark list matching MediaPipe Hand indices."""
    landmarks = [Point3D(wrist[0], wrist[1], 0.0)]
    for pt in thumb:
        landmarks.append(Point3D(pt[0], pt[1], 0.0))
    for pt in index:
        landmarks.append(Point3D(pt[0], pt[1], 0.0))
    for pt in middle:
        landmarks.append(Point3D(pt[0], pt[1], 0.0))
    for pt in ring:
        landmarks.append(Point3D(pt[0], pt[1], 0.0))
    for pt in pinky:
        landmarks.append(Point3D(pt[0], pt[1], 0.0))
    return landmarks


def make_curled_finger(mcp_x, mcp_y):
    """Return PIP, DIP, TIP for a finger curled tightly back towards the MCP."""
    return (
        (mcp_x, mcp_y - 0.05),
        (mcp_x, mcp_y - 0.02),
        (mcp_x, mcp_y + 0.02),  # Tip is curled down near or below knuckle
    )


# ---------------------------------------------------------------------------
# Test Fixtures for the 3 Gestures
# ---------------------------------------------------------------------------

def test_sit_gesture_open_palm():
    """All 5 fingers extended upright = SIT / SITZ."""
    landmarks = create_hand(
        wrist=(0.5, 0.8),
        thumb=((0.40, 0.72), (0.35, 0.65), (0.30, 0.58), (0.25, 0.52)),   # Open flared thumb
        index=((0.45, 0.60), (0.45, 0.48), (0.45, 0.38), (0.45, 0.28)),   # Extended
        middle=((0.50, 0.58), (0.50, 0.45), (0.50, 0.35), (0.50, 0.25)),  # Extended
        ring=((0.55, 0.60), (0.55, 0.48), (0.55, 0.38), (0.55, 0.28)),    # Extended
        pinky=((0.60, 0.63), (0.60, 0.52), (0.60, 0.44), (0.60, 0.35))    # Extended
    )
    res = GestureClassifier.classify(landmarks)
    assert res.gesture == GestureType.SIT
    assert res.gesture.german_label == "SITZ"
    assert res.confidence >= 0.90


def test_up_gesture_pointing_index():
    """Index pointing straight up, others curled = UP / AUF."""
    landmarks = create_hand(
        wrist=(0.5, 0.8),
        thumb=((0.44, 0.75), (0.43, 0.70), (0.44, 0.67), (0.46, 0.66)),  # Curled thumb
        index=((0.48, 0.60), (0.48, 0.48), (0.48, 0.38), (0.48, 0.25)),  # Extended straight up
        middle=((0.52, 0.60), *make_curled_finger(0.52, 0.60)),
        ring=((0.55, 0.62), *make_curled_finger(0.55, 0.62)),
        pinky=((0.58, 0.65), *make_curled_finger(0.58, 0.65))
    )
    res = GestureClassifier.classify(landmarks)
    assert res.gesture == GestureType.UP
    assert res.gesture.german_label == "AUF"
    assert res.confidence >= 0.85


def test_up_gesture_l_shape():
    """Index pointing up + thumb flared out at ~90 degrees forming 'L' = UP / AUF."""
    landmarks = create_hand(
        wrist=(0.5, 0.8),
        thumb=((0.42, 0.72), (0.35, 0.68), (0.28, 0.65), (0.20, 0.63)),  # Flared out horizontally
        index=((0.48, 0.60), (0.48, 0.48), (0.48, 0.38), (0.48, 0.25)),  # Extended straight up
        middle=((0.52, 0.60), *make_curled_finger(0.52, 0.60)),
        ring=((0.55, 0.62), *make_curled_finger(0.55, 0.62)),
        pinky=((0.58, 0.65), *make_curled_finger(0.58, 0.65))
    )
    res = GestureClassifier.classify(landmarks)
    assert res.gesture == GestureType.UP
    assert "L" in res.description
    assert res.confidence >= 0.90


def test_down_gesture_pointing_down():
    """Index pointing straight down, others curled, wrist above = DOWN / PLATZ."""
    landmarks = create_hand(
        wrist=(0.5, 0.3),  # Wrist is at the top
        thumb=((0.44, 0.35), (0.43, 0.40), (0.44, 0.43), (0.46, 0.45)),  # Curled thumb
        index=((0.48, 0.45), (0.48, 0.55), (0.48, 0.65), (0.48, 0.80)),  # Extended pointing DOWN
        middle=((0.52, 0.45), (0.52, 0.49), (0.52, 0.47), (0.52, 0.44)), # Curled back up
        ring=((0.55, 0.44), (0.55, 0.48), (0.55, 0.46), (0.55, 0.43)),   # Curled
        pinky=((0.58, 0.43), (0.58, 0.47), (0.58, 0.45), (0.58, 0.42))   # Curled
    )
    res = GestureClassifier.classify(landmarks)
    assert res.gesture == GestureType.DOWN
    assert res.gesture.german_label == "PLATZ"
    assert res.confidence >= 0.90


def test_closed_fist_rejected():
    """Closed fist (all fingers curled) must return NONE."""
    landmarks = create_hand(
        wrist=(0.5, 0.8),
        thumb=((0.45, 0.75), (0.44, 0.70), (0.45, 0.68), (0.48, 0.68)),
        index=((0.48, 0.65), *make_curled_finger(0.48, 0.65)),
        middle=((0.52, 0.64), *make_curled_finger(0.52, 0.64)),
        ring=((0.55, 0.65), *make_curled_finger(0.55, 0.65)),
        pinky=((0.58, 0.68), *make_curled_finger(0.58, 0.68))
    )
    res = GestureClassifier.classify(landmarks)
    assert res.gesture == GestureType.NONE


def test_peace_sign_rejected():
    """Index + Middle extended (V-sign) must not trigger UP."""
    landmarks = create_hand(
        wrist=(0.5, 0.8),
        thumb=((0.44, 0.75), (0.43, 0.70), (0.44, 0.67), (0.46, 0.66)),
        index=((0.46, 0.60), (0.46, 0.48), (0.46, 0.38), (0.46, 0.25)),  # Extended
        middle=((0.54, 0.60), (0.54, 0.48), (0.54, 0.38), (0.54, 0.25)), # Extended (peace sign!)
        ring=((0.58, 0.62), *make_curled_finger(0.58, 0.62)),
        pinky=((0.61, 0.65), *make_curled_finger(0.61, 0.65))
    )
    res = GestureClassifier.classify(landmarks)
    assert res.gesture == GestureType.NONE


def test_horizontal_pointing_rejected():
    """Index pointing horizontally to the side must not trigger UP or DOWN."""
    landmarks = create_hand(
        wrist=(0.3, 0.5),
        thumb=((0.35, 0.52), (0.36, 0.50), (0.37, 0.49), (0.38, 0.49)),
        index=((0.45, 0.50), (0.58, 0.50), (0.70, 0.50), (0.85, 0.50)),  # Pointing horizontally right
        middle=((0.45, 0.54), *make_curled_finger(0.45, 0.54)),
        ring=((0.44, 0.58), *make_curled_finger(0.44, 0.58)),
        pinky=((0.43, 0.62), *make_curled_finger(0.43, 0.62))
    )
    res = GestureClassifier.classify(landmarks)
    assert res.gesture == GestureType.NONE


# ---------------------------------------------------------------------------
# Test Temporal Smoother & Cooldown
# ---------------------------------------------------------------------------

def test_smoother_debounces_single_frame_noise():
    smoother = GestureSmoother(window_size=5, min_consensus=4, cooldown_seconds=1.0)
    fist_landmarks = create_hand(
        wrist=(0.5, 0.8),
        thumb=((0.45, 0.75), (0.44, 0.70), (0.45, 0.68), (0.48, 0.68)),
        index=((0.48, 0.65), *make_curled_finger(0.48, 0.65)),
        middle=((0.52, 0.64), *make_curled_finger(0.52, 0.64)),
        ring=((0.55, 0.65), *make_curled_finger(0.55, 0.65)),
        pinky=((0.58, 0.68), *make_curled_finger(0.58, 0.68))
    )
    fake_res_none = GestureClassifier.classify(fist_landmarks) # NONE

    # 4 frames of NONE, 1 frame of UP
    for _ in range(4):
        g, is_new = smoother.update(fake_res_none)
        assert g == GestureType.NONE
        assert not is_new

    # 1 single glitch frame of UP
    up_landmarks = create_hand(
        wrist=(0.5, 0.8),
        thumb=((0.44, 0.75), (0.43, 0.70), (0.44, 0.67), (0.46, 0.66)),
        index=((0.48, 0.60), (0.48, 0.48), (0.48, 0.38), (0.48, 0.25)),
        middle=((0.52, 0.60), *make_curled_finger(0.52, 0.60)),
        ring=((0.55, 0.62), *make_curled_finger(0.55, 0.62)),
        pinky=((0.58, 0.65), *make_curled_finger(0.58, 0.65))
    )
    fake_res_up = GestureClassifier.classify(up_landmarks)
    g, is_new = smoother.update(fake_res_up)
    # Should STILL be NONE because consensus of 4 was not met
    assert g == GestureType.NONE
    assert not is_new


def test_smoother_triggers_on_consensus_and_respects_cooldown():
    smoother = GestureSmoother(window_size=5, min_consensus=4, cooldown_seconds=1.0)
    up_landmarks = create_hand(
        wrist=(0.5, 0.8),
        thumb=((0.44, 0.75), (0.43, 0.70), (0.44, 0.67), (0.46, 0.66)),
        index=((0.48, 0.60), (0.48, 0.48), (0.48, 0.38), (0.48, 0.25)),
        middle=((0.52, 0.60), *make_curled_finger(0.52, 0.60)),
        ring=((0.55, 0.62), *make_curled_finger(0.55, 0.62)),
        pinky=((0.58, 0.65), *make_curled_finger(0.58, 0.65))
    )
    fake_res_up = GestureClassifier.classify(up_landmarks)

    t = 100.0
    # Feed 3 frames: not yet consensus
    for _ in range(3):
        g, is_new = smoother.update(fake_res_up, timestamp=t)
        assert not is_new

    # 4th frame: meets consensus!
    g, is_new = smoother.update(fake_res_up, timestamp=t)
    assert g == GestureType.UP
    assert is_new is True

    # 5th frame immediately after (t + 0.03s): still UP, but is_new must be False due to cooldown
    g, is_new = smoother.update(fake_res_up, timestamp=t + 0.03)
    assert g == GestureType.UP
    assert is_new is False

    # After cooldown elapsed (t + 1.2s): should trigger new event
    g, is_new = smoother.update(fake_res_up, timestamp=t + 1.2)
    assert g == GestureType.UP
    assert is_new is True
