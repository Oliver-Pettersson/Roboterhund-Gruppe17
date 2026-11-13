"""
Verbindet Rauschfilter, Spracherkennung und Befehlssuche zu einem Ablauf.

Pro Audioblock (100 ms) wird process() aufgerufen. Sobald ein Befehlswort erkannt
wird, gibt process() den Befehl einmal zurueck.
"""

from typing import Optional, Protocol

from pren_perception.commands import Command
from pren_perception.voice.keyword_spotter import find_command, RepeatFilter
from pren_perception.voice.noise_gate import NoiseGate


class Recognizer(Protocol):
    """Schnittstelle der Spracherkennung (z. B. VoskRecognizer)."""

    def accept(self, chunk: bytes) -> str: ...  # noqa: D102, E704

    def finish(self) -> str: ...  # noqa: D102, E704

    def reset(self) -> None: ...  # noqa: D102, E704


class VoiceCommandDetector:
    """Macht aus Audiobloecken erkannte Befehle."""

    def __init__(self, recognizer: Recognizer, gate: NoiseGate, repeat_filter: RepeatFilter):
        self._recognizer = recognizer
        self._gate = gate
        self._repeat_filter = repeat_filter
        self.last_level = 0.0

    def process(self, chunk: bytes, now: float) -> Optional[Command]:
        """Verarbeitet einen Audioblock. Gibt einen neu erkannten Befehl zurueck."""
        decision = self._gate.process(chunk)
        self.last_level = decision.level

        texts = [self._recognizer.accept(part) for part in decision.chunks_to_recognize]
        if decision.utterance_ended:
            texts.append(self._recognizer.finish())

        for text in texts:
            command = find_command(text)
            if command is None:
                continue
            # Nach einem Treffer neu beginnen, sonst liefert Vosk das Wort erneut.
            self._recognizer.reset()
            if self._repeat_filter.accept(command, now):
                return command
            return None
        return None
