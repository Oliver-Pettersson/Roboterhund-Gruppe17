"""
Findet Befehlswoerter im erkannten Text und unterdrueckt Wiederholungen.

Die Spracherkennung liefert waehrend einer Aeusserung mehrmals Zwischenergebnisse.
Damit ein Wort nur einen Befehl ausloest, wird derselbe Befehl innerhalb von
repeat_cooldown_s nach dem letzten Ausloesen ignoriert. Ein anderer Befehl wird
sofort angenommen.
"""

import math
from typing import Dict, Optional

from pren_perception.commands import Command

# Woerter, die das Vosk-Modell erkennen soll, und der zugehoerige Befehl.
VOICE_KEYWORDS: Dict[str, Command] = {
    'hier': Command.HIER,
    'brav': Command.BRAV,
    'sitz': Command.SITZ,
    'such': Command.SUCH,
}

UNKNOWN_TOKEN = '[unk]'


def find_command(text: str, keywords: Dict[str, Command] = VOICE_KEYWORDS) -> Optional[Command]:
    """Erster Befehl im Text oder None. Gross-/Kleinschreibung spielt keine Rolle."""
    for word in text.lower().split():
        if word in keywords:
            return keywords[word]
    return None


class RepeatFilter:
    """Laesst denselben Befehl erst nach einer Pause wieder durch."""

    def __init__(self, repeat_cooldown_s: float):
        self._cooldown_s = repeat_cooldown_s
        self._last_command: Optional[Command] = None
        self._last_time = -math.inf

    def accept(self, command: Command, now: float) -> bool:
        """Melde, ob der Befehl weitergegeben werden soll, und merke ihn dann."""
        if command == self._last_command and now - self._last_time < self._cooldown_s:
            return False
        self._last_command = command
        self._last_time = now
        return True
