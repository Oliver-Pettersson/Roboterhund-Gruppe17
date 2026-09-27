#!/usr/bin/env python3
"""
Gesture Classification Engine for Robot Dog (HSLU PREN1/PREN2 - Gruppe 17)
Evaluates 21 MediaPipe 3D Hand Landmarks using geometric heuristics.

Supported Gestures:
1. "UP" / «AUF»   : Index finger pointing UP (with or without flared thumb shaping an "L")
2. "DOWN" / «PLATZ»: Index finger pointing DOWN toward the floor
3. "SIT" / «SITZ» : Open palm facing camera / held in front of chest
"""

from collections import deque
from dataclasses import dataclass
from enum import Enum
import math
import time
from typing import Any, Deque, List, Optional, Tuple


class GestureType(Enum):
    NONE = "NONE"
    UP = "UP"        # Alias: AUF
    DOWN = "DOWN"    # Alias: PLATZ
    SIT = "SIT"      # Alias: SITZ

    @property
    def german_label(self) -> str:
        return {
            GestureType.NONE: "KEINE",
            GestureType.UP: "AUF",
            GestureType.DOWN: "PLATZ",
            GestureType.SIT: "SITZ",
        }[self]


@dataclass
class GestureResult:
    gesture: GestureType
    confidence: float
    raw_gesture: GestureType
    hand_label: str  # "Left" or "Right"
    description: str


class GestureClassifier:
    """
    Pure geometric classifier for 21 3D hand landmarks.
    Landmark Indices (MediaPipe convention):
      0: WRIST
      1-4: THUMB (CMC, MCP, IP, TIP)
      5-8: INDEX (MCP, PIP, DIP, TIP)
      9-12: MIDDLE (MCP, PIP, DIP, TIP)
      13-16: RING (MCP, PIP, DIP, TIP)
      17-20: PINKY (MCP, PIP, DIP, TIP)
    """

    @staticmethod
    def _dist(p1, p2) -> float:
        """Euclidean distance in 2D/3D."""
        dx = p1.x - p2.x
        dy = p1.y - p2.y
        dz = getattr(p1, 'z', 0.0) - getattr(p2, 'z', 0.0)
        return math.sqrt(max(0.0, dx * dx + dy * dy + dz * dz))

    @classmethod
    def _is_finger_extended(cls, landmarks, tip_idx: int, pip_idx: int, wrist_idx: int = 0, ratio: float = 1.18) -> bool:
        """A finger is extended if distance(TIP, WRIST) > ratio * distance(PIP, WRIST)."""
        dist_tip = cls._dist(landmarks[tip_idx], landmarks[wrist_idx])
        dist_pip = cls._dist(landmarks[pip_idx], landmarks[wrist_idx])
        return dist_tip > (dist_pip * ratio)

    @classmethod
    def _is_finger_curled(cls, landmarks, tip_idx: int, pip_idx: int, wrist_idx: int = 0) -> bool:
        """A finger is curled if distance(TIP, WRIST) <= distance(PIP, WRIST) * 1.12."""
        dist_tip = cls._dist(landmarks[tip_idx], landmarks[wrist_idx])
        dist_pip = cls._dist(landmarks[pip_idx], landmarks[wrist_idx])
        return dist_tip <= (dist_pip * 1.12)

    @classmethod
    def classify(cls, landmarks, handedness: str = "Right") -> GestureResult:
        """
        Classify 21 normalized hand landmarks.
        landmarks: iterable of 21 objects with .x, .y, .z
        handedness: "Left" or "Right"
        """
        if len(landmarks) < 21:
            return GestureResult(GestureType.NONE, 0.0, GestureType.NONE, handedness, "Insufficient landmarks")

        wrist = landmarks[0]
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        thumb_mcp = landmarks[2]

        index_mcp = landmarks[5]
        index_pip = landmarks[6]
        index_dip = landmarks[7]
        index_tip = landmarks[8]

        middle_mcp = landmarks[9]
        middle_pip = landmarks[10]
        middle_tip = landmarks[12]

        ring_mcp = landmarks[13]
        ring_pip = landmarks[14]
        ring_tip = landmarks[16]

        pinky_mcp = landmarks[17]
        pinky_pip = landmarks[18]
        pinky_tip = landmarks[20]

        # Finger extension states
        index_ext = cls._is_finger_extended(landmarks, 8, 6, 0, ratio=1.20)
        middle_ext = cls._is_finger_extended(landmarks, 12, 10, 0, ratio=1.20)
        ring_ext = cls._is_finger_extended(landmarks, 16, 14, 0, ratio=1.20)
        pinky_ext = cls._is_finger_extended(landmarks, 20, 18, 0, ratio=1.20)

        middle_curled = cls._is_finger_curled(landmarks, 12, 10, 0)
        ring_curled = cls._is_finger_curled(landmarks, 16, 14, 0)
        pinky_curled = cls._is_finger_curled(landmarks, 20, 18, 0)

        # Thumb extension: distance from thumb tip to wrist vs thumb mcp to wrist
        thumb_dist_wrist = cls._dist(thumb_tip, wrist)
        thumb_mcp_wrist = cls._dist(thumb_mcp, wrist)
        thumb_ext = thumb_dist_wrist > (thumb_mcp_wrist * 1.25)

        # Hand scale for normalized tolerances
        hand_scale = cls._dist(index_mcp, wrist)
        if hand_scale < 1e-4:
            return GestureResult(GestureType.NONE, 0.0, GestureType.NONE, handedness, "Degenerate hand scale")

        # --------------------------------------------------------------------
        # 1. GESTURE: "SIT" / «SITZ» (Open Palm)
        # All 4 primary fingers extended, thumb extended, palm facing camera
        # --------------------------------------------------------------------
        if index_ext and middle_ext and ring_ext and pinky_ext and thumb_ext:
            # Check fingers are generally pointing in similar upward/neutral directions
            y_diffs = [
                index_tip.y - index_mcp.y,
                middle_tip.y - middle_mcp.y,
                ring_tip.y - ring_mcp.y,
                pinky_tip.y - pinky_mcp.y
            ]
            # Hand should be open upright or held up before chest (tips higher or level with MCPs)
            if all(yd < 0.25 for yd in y_diffs):
                confidence = 0.95
                return GestureResult(
                    GestureType.SIT, confidence, GestureType.SIT, handedness,
                    "Open palm (all 5 fingers extended)"
                )

        # --------------------------------------------------------------------
        # 2. GESTURE: "UP" / «AUF» (Index pointing UP, or "L" shape)
        # Index extended vertically upward; Middle, Ring, Pinky curled
        # Thumb: either curled into fist OR flared out horizontally forming "L"
        # --------------------------------------------------------------------
        idx_dy = index_tip.y - index_mcp.y
        idx_dx = index_tip.x - index_mcp.x

        if index_ext and middle_curled and ring_curled and pinky_curled:
            # Direction check: Tip is ABOVE knuckle (y_tip < y_mcp in screen space)
            # and predominantly vertical (|dx| / |dy| < 0.70)
            if idx_dy < -0.10 * hand_scale and abs(idx_dx) < (abs(idx_dy) * 0.75):
                # Verify middle, ring, pinky are not extended
                if not (middle_ext or ring_ext or pinky_ext):
                    # Check thumb variant:
                    # Variant A: Standard Pointing Up (thumb curled)
                    # Variant B: "L" Handshape (thumb flared out laterally)
                    thumb_to_index_mcp = abs(thumb_tip.x - index_mcp.x)
                    is_l_shape = thumb_ext and (thumb_to_index_mcp > 0.40 * hand_scale)
                    desc = "Index pointing UP ('L' shape)" if is_l_shape else "Index pointing UP"
                    confidence = 0.95 if is_l_shape else 0.90
                    return GestureResult(GestureType.UP, confidence, GestureType.UP, handedness, desc)

        # --------------------------------------------------------------------
        # 3. GESTURE: "DOWN" / «PLATZ» (Index pointing DOWN toward floor)
        # Index extended vertically downward; Middle, Ring, Pinky curled
        # Wrist higher than fingertip
        # --------------------------------------------------------------------
        if index_ext and middle_curled and ring_curled and pinky_curled:
            # Direction check: Tip is BELOW knuckle (y_tip > y_mcp)
            # and predominantly vertical (|dx| / |dy| < 0.85)
            if idx_dy > 0.10 * hand_scale and abs(idx_dx) < (abs(idx_dy) * 0.85):
                # Hand base should be above or near index tip
                if wrist.y < index_tip.y:
                    confidence = 0.92
                    return GestureResult(
                        GestureType.DOWN, confidence, GestureType.DOWN, handedness,
                        "Index pointing DOWN (toward floor)"
                    )

        return GestureResult(GestureType.NONE, 0.0, GestureType.NONE, handedness, "No matching gesture")


