"""
Verbindet Rauschfilter, Spracherkennung und Befehlsentscheidung zu einem Ablauf.

Pro Audioblock (100 ms) wird process() aufgerufen. Alles, was waehrend einer Aeusserung
erkannt wird, wird gesammelt. Erst wenn die Aeusserung zu Ende ist (Rauschfilter meldet
Stille), wird entschieden, ob sie ein Befehl war. Zu lange Aeusserungen sind Gespraeche
und werden verworfen.
"""

from typing import List, Optional, Protocol

from pren_perception.commands import Command
from pren_perception.voice.keyword_spotter import (
    command_in_utterance,
    RecognizedWord,
    RepeatFilter,
)
from pren_perception.voice.noise_gate import NoiseGate

CHUNK_DURATION_S = 0.1


class Recognizer(Protocol):
    """Schnittstelle der Spracherkennung (z. B. VoskRecognizer)."""

    def accept(self, chunk: bytes) -> List[RecognizedWord]: ...  # noqa: D102, E704

    def finish(self) -> List[RecognizedWord]: ...  # noqa: D102, E704

    def reset(self) -> None: ...  # noqa: D102, E704


class VoiceCommandDetector:
    """Macht aus Audiobloecken erkannte Befehle."""

    def __init__(self, recognizer: Recognizer, gate: NoiseGate, repeat_filter: RepeatFilter,
                 min_confidence: float = 0.7, max_utterance_s: float = 2.0):
        self._recognizer = recognizer
        self._gate = gate
        self._repeat_filter = repeat_filter
        self._min_confidence = min_confidence
        self._max_utterance_s = max_utterance_s
        self._words: List[RecognizedWord] = []
        self._utterance_chunks = 0
        self.last_level = 0.0
        self.last_rejected: List[RecognizedWord] = []

    def process(self, chunk: bytes, now: float) -> Optional[Command]:
        """Verarbeitet einen Audioblock. Gibt einen neu erkannten Befehl zurueck."""
        decision = self._gate.process(chunk)
        self.last_level = decision.level

        for part in decision.chunks_to_recognize:
            self._words.extend(self._recognizer.accept(part))
            self._utterance_chunks += 1

        if not decision.utterance_ended:
            return None
        self._words.extend(self._recognizer.finish())
        return self._decide(now)

    def _decide(self, now: float) -> Optional[Command]:
        words, duration = self._words, self._utterance_chunks * CHUNK_DURATION_S
        self._words, self._utterance_chunks = [], 0
        self._recognizer.reset()

        command = None
        if duration <= self._max_utterance_s:
            command = command_in_utterance(words, self._min_confidence)
        if command is None:
            self.last_rejected = words
            return None
        return command if self._repeat_filter.accept(command, now) else None
