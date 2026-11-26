"""Tests fuer die Reaktion des Hundes auf Befehle."""

from pren_behavior.commands import Command, CommandSource, is_allowed
from pren_behavior.dog_state_machine import (
    BehaviorParameters,
    DogSignal,
    DogState,
    DogStateMachine,
    Posture,
)
from pren_behavior.motion import NO_BONE, STOP
import pytest

from simulated_world import SimulatedWorld, START_POSE

VOICE = CommandSource.VOICE
GESTURE = CommandSource.GESTURE
GUI = CommandSource.GUI
DT = 0.05


def run(machine: DogStateMachine, world: SimulatedWorld, seconds: float, start: float = 0.0):
    """Ruft update() fuer die angegebene Zeit auf und sammelt alle Signale."""
    signals = []
    now = start
    while now < start + seconds:
        output = machine.update(world.pose, world.observe_bone(), now)
        signals.extend(output.signals)
        world.drive(output.velocity, DT)
        now += DT
    return signals


# --------------------------------------------------------------- Quellen

@pytest.mark.parametrize('command', [Command.HIER, Command.BRAV, Command.SITZ, Command.SUCH])
def test_voice_may_give_voice_commands(command):
    assert is_allowed(command, VOICE)


@pytest.mark.parametrize('command', [Command.SITZ, Command.PLATZ, Command.AUF])
def test_gesture_may_give_gesture_commands(command):
    assert is_allowed(command, GESTURE)


@pytest.mark.parametrize('command, source', [
    (Command.PLATZ, VOICE), (Command.AUF, VOICE),
    (Command.SUCH, GESTURE), (Command.HIER, GESTURE), (Command.BRAV, GESTURE),
])
def test_rejects_command_from_wrong_source(command, source):
    machine = DogStateMachine()

    result = machine.handle_command(command, source)

    assert not result.accepted
    assert machine.state is DogState.STANDING
    assert machine.last_command is None


def test_accepts_any_source_when_source_check_disabled():
    machine = DogStateMachine(BehaviorParameters(enforce_command_sources=False))

    assert machine.handle_command(Command.PLATZ, VOICE).accepted
    assert machine.posture is Posture.LIE


# ------------------------------------------------------------- Haltungen

@pytest.mark.parametrize('command, source, state, posture', [
    (Command.SITZ, VOICE, DogState.SITTING, Posture.SIT),
    (Command.SITZ, GESTURE, DogState.SITTING, Posture.SIT),
    (Command.PLATZ, GESTURE, DogState.LYING, Posture.LIE),
    (Command.AUF, GESTURE, DogState.STANDING, Posture.STAND),
])
def test_posture_commands_change_posture_and_keep_robot_still(command, source, state, posture):
    machine = DogStateMachine()
    machine.handle_command(Command.PLATZ, GESTURE)

    assert machine.handle_command(command, source).accepted
    output = machine.update(START_POSE, NO_BONE, 0.0)

    assert machine.state is state
    assert output.posture is posture
    assert output.velocity == STOP
    assert machine.last_command is command
    assert machine.last_command_source is source


def test_brav_sends_praise_once_and_keeps_state():
    machine = DogStateMachine()
    machine.handle_command(Command.SITZ, VOICE)

    machine.handle_command(Command.BRAV, VOICE)
    first = machine.update(START_POSE, NO_BONE, 0.0)
    second = machine.update(START_POSE, NO_BONE, 0.05)

    assert first.signals == (DogSignal.PRAISE,)
    assert second.signals == ()
    assert machine.state is DogState.SITTING


# ------------------------------------------------------------------ HIER

def test_hier_drives_towards_person_and_stands_afterwards():
    machine = DogStateMachine()
    world = SimulatedWorld()

    machine.handle_command(Command.HIER, VOICE)
    assert machine.state is DogState.COMING
    run(machine, world, seconds=10.0)

    travelled = world.pose.distance_to(START_POSE)
    assert travelled == pytest.approx(BehaviorParameters().come_here.distance_m, abs=0.02)
    assert world.pose.x < 0.0  # in Blickrichtung, also zum Schiedsrichter hin
    assert machine.state is DogState.STANDING


def test_hier_from_sitting_stands_up_first():
    machine = DogStateMachine()
    machine.handle_command(Command.SITZ, VOICE)

    machine.handle_command(Command.HIER, VOICE)

    assert machine.posture is Posture.STAND


