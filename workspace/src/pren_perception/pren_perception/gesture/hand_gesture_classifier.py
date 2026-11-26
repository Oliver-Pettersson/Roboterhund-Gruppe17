"""
Erkennt aus 21 MediaPipe-Handpunkten eine der drei Gesten.

    OPEN_PALM     flache Hand, alle Finger gestreckt          -> SITZ
    POINTING_UP   Zeigefinger nach oben (auch als "L")        -> AUF
    POINTING_DOWN Zeigefinger zum Boden, Handgelenk oben      -> PLATZ

Die Regeln und Schwellwerte stammen aus dem frueheren Gesten-Prototyp
(gesture_classifier.py, entfernt am 25.11.2026). Seit dem 20.11.2026 muss die flache
Hand zusaetzlich nach oben zeigen (OPEN_PALM_MIN_RISE, OPEN_PALM_MAX_SLOPE).

Bildkoordinaten von MediaPipe: x nach rechts, y nach UNTEN, Werte 0 bis 1.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Optional, Sequence

from pren_perception.commands import Command

# Indizes der MediaPipe-Handpunkte
WRIST = 0
THUMB_MCP, THUMB_TIP = 2, 4
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_MCP, RING_PIP, RING_TIP = 13, 14, 16
PINKY_MCP, PINKY_PIP, PINKY_TIP = 17, 18, 20
LANDMARK_COUNT = 21

# (Spitze, Mittelgelenk, Grundgelenk) der vier Langfinger
FINGERS = {
    'index': (INDEX_TIP, INDEX_PIP, INDEX_MCP),
    'middle': (MIDDLE_TIP, MIDDLE_PIP, MIDDLE_MCP),
    'ring': (RING_TIP, RING_PIP, RING_MCP),
    'pinky': (PINKY_TIP, PINKY_PIP, PINKY_MCP),
}

# Schwellwerte (Verhaeltnisse von Abstaenden zum Handgelenk)
EXTENDED_RATIO = 1.20         # Finger gestreckt: Spitze deutlich weiter weg als Mittelgelenk
CURLED_RATIO = 1.12           # Finger eingerollt: Spitze kaum weiter weg als Mittelgelenk
THUMB_EXTENDED_RATIO = 1.25
OPEN_PALM_MAX_DROP = 0.25     # Fingerspitzen duerfen hoechstens so weit unter dem Knoechel sein
# Flache Hand nur, wenn sie nach oben zeigt (wie ein Stoppzeichen). Im Test T2 vom 20.11.2026
# loesten Handy halten, Arme verschraenken und Kopf kratzen 4 von 9 Mal SITZ aus.
OPEN_PALM_MIN_RISE = 1.0      # Mittelfingerspitze mind. 1 Handgroesse ueber dem Handgelenk
OPEN_PALM_MAX_SLOPE = 1.0     # |dx| / |dy| Handgelenk -> Mittelfingerspitze, max. 45 Grad schraeg
MIN_VERTICAL_TRAVEL = 0.10    # Zeigefinger muss mind. 10 % der Handgroesse senkrecht zeigen
UP_MAX_SLOPE = 0.75           # |dx| / |dy| beim Zeigen nach oben
DOWN_MAX_SLOPE = 0.85         # |dx| / |dy| beim Zeigen nach unten
L_SHAPE_THUMB_SPREAD = 0.40   # Daumen seitlich abgespreizt -> "L"


class HandGesture(Enum):
    """Erkennbare Handgesten mit dem zugehoerigen Befehl."""

    NONE = None
    OPEN_PALM = Command.SITZ
    POINTING_UP = Command.AUF
    POINTING_DOWN = Command.PLATZ

    @property
    def command(self) -> Optional[Command]:
        """Befehl zur Geste oder None."""
        return self.value


@dataclass(frozen=True)
class GestureResult:
    """Ergebnis fuer ein einzelnes Bild."""

    gesture: HandGesture
    confidence: float
    description: str


NO_GESTURE = GestureResult(HandGesture.NONE, 0.0, 'Keine Geste')


def _distance(a, b) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 +
                     (getattr(a, 'z', 0.0) - getattr(b, 'z', 0.0)) ** 2)


class _Hand:
    """Hilfsklasse mit sprechenden Abfragen auf den 21 Handpunkten."""

    def __init__(self, landmarks: Sequence):
        self.points = landmarks
        self.wrist = landmarks[WRIST]
        self.scale = _distance(landmarks[INDEX_MCP], self.wrist)

    def _reach(self, index: int) -> float:
        return _distance(self.points[index], self.wrist)

    def is_extended(self, finger: str) -> bool:
        tip, pip, _ = FINGERS[finger]
        return self._reach(tip) > self._reach(pip) * EXTENDED_RATIO

    def is_curled(self, finger: str) -> bool:
        tip, pip, _ = FINGERS[finger]
        return self._reach(tip) <= self._reach(pip) * CURLED_RATIO

    def thumb_is_extended(self) -> bool:
        return self._reach(THUMB_TIP) > self._reach(THUMB_MCP) * THUMB_EXTENDED_RATIO

    def fingertip_drop(self, finger: str) -> float:
        """Wie weit die Spitze unter dem Knoechel liegt (positiv = tiefer im Bild)."""
        tip, _, mcp = FINGERS[finger]
        return self.points[tip].y - self.points[mcp].y

    def index_direction(self) -> tuple:
        """(dx, dy) vom Zeigefinger-Knoechel zur Spitze."""
        tip, mcp = self.points[INDEX_TIP], self.points[INDEX_MCP]
        return tip.x - mcp.x, tip.y - mcp.y

    def only_index_extended(self) -> bool:
        others = ('middle', 'ring', 'pinky')
        return (self.is_extended('index')
                and all(self.is_curled(finger) for finger in others)
                and not any(self.is_extended(finger) for finger in others))


def classify_hand(landmarks: Sequence) -> GestureResult:
    """Ordnet 21 Handpunkte einer Geste zu."""
    if len(landmarks) < LANDMARK_COUNT:
        return GestureResult(HandGesture.NONE, 0.0, 'Zu wenige Handpunkte')
    hand = _Hand(landmarks)
    if hand.scale < 1e-4:
        return GestureResult(HandGesture.NONE, 0.0, 'Hand zu klein')

    if _is_open_palm(hand):
        return GestureResult(HandGesture.OPEN_PALM, 0.95, 'Flache Hand')
    if _is_pointing_up(hand):
        thumb_spread = abs(landmarks[THUMB_TIP].x - landmarks[INDEX_MCP].x)
        if hand.thumb_is_extended() and thumb_spread > L_SHAPE_THUMB_SPREAD * hand.scale:
            return GestureResult(HandGesture.POINTING_UP, 0.95, 'Zeigefinger nach oben (L)')
        return GestureResult(HandGesture.POINTING_UP, 0.90, 'Zeigefinger nach oben')
    if _is_pointing_down(hand):
        return GestureResult(HandGesture.POINTING_DOWN, 0.92, 'Zeigefinger nach unten')
    return NO_GESTURE


def _is_open_palm(hand: _Hand) -> bool:
    return (all(hand.is_extended(finger) for finger in FINGERS)
            and hand.thumb_is_extended()
            and all(hand.fingertip_drop(finger) < OPEN_PALM_MAX_DROP for finger in FINGERS)
            and _points_up(hand))


def _points_up(hand: _Hand) -> bool:
    """Hand zeigt nach oben: alle Fingerspitzen ueber dem Handgelenk, Hand kaum schraeg."""
    tip = hand.points[MIDDLE_TIP]
    dx, dy = tip.x - hand.wrist.x, tip.y - hand.wrist.y
    return (dy < -OPEN_PALM_MIN_RISE * hand.scale
            and abs(dx) <= abs(dy) * OPEN_PALM_MAX_SLOPE
            and all(hand.points[FINGERS[finger][0]].y < hand.wrist.y for finger in FINGERS))


def _is_pointing_up(hand: _Hand) -> bool:
    dx, dy = hand.index_direction()
    return (hand.only_index_extended()
            and dy < -MIN_VERTICAL_TRAVEL * hand.scale
            and abs(dx) < abs(dy) * UP_MAX_SLOPE)


def _is_pointing_down(hand: _Hand) -> bool:
    dx, dy = hand.index_direction()
    return (hand.only_index_extended()
            and dy > MIN_VERTICAL_TRAVEL * hand.scale
            and abs(dx) < abs(dy) * DOWN_MAX_SLOPE
            and hand.wrist.y < hand.points[INDEX_TIP].y)
