"""Duenne Huelle um Vosk: erkennt nur die vorgegebenen Woerter und liefert ihre Sicherheit."""

import json
from pathlib import Path
from typing import Iterable, List

from pren_perception.voice.keyword_spotter import RecognizedWord, UNKNOWN_TOKEN
from vosk import KaldiRecognizer, Model, SetLogLevel


class VoskRecognizer:
    """Offline-Spracherkennung, beschraenkt auf eine Wortliste."""

    def __init__(self, model_path: Path, sample_rate: int, words: Iterable[str]):
        if not model_path.is_dir():
            raise FileNotFoundError(f'Vosk-Modell nicht gefunden: {model_path}')
        SetLogLevel(-1)
        grammar = json.dumps([*words, UNKNOWN_TOKEN])
        self._recognizer = KaldiRecognizer(Model(str(model_path)), sample_rate, grammar)
        self._recognizer.SetWords(True)

    def accept(self, chunk: bytes) -> List[RecognizedWord]:
        """Gibt einen Audioblock hinein. Liefert Woerter, sobald Vosk einen Abschnitt beendet."""
        if self._recognizer.AcceptWaveform(chunk):
            return _words(self._recognizer.Result())
        return []

    def finish(self) -> List[RecognizedWord]:
        """Schliesst die Aeusserung ab und liefert die restlichen Woerter."""
        return _words(self._recognizer.FinalResult())

    def reset(self) -> None:
        """Verwirft alles bisher Gehoerte."""
        self._recognizer.Reset()


def _words(result_json: str) -> List[RecognizedWord]:
    result = json.loads(result_json).get('result', [])
    return [RecognizedWord(item['word'], float(item.get('conf', 0.0))) for item in result]
