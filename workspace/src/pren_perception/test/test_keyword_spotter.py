"""Tests fuer Befehlssuche im Text und Wiederholungsfilter."""

from pren_perception.commands import Command
from pren_perception.voice.keyword_spotter import find_command, RepeatFilter, VOICE_KEYWORDS
import pytest


@pytest.mark.parametrize('text, command', [
    ('hier', Command.HIER), ('brav', Command.BRAV),
    ('sitz', Command.SITZ), ('such', Command.SUCH),
    ('SUCH', Command.SUCH), ('[unk] sitz', Command.SITZ), ('brav sitz', Command.BRAV),
])
def test_finds_command_in_text(text, command):
    assert find_command(text) is command


@pytest.mark.parametrize('text', ['', '[unk]', 'platz', 'auf', 'hallo welt', 'suche'])
def test_ignores_text_without_voice_command(text):
    assert find_command(text) is None


def test_voice_keywords_match_task():
    assert set(VOICE_KEYWORDS.values()) == {Command.HIER, Command.BRAV, Command.SITZ,
                                            Command.SUCH}


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
