"""Kuenstliche MediaPipe-Handpunkte fuer Tests (aus dem Gesten-Prototyp uebernommen)."""

from dataclasses import dataclass


@dataclass
class Point:
    x: float
    y: float
    z: float = 0.0


def hand(wrist, thumb, index, middle, ring, pinky):
    """21 Punkte in MediaPipe-Reihenfolge: Handgelenk, dann je Finger 4 Punkte."""
    points = [Point(*wrist)]
    for finger in (thumb, index, middle, ring, pinky):
        points.extend(Point(*p) for p in finger)
    return points


def curled(mcp_x, mcp_y):
    """Knoechel plus Mittelgelenk, Endgelenk und Spitze eines eingerollten Fingers."""
    return ((mcp_x, mcp_y), (mcp_x, mcp_y - 0.05), (mcp_x, mcp_y - 0.02), (mcp_x, mcp_y + 0.02))


OPEN_PALM = hand(
    wrist=(0.5, 0.8),
    thumb=((0.40, 0.72), (0.35, 0.65), (0.30, 0.58), (0.25, 0.52)),
    index=((0.45, 0.60), (0.45, 0.48), (0.45, 0.38), (0.45, 0.28)),
    middle=((0.50, 0.58), (0.50, 0.45), (0.50, 0.35), (0.50, 0.25)),
    ring=((0.55, 0.60), (0.55, 0.48), (0.55, 0.38), (0.55, 0.28)),
    pinky=((0.60, 0.63), (0.60, 0.52), (0.60, 0.44), (0.60, 0.35)),
)

POINTING_UP = hand(
    wrist=(0.5, 0.8),
    thumb=((0.44, 0.75), (0.43, 0.70), (0.44, 0.67), (0.46, 0.66)),
    index=((0.48, 0.60), (0.48, 0.48), (0.48, 0.38), (0.48, 0.25)),
    middle=curled(0.52, 0.60), ring=curled(0.55, 0.62), pinky=curled(0.58, 0.65),
)

L_SHAPE = hand(
    wrist=(0.5, 0.8),
    thumb=((0.42, 0.72), (0.35, 0.68), (0.28, 0.65), (0.20, 0.63)),
    index=((0.48, 0.60), (0.48, 0.48), (0.48, 0.38), (0.48, 0.25)),
    middle=curled(0.52, 0.60), ring=curled(0.55, 0.62), pinky=curled(0.58, 0.65),
)

POINTING_DOWN = hand(
    wrist=(0.5, 0.3),
    thumb=((0.44, 0.35), (0.43, 0.40), (0.44, 0.43), (0.46, 0.45)),
    index=((0.48, 0.45), (0.48, 0.55), (0.48, 0.65), (0.48, 0.80)),
    middle=((0.52, 0.45), (0.52, 0.49), (0.52, 0.47), (0.52, 0.44)),
    ring=((0.55, 0.44), (0.55, 0.48), (0.55, 0.46), (0.55, 0.43)),
    pinky=((0.58, 0.43), (0.58, 0.47), (0.58, 0.45), (0.58, 0.42)),
)

FIST = hand(
    wrist=(0.5, 0.8),
    thumb=((0.45, 0.75), (0.44, 0.70), (0.45, 0.68), (0.48, 0.68)),
    index=curled(0.48, 0.65), middle=curled(0.52, 0.64),
    ring=curled(0.55, 0.65), pinky=curled(0.58, 0.68),
)

PEACE_SIGN = hand(
    wrist=(0.5, 0.8),
    thumb=((0.44, 0.75), (0.43, 0.70), (0.44, 0.67), (0.46, 0.66)),
    index=((0.46, 0.60), (0.46, 0.48), (0.46, 0.38), (0.46, 0.25)),
    middle=((0.54, 0.60), (0.54, 0.48), (0.54, 0.38), (0.54, 0.25)),
    ring=curled(0.58, 0.62), pinky=curled(0.61, 0.65),
)

POINTING_SIDEWAYS = hand(
    wrist=(0.3, 0.5),
    thumb=((0.35, 0.52), (0.36, 0.50), (0.37, 0.49), (0.38, 0.49)),
    index=((0.45, 0.50), (0.58, 0.50), (0.70, 0.50), (0.85, 0.50)),
    middle=curled(0.45, 0.54), ring=curled(0.44, 0.58), pinky=curled(0.43, 0.62),
)