def test_sitz_interrupts_hier():
    machine = DogStateMachine()
    world = SimulatedWorld()
    machine.handle_command(Command.HIER, VOICE)
    run(machine, world, seconds=0.5)

    machine.handle_command(Command.SITZ, GESTURE)
    output = machine.update(world.pose, NO_BONE, 1.0)

    assert machine.state is DogState.SITTING
    assert output.velocity == STOP


# ------------------------------------------------------------------ SUCH

def test_such_runs_complete_mission_with_bark_and_final_signal():
    machine = DogStateMachine()
    world = SimulatedWorld(bone_x=3.0, bone_y=0.3)

    machine.handle_command(Command.SUCH, VOICE)
    assert machine.is_busy
    signals = run(machine, world, seconds=60.0)

    assert signals == [DogSignal.BARK, DogSignal.MISSION_COMPLETE]
    assert machine.state is DogState.SITTING
    assert machine.posture is Posture.SIT
    assert not machine.is_busy


def test_search_ends_sitting_in_the_same_step_as_the_final_signal():
    """Anforderung 5.8: Ende sitzend mit Ton, Haltung und Ton kommen zusammen."""
    machine = DogStateMachine()
    world = SimulatedWorld(bone_x=3.0, bone_y=0.3)
    machine.handle_command(Command.SUCH, VOICE)

    final = None
    for step in range(int(60.0 / DT)):
        output = machine.update(world.pose, world.observe_bone(), step * DT)
        world.drive(output.velocity, DT)
        if DogSignal.MISSION_COMPLETE in output.signals:
            final = output
            break

    assert final is not None
    assert final.posture is Posture.SIT
    assert final.velocity == STOP
    assert final.signals.count(DogSignal.MISSION_COMPLETE) == 1


def test_search_without_bone_also_ends_sitting():
    machine = DogStateMachine()
    world = SimulatedWorld(bone_x=50.0, bone_y=50.0)   # Knochen ausserhalb des Suchbereichs
    machine.handle_command(Command.SUCH, VOICE)
    signals = run(machine, world, seconds=90.0)

    assert signals == [DogSignal.MISSION_COMPLETE]
    assert machine.state is DogState.SITTING


def test_dog_stands_up_with_auf_after_search():
    machine = DogStateMachine()
    world = SimulatedWorld(bone_x=2.0, bone_y=0.0)
    machine.handle_command(Command.SUCH, VOICE)
    run(machine, world, seconds=60.0)

    assert machine.handle_command(Command.AUF, GESTURE).accepted
    assert machine.posture is Posture.STAND


@pytest.mark.parametrize('command, source', [
    (Command.SITZ, VOICE), (Command.PLATZ, GESTURE), (Command.HIER, VOICE),
    (Command.SUCH, VOICE), (Command.BRAV, VOICE),
])
def test_all_commands_are_ignored_while_searching(command, source):
    machine = DogStateMachine()
    world = SimulatedWorld()
    machine.handle_command(Command.SUCH, VOICE)
    run(machine, world, seconds=1.0)

    result = machine.handle_command(command, source)

    assert not result.accepted
    assert machine.state is DogState.SEARCHING
    assert machine.last_command is Command.SUCH


def test_commands_are_accepted_again_after_search():
    machine = DogStateMachine()
    world = SimulatedWorld(bone_x=2.0, bone_y=0.0)
    machine.handle_command(Command.SUCH, VOICE)
    run(machine, world, seconds=60.0)

    assert machine.handle_command(Command.SITZ, VOICE).accepted


def test_activity_describes_search_phase():
    machine = DogStateMachine()
    machine.handle_command(Command.SUCH, VOICE)
    machine.update(START_POSE, NO_BONE, 0.0)

    assert machine.activity == 'Zum Suchbereich drehen'


# ----------------------------------------------------------------- Reset

def test_reset_aborts_search_and_returns_to_standing():
    machine = DogStateMachine()
    world = SimulatedWorld()
    machine.handle_command(Command.SUCH, VOICE)
    run(machine, world, seconds=2.0)

    machine.reset()
    output = machine.update(world.pose, NO_BONE, 3.0)

    assert machine.state is DogState.STANDING
    assert not machine.is_busy
    assert machine.last_command is None
    assert output.velocity == STOP
    assert output.signals == ()
