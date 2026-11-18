"""Tests fuer die Befehlsentscheidung und den Wiederholungsfilter."""

from pren_perception.commands import Command
from pren_perception.voice.keyword_spotter import (
    command_in_utterance,
    FILLER_WORDS,
    find_command,
    RecognizedWord,
    RECOGNIZER_WORDS,
    RepeatFilter,
    VOICE_KEYWORDS,
)
import pytest


@pytest.mark.parametrize('text, command', [
    ('hier', Command.HIER), ('brav', Command.BRAV),
    ('sitz', Command.SITZ), ('such', Command.SUCH), ('SUCH', Command.SUCH),
])
def test_single_command_word_is_found(text, command):
    assert find_command(text) is command


@pytest.mark.parametrize('text', [
    '', '[unk]', 'platz', 'auf', 'suchen', 'hallo welt', 'brav sitz', '[unk] sitz', 'sitz sitz',
])
def test_anything_but_one_command_word_is_ignored(text):
    assert find_command(text) is None


def test_voice_keywords_match_task():
    assert set(VOICE_KEYWORDS.values()) == {Command.HIER, Command.BRAV, Command.SITZ,
                                            Command.SUCH}


def test_filler_words_never_trigger_and_do_not_overlap_commands():
    assert not set(FILLER_WORDS) & set(VOICE_KEYWORDS)
    assert all(find_command(word) is None for word in FILLER_WORDS)
    assert set(VOICE_KEYWORDS) <= set(RECOGNIZER_WORDS)


def test_utterance_with_one_confident_command_word_is_accepted():
    assert command_in_utterance([RecognizedWord('sitz', 0.95)], 0.8) is Command.SITZ


def test_unsure_command_word_is_rejected():
    assert command_in_utterance([RecognizedWord('such', 0.53)], 0.8) is None


def test_command_word_inside_sentence_is_rejected():
    words = [RecognizedWord('der', 1.0), RecognizedWord('hund', 1.0), RecognizedWord('sitz', 1.0)]
    assert command_in_utterance(words, 0.8) is None


def test_empty_utterance_is_rejected():
    assert command_in_utterance([], 0.8) is None


def test_repeat_filter_blocks_same_command_within_cooldown():
    repeat_filter = RepeatFilter(repeat_cooldown_s=1.5)

    assert repeat_filter.accept(Command.SITZ, now=0.0)
    assert not repeat_filter.accept(Command.SITZ, now=1.0)
    assert repeat_filter.accept(Command.SITZ, now=2.6)


def test_repeat_filter_lets_other_command_through_immediately():
    repeat_filter = RepeatFilter(repeat_cooldown_s=1.5)
    repeat_filter.accept(Command.SITZ, now=0.0)

    assert repeat_filter.accept(Command.BRAV, now=0.1)
    assert repeat_filter.accept(Command.SITZ, now=0.2)
