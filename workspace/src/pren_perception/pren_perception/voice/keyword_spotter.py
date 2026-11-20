"""
Entscheidet, ob eine abgeschlossene Aeusserung ein Sprachbefehl ist.

Vosk mit fester Wortliste ordnet jedes gehoerte Wort dem aehnlichsten Wort der Liste zu.
Mit nur den vier Befehlen wird deshalb fast jedes Gespraech zu Befehlen. Drei Regeln
verhindern das:

1. Die Wortliste enthaelt neben den Befehlen viele Fuellwoerter (FILLER_WORDS). Fremde
   Woerter landen dann meist dort statt bei einem Befehl.
2. Ein Befehl wird nur angenommen, wenn die ganze Aeusserung aus genau diesem einen Wort
   besteht. Wer "Sitz!" ruft, sagt nichts anderes; Gespraeche bestehen aus vielen Woertern.
3. Die Erkennung muss sich sicher sein (min_confidence, Standard 0.7).

Zusaetzlich unterdrueckt RepeatFilter, dass derselbe Befehl kurz hintereinander doppelt
ausgeloest wird.
"""

from dataclasses import dataclass
import math
from typing import Dict, Optional, Sequence

from pren_perception.commands import Command

# Woerter, die einen Befehl ausloesen (laut Aufgabe nur diese vier per Sprache).
VOICE_KEYWORDS: Dict[str, Command] = {
    'hier': Command.HIER,
    'brav': Command.BRAV,
    'sitz': Command.SITZ,
    'such': Command.SUCH,
}

# Woerter, die Vosk ebenfalls erkennen darf, die aber nie einen Befehl ausloesen.
FILLER_WORDS = (
    # aehnlich klingend wie ein Befehl. Reime auf "hier" (wir, mir, vier ...) fehlen
    # bewusst: sie verdraengen bei Rauschen das echte "hier" (gemessen mit den Testaufnahmen).
    # Aus demselben Grund fehlen "braun" und "brauchen": Im Test T1 vom 20.11.2026 (Laptop-
    # Mikrofon, 1 m) wurde "brav" meist als "brauchen" gehoert, BRAV kam ruhig nur auf 60 %,
    # mit Laerm auf 20 %.
    'sitzen', 'setzen', 'suchen', 'sucht', 'hierher', 'sie', 'sicht',
    'ziel', 'zug', 'buch', 'tuch', 'platz', 'auf',
    # haeufig im Gespraech
    'ja', 'nein', 'danke', 'bitte', 'hallo', 'gut', 'genau', 'ich', 'du', 'er', 'es', 'das', 'der',
    'die', 'und', 'oder', 'aber', 'ist', 'nicht', 'mal', 'so', 'was', 'wie', 'wo', 'wann', 'schon',
    'noch', 'jetzt', 'heute', 'morgen', 'haben', 'sein', 'machen', 'gehen', 'kommen', 'sehen',
    'eins', 'zwei', 'drei', 'zehn', 'uhr', 'mit', 'von', 'zu', 'in', 'an', 'auch', 'nur', 'sehr',
)

UNKNOWN_TOKEN = '[unk]'
RECOGNIZER_WORDS = (*VOICE_KEYWORDS, *FILLER_WORDS)


@dataclass(frozen=True)
class RecognizedWord:
    """Ein von Vosk erkanntes Wort mit Sicherheit (0 bis 1)."""

    text: str
    confidence: float


def find_command(text: str, keywords: Dict[str, Command] = VOICE_KEYWORDS) -> Optional[Command]:
    """Befehl, wenn der Text genau aus einem Befehlswort besteht, sonst None."""
    words = text.lower().split()
    if len(words) != 1:
        return None
    return keywords.get(words[0])


def command_in_utterance(words: Sequence[RecognizedWord], min_confidence: float,
                         keywords: Dict[str, Command] = VOICE_KEYWORDS) -> Optional[Command]:
    """Befehl, wenn die Aeusserung aus genau einem sicher erkannten Befehlswort besteht."""
    if len(words) != 1 or words[0].confidence < min_confidence:
        return None
    return find_command(words[0].text, keywords)


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
