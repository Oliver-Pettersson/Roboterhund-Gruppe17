"""Tests fuer den Ablauf Audio -> Befehl mit einer Platzhalter-Erkennung."""

from audio_samples import LOUD, QUIET
from pren_perception.commands import Command
from pren_perception.voice.keyword_spotter import RecognizedWord, RepeatFilter
from pren_perception.voice.noise_gate import NoiseGate
from pren_perception.voice.voice_command_detector import VoiceCommandDetector


class ScriptedRecognizer:
    """Liefert am Ende jeder Aeusserung vorgegebene Woerter statt echter Erkennung."""

    def __init__(self, *utterances):
        self._utterances = [[RecognizedWord(*word) for word in u] for u in utterances]
        self.accepted_chunks = 0
        self.resets = 0

    def accept(self, chunk):
        self.accepted_chunks += 1
        return []

    def finish(self):
        return self._utterances.pop(0) if self._utterances else []

    def reset(self):
        self.resets += 1


def make_detector(recognizer, max_utterance_s=2.0):
    return VoiceCommandDetector(recognizer, NoiseGate(750.0, hangover_chunks=1),
                                RepeatFilter(1.5), min_confidence=0.8,
                                max_utterance_s=max_utterance_s)


def speak(detector, loud_chunks, start=0.0):
    """Eine Aeusserung: laute Bloecke, dann Stille bis zum Ende. Gibt alle Ergebnisse zurueck."""
    results = []
    now = start
    for chunk in [LOUD] * loud_chunks + [QUIET] * 3:
        results.append(detector.process(chunk, now))
        now += 0.1
    return [r for r in results if r is not None]


def test_single_command_is_reported_once_at_end_of_utterance():
    detector = make_detector(ScriptedRecognizer([('such', 1.0)]))

    assert speak(detector, loud_chunks=4) == [Command.SUCH]


def test_nothing_is_reported_while_still_speaking():
    detector = make_detector(ScriptedRecognizer([('such', 1.0)]))

    assert [detector.process(LOUD, now=i * 0.1) for i in range(5)] == [None] * 5


def test_sentence_with_command_word_is_ignored():
    detector = make_detector(ScriptedRecognizer([('ich', 1.0), ('such', 1.0), ('das', 1.0)]))

    assert speak(detector, loud_chunks=10) == []
    assert [w.text for w in detector.last_rejected] == ['ich', 'such', 'das']


def test_unsure_command_is_ignored():
    detector = make_detector(ScriptedRecognizer([('hier', 0.5)]))

    assert speak(detector, loud_chunks=4) == []


def test_too_long_utterance_is_ignored():
    detector = make_detector(ScriptedRecognizer([('sitz', 1.0)]), max_utterance_s=1.0)

    assert speak(detector, loud_chunks=15) == []


def test_quiet_audio_never_reaches_recognizer():
    recognizer = ScriptedRecognizer([('sitz', 1.0)])
    detector = make_detector(recognizer)

    assert [detector.process(QUIET, now=i * 0.1) for i in range(10)] == [None] * 10
    assert recognizer.accepted_chunks == 0


def test_command_after_conversation_is_recognized():
    detector = make_detector(ScriptedRecognizer([('wir', 1.0), ('gehen', 1.0)], [('sitz', 1.0)]))

    assert speak(detector, loud_chunks=8) == []
    assert speak(detector, loud_chunks=4, start=5.0) == [Command.SITZ]


def test_same_command_twice_in_a_row_is_reported_once():
    detector = make_detector(ScriptedRecognizer([('sitz', 1.0)], [('sitz', 1.0)]))

    first = speak(detector, loud_chunks=4, start=0.0)
    second = speak(detector, loud_chunks=4, start=0.8)

    assert first + second == [Command.SITZ]


def test_reports_last_audio_level():
    detector = make_detector(ScriptedRecognizer())
    detector.process(LOUD, now=0.0)

    assert detector.last_level > 750.0
