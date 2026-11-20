"""
Prueft die Spracherkennung mit echtem Vosk-Modell und Testaufnahmen.

Die Aufnahmen liegen unter test/data/voice (erzeugt mit generate_samples.ps1):
    commands/     ein Befehlswort, langsam/normal/schnell gesprochen -> genau dieser Befehl
    distractors/  einzelne Woerter, die kein Sprachbefehl sind      -> kein Befehl
    background/   ganze Saetze, teils mit Befehlswoertern darin       -> kein Befehl

Ohne Vosk-Modell werden die Tests uebersprungen.
"""

from pathlib import Path
import wave

import numpy as np
from pren_perception.commands import Command
from pren_perception.voice.keyword_spotter import RECOGNIZER_WORDS, RepeatFilter
from pren_perception.voice.noise_gate import NoiseGate
from pren_perception.voice.voice_command_detector import VoiceCommandDetector
import pytest
from test_vosk_recognizer import MODEL

DATA = Path(__file__).parent / 'data' / 'voice'
CHUNK = 1600
SPEECH_PEAK = 12000     # Lautstaerke wie bei deutlichem Sprechen vor dem Mikrofon

pytestmark = pytest.mark.skipif(MODEL is None, reason='Vosk-Modell nicht vorhanden')


def recording(path: Path, pause_s: float = 1.0, noise_rms: float = 0.0) -> np.ndarray:
    """Aufnahme mit Pause davor und danach, auf Sprechlautstaerke, optional mit Rauschen."""
    with wave.open(str(path)) as wav:
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
    samples = samples.astype(np.float32) / max(1.0, float(np.abs(samples).max())) * SPEECH_PEAK
    pause = np.zeros(int(16000 * pause_s), dtype=np.float32)
    audio = np.concatenate([pause, samples, pause])
    audio += np.random.default_rng(17).normal(0.0, noise_rms, audio.size)
    return np.clip(audio, -32768, 32767).astype(np.int16)


@pytest.fixture(scope='module')
def recognizer():
    from pren_perception.voice.vosk_recognizer import VoskRecognizer
    return VoskRecognizer(MODEL, 16000, RECOGNIZER_WORDS)


def detect(recognizer, audio: np.ndarray) -> list:
    """Alle Befehle, die der Detektor in der Aufnahme meldet."""
    recognizer.reset()
    detector = VoiceCommandDetector(recognizer, NoiseGate(750.0), RepeatFilter(1.5))
    commands = []
    for index in range(0, len(audio), CHUNK):
        command = detector.process(audio[index:index + CHUNK].tobytes(), now=index / 16000)
        if command is not None:
            commands.append(command)
    return commands


def files(folder: str):
    return sorted((DATA / folder).glob('*.wav'), key=lambda p: p.name)


@pytest.mark.parametrize('noise_rms', [0.0, 400.0], ids=['ruhig', 'rauschen'])
@pytest.mark.parametrize('path', files('commands'), ids=lambda p: p.stem)
def test_spoken_command_is_recognized_once(recognizer, path, noise_rms):
    expected = Command[path.stem.split('_')[0].upper()]

    assert detect(recognizer, recording(path, noise_rms=noise_rms)) == [expected]


def test_command_is_reported_within_one_second_after_speaking(recognizer):
    path = DATA / 'commands' / 'such_rate0.wav'
    audio = recording(path, pause_s=1.0)
    with wave.open(str(path)) as wav:
        speech_end_s = 1.0 + wav.getnframes() / 16000

    recognizer.reset()
    detector = VoiceCommandDetector(recognizer, NoiseGate(750.0), RepeatFilter(1.5))
    for index in range(0, len(audio), CHUNK):
        now = (index + CHUNK) / 16000
        if detector.process(audio[index:index + CHUNK].tobytes(), now) is not None:
            break

    assert now - speech_end_s < 1.0


@pytest.mark.parametrize('path', files('distractors'), ids=lambda p: p.stem)
def test_single_non_command_word_is_ignored(recognizer, path):
    assert detect(recognizer, recording(path)) == []


@pytest.mark.parametrize('noise_rms', [0.0, 400.0], ids=['ruhig', 'rauschen'])
@pytest.mark.parametrize('path', files('background'), ids=lambda p: p.stem)
def test_conversation_is_ignored(recognizer, path, noise_rms):
    assert detect(recognizer, recording(path, noise_rms=noise_rms)) == []


def test_command_right_after_conversation_is_recognized(recognizer):
    audio = np.concatenate([recording(DATA / 'background' / 'satz_06.wav'),
                            recording(DATA / 'commands' / 'sitz_rate0.wav')])

    assert detect(recognizer, audio) == [Command.SITZ]


def test_all_commands_in_a_row(recognizer):
    audio = np.concatenate([recording(DATA / 'commands' / f'{word}_rate0.wav')
                            for word in ('such', 'hier', 'brav', 'sitz')])

    assert detect(recognizer, audio) == [Command.SUCH, Command.HIER, Command.BRAV, Command.SITZ]
