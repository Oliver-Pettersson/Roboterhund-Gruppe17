"""
Rauschfilter: nur Audio mit genug Lautstaerke wird an die Spracherkennung weitergegeben.

Uebernommen aus prototypes/voice_detection/voice_control.py:
    * Bloecke unter der Schwelle gelten als Umgebungsgeraeusch.
    * Die letzten leisen Bloecke vor dem Sprechen werden mitgegeben (pre-roll), damit
      Anlaute wie "S" oder "H" nicht abgeschnitten werden.
    * Nach dem Sprechen werden noch einige leise Bloecke mitgegeben (hangover), dann
      gilt die Aeusserung als beendet.
"""

from collections import deque
from dataclasses import dataclass
from typing import Tuple

import numpy as np


def rms_level(pcm_chunk: bytes) -> float:
    """Lautstaerke (RMS) eines 16-Bit-PCM-Blocks."""
    samples = np.frombuffer(pcm_chunk, dtype=np.int16).astype(np.float32)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples ** 2)))


@dataclass(frozen=True)
class GateResult:
    """Was mit einem Audioblock passieren soll."""

    chunks_to_recognize: Tuple[bytes, ...]   # in dieser Reihenfolge an die Erkennung geben
    utterance_ended: bool                    # True: Aeusserung abschliessen
    level: float                             # gemessene Lautstaerke des Blocks


class NoiseGate:
    """Entscheidet pro Audioblock, ob er erkannt oder verworfen wird."""

    def __init__(self, threshold: float, hangover_chunks: int = 4, pre_roll_chunks: int = 2):
        self.threshold = threshold
        self._hangover_chunks = hangover_chunks
        self._pre_roll = deque(maxlen=pre_roll_chunks)
        self._speaking = False
        self._quiet_chunks = 0

    @property
    def is_open(self) -> bool:
        """Melde, ob gerade gesprochen wird."""
        return self._speaking

    def process(self, chunk: bytes) -> GateResult:
        """Bewertet einen Audioblock."""
        level = rms_level(chunk)

        if level >= self.threshold:
            to_recognize = tuple(self._pre_roll) if not self._speaking else ()
            self._pre_roll.clear()
            self._speaking = True
            self._quiet_chunks = 0
            return GateResult(to_recognize + (chunk,), False, level)

        if not self._speaking:
            self._pre_roll.append(chunk)
            return GateResult((), False, level)

        self._quiet_chunks += 1
        if self._quiet_chunks > self._hangover_chunks:
            self._speaking = False
            self._quiet_chunks = 0
            return GateResult((), True, level)
        return GateResult((chunk,), False, level)
