"""Tests fuer die Texte im Bedienfenster."""

import math

from pren_interfaces.msg import BoneDetection, DogCommand, RobotState
from pren_simulation.control_panel import describe_bone, describe_last_command, describe_state


def test_describe_state_marks_lock():
    text = describe_state(RobotState(state='SEARCHING', activity='Knochen anfahren', busy=True))
    assert text == 'SEARCHING (gesperrt): Knochen anfahren'


def test_describe_last_command():
    assert describe_last_command(RobotState()) == 'noch keiner'
    state = RobotState(last_command=DogCommand.PLATZ, last_command_source='gesture')
    assert describe_last_command(state) == 'PLATZ (gesture)'


def test_describe_bone():
    assert describe_bone(BoneDetection()) == 'nicht im Blick'
    seen = BoneDetection(detected=True, distance_m=1.5, bearing_rad=math.radians(10))
    assert describe_bone(seen) == '1.50 m, 10 Grad'
