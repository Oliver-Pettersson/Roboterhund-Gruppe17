"""Tests fuer den Gesamtablauf Audio -> Befehl mit einer Platzhalter-Erkennung."""

from audio_samples import LOUD, QUIET
from pren_perception.commands import Command
from pren_perception.voice.keyword_spotter import RepeatFilter
from pren_perception.voice.noise_gate import NoiseGate
from pren_perception.voice.voice_command_detector import VoiceCommandDetector


class ScriptedRecognizer:
    """Liefert vorgegebene Texte statt echter Spracherkennung."""

    def __init__(self, partial_texts, final_text=''):
        self._partial_texts = list(partial_texts)
        self._final_text = final_text
        self.accepted_chunks = 0
        self.resets = 0

    def accept(self, chunk):
        self.accepted_chunks += 1
        return self._partial_texts.pop(0) if self._partial_texts else ''

    def finish(self):
        return self._final_text

    def reset(self):
        self.resets += 1


def make_detector(recognizer, cooldown=1.5):
    return VoiceCommandDetector(recognizer, NoiseGate(750.0, hangover_chunks=1),
                                RepeatFilter(cooldown))


def test_detects_command_from_partial_result():
    recognizer = ScriptedRecognizer(['', 'such'])
    detector = make_detector(recognizer)

    assert detector.process(LOUD, now=0.0) is None
    assert detector.process(LOUD, now=0.1) is Command.SUCH
    assert recognizer.resets == 1


def test_detects_command_at_end_of_utterance():
    detector = make_detector(ScriptedRecognizer([], final_text='hier'))
    detector.process(LOUD, now=0.0)
    detector.process(QUIET, now=0.1)

    assert detector.process(QUIET, now=0.2) is Command.HIER


def test_quiet_audio_never_reaches_recognizer():
    recognizer = ScriptedRecognizer(['sitz'] * 10)
    detector = make_detector(recognizer)

    results = [detector.process(QUIET, now=i * 0.1) for i in range(10)]

    assert results == [None] * 10
    assert recognizer.accepted_chunks == 0


def test_same_word_in_following_partials_triggers_only_once():
    detector = make_detector(ScriptedRecognizer(['sitz', 'sitz', 'sitz']))

    results = [detector.process(LOUD, now=i * 0.1) for i in range(3)]

    assert results == [Command.SITZ, None, None]


def test_unknown_words_are_ignored():
    detector = make_detector(ScriptedRecognizer(['[unk]', 'platz', 'auf']))

    assert [detector.process(LOUD, now=i * 0.1) for i in range(3)] == [None, None, None]


def test_reports_last_audio_level():
    detector = make_detector(ScriptedRecognizer([]))
    detector.process(LOUD, now=0.0)

    assert detector.last_level > 750.0
