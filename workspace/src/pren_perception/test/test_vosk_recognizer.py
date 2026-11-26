"""Rauchtest mit dem echten Vosk-Modell. Wird uebersprungen, wenn das Modell fehlt."""

import os
from pathlib import Path

from audio_samples import QUIET
import pytest

MODEL_NAME = 'vosk-model-small-de-0.15'


def find_model():
    if os.environ.get('PREN_VOSK_MODEL'):
        return Path(os.environ['PREN_VOSK_MODEL'])
    for parent in Path(__file__).resolve().parents:
        candidate = parent / 'models' / 'voice' / MODEL_NAME
        if candidate.is_dir():
            return candidate
    return None


MODEL = find_model()


@pytest.mark.skipif(MODEL is None, reason='Vosk-Modell nicht vorhanden')
def test_model_loads_and_silence_gives_no_words():
    from pren_perception.voice.keyword_spotter import RECOGNIZER_WORDS
    from pren_perception.voice.vosk_recognizer import VoskRecognizer

    recognizer = VoskRecognizer(MODEL, 16000, RECOGNIZER_WORDS)
    words = [word for _ in range(10) for word in recognizer.accept(QUIET)]
    words += recognizer.finish()

    assert words == []


def test_missing_model_raises_clear_error(tmp_path):
    from pren_perception.voice.vosk_recognizer import VoskRecognizer

    with pytest.raises(FileNotFoundError):
        VoskRecognizer(tmp_path / 'fehlt', 16000, ['sitz'])