class GestureSmoother:
    """
    Temporal debouncer and rolling majority vote filter.
    Eliminates single-frame noise and prevents rapid re-triggering via cooldown.
    """

    def __init__(self, window_size: int = 5, min_consensus: int = 4, cooldown_seconds: float = 1.0):
        self.window_size = window_size
        self.min_consensus = min_consensus
        self.cooldown_seconds = cooldown_seconds

        self.history: Deque[GestureType] = deque(maxlen=window_size)
        self.last_confirmed_gesture: GestureType = GestureType.NONE
        self.last_trigger_time: float = 0.0

    def update(self, raw_result: GestureResult, timestamp: Optional[float] = None) -> Tuple[GestureType, bool]:
        """
        Feed a raw frame classification into the smoother.
        Returns:
            (current_stable_gesture, is_new_event)
        """
        now = time.time() if timestamp is None else timestamp
        self.history.append(raw_result.gesture)

        if len(self.history) < self.min_consensus:
            return GestureType.NONE, False

        # Count occurrences of each gesture in rolling window
        counts = {}
        for g in self.history:
            counts[g] = counts.get(g, 0) + 1

        most_common = max(counts, key=counts.get)
        count = counts[most_common]

        # Must meet consensus threshold and not be NONE
        if count >= self.min_consensus and most_common != GestureType.NONE:
            # Check cooldown against repeated triggers
            is_new = False
            if most_common != self.last_confirmed_gesture or (now - self.last_trigger_time) >= self.cooldown_seconds:
                self.last_confirmed_gesture = most_common
                self.last_trigger_time = now
                is_new = True
            return most_common, is_new

        if count >= self.min_consensus and most_common == GestureType.NONE:
            self.last_confirmed_gesture = GestureType.NONE

        return self.last_confirmed_gesture, False

    def reset(self) -> None:
        self.history.clear()
        self.last_confirmed_gesture = GestureType.NONE
        self.last_trigger_time = 0.0
