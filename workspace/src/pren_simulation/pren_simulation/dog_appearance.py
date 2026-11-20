"""
Wie die Simulation Haltung und Signale des Hundes sichtbar und hoerbar macht.

Der Pioneer-Roboter hat keine Beine. Haltung, Taetigkeit und Lob werden deshalb als
Text im 3D-Fenster angezeigt, der Knochenfund mit Licht und Bellen.
"""

import math
from typing import Optional

from pren_interfaces.msg import DogSignal, Posture

POSTURE_TEXT = {
    Posture.STAND: 'steht',
    Posture.SIT: 'sitzt',
    Posture.LIE: 'liegt',
}

SIGNAL_SOUND = {
    DogSignal.BARK: 'dog_bark.wav',
    DogSignal.MISSION_COMPLETE: 'victory_chime.wav',
}

BARK_LIGHT_DURATION_S = 2.2
PRAISE_DURATION_S = 2.0


class DogAppearance:
    """Merkt sich Haltung, Taetigkeit und laufende Effekte."""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        """Alle Effekte aus, Hund steht."""
        self.posture = Posture.STAND
        self.activity = ''
        self._light_until = -math.inf
        self._praise_until = -math.inf

    def on_signal(self, signal: int, now: float) -> Optional[str]:
        """Startet den Effekt zum Signal. Gibt die abzuspielende Tondatei zurueck."""
        if signal == DogSignal.BARK:
            self._light_until = now + BARK_LIGHT_DURATION_S
        elif signal == DogSignal.PRAISE:
            self._praise_until = now + PRAISE_DURATION_S
        return SIGNAL_SOUND.get(signal)

    def status_text(self, now: float) -> str:
        """Text fuer die Anzeige im 3D-Fenster."""
        lines = [f'Hund {POSTURE_TEXT.get(self.posture, "?")}']
        if self.activity:
            lines.append(self.activity)
        if now < self._praise_until:
            lines.append('BRAV! Der Hund freut sich.')
        return '\n'.join(lines)

    def light_intensity(self, now: float) -> float:
        """Pulsierendes Licht nach dem Knochenfund, sonst aus."""
        if now >= self._light_until:
            return 0.0
        return 5.0 + 3.0 * math.sin(now * 10.0)
