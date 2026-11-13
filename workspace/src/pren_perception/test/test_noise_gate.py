"""Tests fuer den Rauschfilter vor der Spracherkennung."""

from audio_samples import chunk_with_level, LOUD, QUIET
from pren_perception.voice.noise_gate import NoiseGate, rms_level
import pytest

THRESHOLD = 750.0


def test_rms_level_of_known_signal():
    assert rms_level(chunk_with_level(1234.0)) == pytest.approx(1234.0, abs=1.0)


def test_rms_level_of_empty_chunk_is_zero():
    assert rms_level(b'') == 0.0


def test_quiet_audio_is_not_recognized():
    gate = NoiseGate(THRESHOLD)
    for _ in range(10):
        result = gate.process(QUIET)
        assert result.chunks_to_recognize == ()
        assert not result.utterance_ended
    assert not gate.is_open


def test_loud_audio_is_recognized_with_pre_roll():
    gate = NoiseGate(THRESHOLD, pre_roll_chunks=2)
    before = [chunk_with_level(100.0 + i) for i in range(3)]
    for chunk in before:
        gate.process(chunk)

    result = gate.process(LOUD)

    assert result.chunks_to_recognize == (before[1], before[2], LOUD)
    assert gate.is_open


def test_pre_roll_is_only_sent_once_per_utterance():
    gate = NoiseGate(THRESHOLD, pre_roll_chunks=2)
    gate.process(QUIET)
    gate.process(LOUD)

    assert gate.process(LOUD).chunks_to_recognize == (LOUD,)


def test_utterance_ends_after_hangover():
    gate = NoiseGate(THRESHOLD, hangover_chunks=2)
    gate.process(LOUD)

    assert gate.process(QUIET).chunks_to_recognize == (QUIET,)
    assert gate.process(QUIET).chunks_to_recognize == (QUIET,)
    final = gate.process(QUIET)

    assert final.utterance_ended
    assert final.chunks_to_recognize == ()
    assert not gate.is_open


def test_short_pause_keeps_utterance_open():
    gate = NoiseGate(THRESHOLD, hangover_chunks=2)
    gate.process(LOUD)
    gate.process(QUIET)

    result = gate.process(LOUD)

    assert not result.utterance_ended
    assert gate.is_open
