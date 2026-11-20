"""
Stabilitaetstest der Gestenerkennung mit veraenderten Handpunkten.

Echte Handpunkte zittern von Bild zu Bild, die Hand ist mal naeher, mal weiter weg, mal
links, mal rechts im Bild, und es kann die linke oder die rechte Hand sein.
"""

import random

from hand_samples import (
    FIST,
    L_SHAPE,
    OPEN_PALM,
    PEACE_SIGN,
    Point,
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

GESTURES = [
    (OPEN_PALM, HandGesture.OPEN_PALM),
    (POINTING_UP, HandGesture.POINTING_UP),
    (L_SHAPE, HandGesture.POINTING_UP),
    (POINTING_DOWN, HandGesture.POINTING_DOWN),
]
GESTURE_IDS = ['flache_hand', 'zeigefinger_oben', 'l_form', 'zeigefinger_unten']
NOT_GESTURES = [FIST, PEACE_SIGN, POINTING_SIDEWAYS]


def jitter(hand, rng: random.Random, amount: float):
    return [Point(p.x + rng.uniform(-amount, amount), p.y + rng.uniform(-amount, amount),
                  p.z + rng.uniform(-amount, amount)) for p in hand]


def transform(hand, scale: float = 1.0, shift_x: float = 0.0, shift_y: float = 0.0,
              mirror: bool = False):
    """Hand um das Handgelenk skalieren, verschieben und optional spiegeln (linke Hand)."""
    wrist = hand[0]
    points = []
    for p in hand:
        dx = (p.x - wrist.x) * scale * (-1.0 if mirror else 1.0)
        dy = (p.y - wrist.y) * scale
        points.append(Point(wrist.x + dx + shift_x, wrist.y + dy + shift_y, p.z * scale))
    return points


@pytest.mark.parametrize('hand, gesture', GESTURES, ids=GESTURE_IDS)
def test_gesture_survives_small_jitter(hand, gesture):
    rng = random.Random(7)
    results = [classify_hand(jitter(hand, rng, 0.004)).gesture for _ in range(200)]

    assert results.count(gesture) / len(results) >= 0.95


@pytest.mark.parametrize('scale', [0.5, 0.75, 1.5])
@pytest.mark.parametrize('hand, gesture', GESTURES, ids=GESTURE_IDS)
def test_gesture_independent_of_hand_size(hand, gesture, scale):
    assert classify_hand(transform(hand, scale=scale)).gesture is gesture


@pytest.mark.parametrize('shift', [(-0.3, 0.0), (0.3, 0.0), (0.0, -0.2), (0.0, 0.15)])
@pytest.mark.parametrize('hand, gesture', GESTURES, ids=GESTURE_IDS)
def test_gesture_independent_of_position_in_image(hand, gesture, shift):
    assert classify_hand(transform(hand, shift_x=shift[0], shift_y=shift[1])).gesture is gesture


@pytest.mark.parametrize('hand, gesture', GESTURES, ids=GESTURE_IDS)
def test_left_hand_gives_same_gesture(hand, gesture):
    assert classify_hand(transform(hand, mirror=True)).gesture is gesture


@pytest.mark.parametrize('hand', NOT_GESTURES, ids=['faust', 'peace', 'seitlich'])
def test_other_hand_shapes_stay_rejected_with_jitter(hand):
    rng = random.Random(11)
    results = [classify_hand(jitter(hand, rng, 0.004)).gesture for _ in range(200)]

    assert results.count(HandGesture.NONE) / len(results) >= 0.95


def test_flickering_detection_still_gives_one_command():
    """Jedes dritte Bild findet keine Hand: die Geste wird trotzdem genau einmal gemeldet."""
    frames = iter(([POINTING_UP], [POINTING_UP], []) * 10)
    detector = GestureCommandDetector(find_hands=lambda image: next(frames),
                                      debouncer=GestureDebouncer(cooldown_s=10.0))
    image = np.zeros((4, 4, 3), np.uint8)

    commands = [detector.process(image, now=i * 0.066) for i in range(30)]

    assert [c for c in commands if c is not None] == [Command.AUF]


def test_switching_gestures_gives_each_command_once():
    sequence = [[OPEN_PALM]] * 8 + [[]] * 5 + [[POINTING_DOWN]] * 8 + [[]] * 5 + \
        [[POINTING_UP]] * 8
    frames = iter(sequence)
    detector = GestureCommandDetector(find_hands=lambda image: next(frames),
                                      debouncer=GestureDebouncer(cooldown_s=10.0))
    image = np.zeros((4, 4, 3), np.uint8)

    commands = [detector.process(image, now=i * 0.066) for i in range(len(sequence))]

    assert [c for c in commands if c is not None] == [Command.SITZ, Command.PLATZ, Command.AUF]
