"""Tests fuer Gestenklassifikation, Glaettung und den Gesamtablauf Bild -> Befehl."""

from hand_samples import (
    FIST,
    L_SHAPE,
    OPEN_PALM,
    PEACE_SIGN,
    POINTING_DOWN,
    POINTING_SIDEWAYS,
    POINTING_UP,
)
import numpy as np
from pren_perception.commands import Command
from pren_perception.gesture.gesture_command_detector import GestureCommandDetector
from pren_perception.gesture.gesture_debouncer import GestureDebouncer
from pren_perception.gesture.hand_gesture_classifier import classify_hand, HandGesture
import pytest

UP, DOWN, PALM, NONE = (HandGesture.POINTING_UP, HandGesture.POINTING_DOWN,
                        HandGesture.OPEN_PALM, HandGesture.NONE)

# ----------------------------------------------------------- Klassifikation


@pytest.mark.parametrize('landmarks, gesture, command', [
    (OPEN_PALM, PALM, Command.SITZ),
    (POINTING_UP, UP, Command.AUF),
    (L_SHAPE, UP, Command.AUF),
    (POINTING_DOWN, DOWN, Command.PLATZ),
])
def test_recognizes_task_gestures(landmarks, gesture, command):
    result = classify_hand(landmarks)

    assert result.gesture is gesture
    assert result.gesture.command is command
    assert result.confidence >= 0.85


def test_l_shape_is_described_as_such():
    assert '(L)' in classify_hand(L_SHAPE).description


@pytest.mark.parametrize('landmarks', [FIST, PEACE_SIGN, POINTING_SIDEWAYS])
def test_rejects_other_hand_shapes(landmarks):
    assert classify_hand(landmarks).gesture is NONE


def test_rejects_incomplete_hand():
    assert classify_hand(OPEN_PALM[:10]).gesture is NONE


# ---------------------------------------------------------------- Glaettung

def test_single_wrong_frame_does_not_trigger():
    debouncer = GestureDebouncer(window_size=5, min_agreeing=4)
    results = [debouncer.update(g, now=i * 0.1) for i, g in enumerate([NONE] * 4 + [UP])]

    assert results == [None] * 5


def test_triggers_once_after_enough_agreeing_frames():
    debouncer = GestureDebouncer(window_size=5, min_agreeing=4, cooldown_s=1.0)

    results = [debouncer.update(UP, now=0.0) for _ in range(5)]

    assert results == [None, None, None, UP, None]


def test_held_gesture_triggers_again_after_cooldown():
    debouncer = GestureDebouncer(window_size=5, min_agreeing=4, cooldown_s=1.0)
    for _ in range(4):
        debouncer.update(UP, now=0.0)

    assert debouncer.update(UP, now=0.5) is None
    assert debouncer.update(UP, now=1.2) is UP


def test_new_gesture_triggers_without_waiting_for_cooldown():
    debouncer = GestureDebouncer(window_size=5, min_agreeing=4, cooldown_s=10.0)
    for _ in range(4):
        debouncer.update(UP, now=0.0)

    results = [debouncer.update(DOWN, now=0.1) for _ in range(4)]

    assert results[-1] is DOWN


def test_reset_forgets_history():
    debouncer = GestureDebouncer(window_size=5, min_agreeing=4)
    for _ in range(3):
        debouncer.update(UP, now=0.0)

    debouncer.reset()

    assert debouncer.update(UP, now=0.0) is None


# ------------------------------------------------------------ Gesamtablauf

def test_detector_turns_frames_into_one_command():
    detector = GestureCommandDetector(find_hands=lambda image: [POINTING_DOWN],
                                      debouncer=GestureDebouncer())
    image = np.zeros((48, 64, 3), dtype=np.uint8)

    commands = [detector.process(image, now=i * 0.05) for i in range(6)]

    assert [c for c in commands if c is not None] == [Command.PLATZ]
    assert detector.last_result.gesture is DOWN


def test_detector_ignores_frames_without_hand():
    detector = GestureCommandDetector(find_hands=lambda image: [],
                                      debouncer=GestureDebouncer())

    commands = [detector.process(np.zeros((4, 4, 3), np.uint8), now=i) for i in range(6)]

    assert commands == [None] * 6
    assert detector.last_result.gesture is NONE


def test_detector_prefers_most_confident_hand():
    detector = GestureCommandDetector(find_hands=lambda image: [FIST, OPEN_PALM],
                                      debouncer=GestureDebouncer(min_agreeing=1))

    assert detector.process(np.zeros((4, 4, 3), np.uint8), now=0.0) is Command.SITZ
