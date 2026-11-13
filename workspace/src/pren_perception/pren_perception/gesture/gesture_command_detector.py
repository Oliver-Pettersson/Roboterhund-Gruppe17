"""
Verbindet Handpunkt-Erkennung, Klassifikation und Glaettung zu einem Ablauf.

Pro Kamerabild wird process() aufgerufen. Sobald eine Geste stabil erkannt ist,
gibt process() den Befehl einmal zurueck.
"""

from typing import Callable, List, Optional, Sequence

import numpy as np
from pren_perception.commands import Command
from pren_perception.gesture.gesture_debouncer import GestureDebouncer
from pren_perception.gesture.hand_gesture_classifier import (
    classify_hand,
    GestureResult,
    NO_GESTURE,
)

LandmarkSource = Callable[[np.ndarray], List[Sequence]]


class GestureCommandDetector:
    """Macht aus Kamerabildern erkannte Befehle."""

    def __init__(self, find_hands: LandmarkSource, debouncer: GestureDebouncer):
        self._find_hands = find_hands
        self._debouncer = debouncer
        self.last_result: GestureResult = NO_GESTURE

    def process(self, bgr_image: np.ndarray, now: float) -> Optional[Command]:
        """Verarbeitet ein Bild. Gibt einen neu bestaetigten Befehl zurueck."""
        results = [classify_hand(hand) for hand in self._find_hands(bgr_image)]
        # Bei mehreren Haenden zaehlt die sicherste Geste.
        self.last_result = max(results, key=lambda r: r.confidence, default=NO_GESTURE)
        confirmed = self._debouncer.update(self.last_result.gesture, now)
        return confirmed.command if confirmed is not None else None
