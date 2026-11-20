"""
Glaettet die Gesten ueber mehrere Bilder, damit einzelne Fehlbilder nichts ausloesen.

Eine Geste gilt erst als erkannt, wenn sie in mindestens min_agreeing der letzten
window_size Bilder vorkommt. Dieselbe Geste loest danach erst nach cooldown_s
erneut aus. Uebernommen aus GestureSmoother im Prototyp.

Fuer die flache Hand (SITZ) kann eine strengere Glaettung gelten (open_palm_window_size,
open_palm_min_agreeing): Sie entsteht auch zufaellig, z. B. beim Kopfkratzen. AUF und
PLATZ bleiben dadurch gleich schnell.
"""

from collections import Counter, deque
import math
from typing import Optional

from pren_perception.gesture.hand_gesture_classifier import HandGesture


class GestureDebouncer:
    """Mehrheitsentscheid ueber die letzten Bilder mit Sperrzeit."""

    def __init__(self, window_size: int = 5, min_agreeing: int = 4, cooldown_s: float = 1.0,
                 open_palm_window_size: int = 0, open_palm_min_agreeing: int = 0):
        # 0 = wie die anderen Gesten
        self._window_size = window_size
        self._palm_window = open_palm_window_size or window_size
        self._palm_min_agreeing = open_palm_min_agreeing or min_agreeing
        self._recent = deque(maxlen=max(window_size, self._palm_window))
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
        window = list(self._recent)[-self._window_size:]
        if len(window) < self._min_agreeing:
            return None
        gesture, count = Counter(window).most_common(1)[0]
        if count < self._min_agreeing:
            return None
        if gesture is HandGesture.OPEN_PALM:
            palm_window = list(self._recent)[-self._palm_window:]
            if palm_window.count(HandGesture.OPEN_PALM) < self._palm_min_agreeing:
                return None
        return gesture
