"""
Glaettet die Gesten ueber mehrere Bilder, damit einzelne Fehlbilder nichts ausloesen.

Eine Geste gilt erst als erkannt, wenn sie in mindestens min_agreeing der letzten
window_size Bilder vorkommt. Dieselbe Geste loest danach erst nach cooldown_s
erneut aus. Uebernommen aus GestureSmoother im Prototyp.
"""

from collections import Counter, deque
import math
from typing import Optional

from pren_perception.gesture.hand_gesture_classifier import HandGesture


class GestureDebouncer:
    """Mehrheitsentscheid ueber die letzten Bilder mit Sperrzeit."""

    def __init__(self, window_size: int = 5, min_agreeing: int = 4, cooldown_s: float = 1.0):
        self._recent = deque(maxlen=window_size)
        self._min_agreeing = min_agreeing
        self._cooldown_s = cooldown_s
        self._last_gesture = HandGesture.NONE
        self._last_trigger_time = -math.inf

    def update(self, gesture: HandGesture, now: float) -> Optional[HandGesture]:
        """Nimmt die Geste eines Bildes auf. Gibt eine neu bestaetigte Geste zurueck."""
        self._recent.append(gesture)
        stable = self._stable_gesture()
        if stable is None:
            return None
        if stable is HandGesture.NONE:
            self._last_gesture = HandGesture.NONE
            return None

        is_new = stable is not self._last_gesture
        if is_new or now - self._last_trigger_time >= self._cooldown_s:
            self._last_gesture = stable
            self._last_trigger_time = now
            return stable
        return None

    def reset(self) -> None:
        """Vergisst alle bisherigen Bilder."""
        self._recent.clear()
        self._last_gesture = HandGesture.NONE
        self._last_trigger_time = -math.inf

    def _stable_gesture(self) -> Optional[HandGesture]:
        if len(self._recent) < self._min_agreeing:
            return None
        gesture, count = Counter(self._recent).most_common(1)[0]
        return gesture if count >= self._min_agreeing else None
