"""Merkt sich den letzten Messwert eines Sensors und verwirft ihn, wenn er zu alt ist."""

import math
from typing import Generic, Optional, TypeVar

T = TypeVar('T')


class LatestReading(Generic[T]):
    """
    Letzter Messwert mit Ablaufzeit.

    Faellt ein Sensor aus (Kabel, abgestuerzter Node), darf das Verhalten nicht mit dem
    alten Wert weiterfahren. Nach max_age_s gilt der Wert als nicht mehr vorhanden.
    """

    def __init__(self, max_age_s: float):
        self._max_age_s = max_age_s
        self._value: Optional[T] = None
        self._received_at = -math.inf

    def update(self, value: T, now: float) -> None:
        """Speichert einen neuen Messwert."""
        self._value = value
        self._received_at = now

    def get(self, now: float, default: Optional[T] = None) -> Optional[T]:
        """Den Messwert, wenn er frisch genug ist, sonst default."""
        if self._value is None or now - self._received_at > self._max_age_s:
            return default
        return self._value

    @property
    def ever_received(self) -> bool:
        """Melde, ob schon einmal ein Wert kam."""
        return self._value is not None

    def clear(self) -> None:
        """Vergisst den gespeicherten Wert."""
        self._value = None
        self._received_at = -math.inf
