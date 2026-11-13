"""Duenne Huelle um Vosk: erkennt nur die vorgegebenen Woerter (Grammatik)."""

import json
from pathlib import Path
from typing import Iterable

from pren_perception.voice.keyword_spotter import UNKNOWN_TOKEN
from vosk import KaldiRecognizer, Model, SetLogLevel


class VoskRecognizer:
    """Offline-Spracherkennung, beschraenkt auf eine Wortliste."""

    def __init__(self, model_path: Path, sample_rate: int, words: Iterable[str]):
        if not model_path.is_dir():
            raise FileNotFoundError(f'Vosk-Modell nicht gefunden: {model_path}')
        SetLogLevel(-1)
        grammar = json.dumps([*words, UNKNOWN_TOKEN])
        self._recognizer = KaldiRecognizer(Model(str(model_path)), sample_rate, grammar)
        self._recognizer.SetWords(False)

    def accept(self, chunk: bytes) -> str:
        """Gibt einen Audioblock hinein und liefert den bisher erkannten Text."""
        if self._recognizer.AcceptWaveform(chunk):
            return json.loads(self._recognizer.Result()).get('text', '')
        return json.loads(self._recognizer.PartialResult()).get('partial', '')

    def finish(self) -> str:
        """Schliesst die Aeusserung ab und liefert den endgueltigen Text."""
        return json.loads(self._recognizer.Result()).get('text', '')

    def reset(self) -> None:
        """Verwirft alles bisher Gehoerte."""
        self._recognizer.Reset()
