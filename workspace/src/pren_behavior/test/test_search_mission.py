"""Tests fuer den SUCH-Ablauf mit einer simulierten Welt."""

import math

from pren_behavior.motion import BoneObservation, normalize_angle, Pose2D
from pren_behavior.search_mission import (
    SearchEvent,
    SearchMission,
    SearchParameters,
    SearchPhase,
)
import pytest

from simulated_world import SimulatedWorld, START_POSE

DT = 0.05


def run_mission(world: SimulatedWorld, params=SearchParameters(), max_seconds=120.0):
    """Faehrt die Suche in der Welt durch und sammelt Phasen und Ereignisse."""
    mission = SearchMission(world.pose, 0.0, params)
    phases, events = [mission.phase], []
    now = 0.0
    while not mission.is_finished and now < max_seconds:
        step = mission.update(world.pose, world.observe_bone(), now)
        events.extend(step.events)
        if mission.phase is not phases[-1]:
            phases.append(mission.phase)
        world.drive(step.velocity, DT)
        now += DT
    return mission, phases, events


@pytest.mark.parametrize('bone_x, bone_y', [(2.0, 0.0), (3.0, 0.4), (4.0, -0.6), (2.5, -0.5)])
def test_finds_bone_and_returns_home_facing_referee(bone_x, bone_y):
    world = SimulatedWorld(bone_x=bone_x, bone_y=bone_y)

    mission, phases, events = run_mission(world)

    assert mission.is_finished
    assert phases == [
        SearchPhase.TURN_TO_SEARCH_AREA,
        SearchPhase.SWEEP_SEARCH_AREA,
        SearchPhase.APPROACH_BONE,
        SearchPhase.CELEBRATE,
        SearchPhase.RETURN_HOME,
        SearchPhase.FACE_REFEREE,
        SearchPhase.FINISHED,
    ]
    assert events == [SearchEvent.BONE_FOUND, SearchEvent.MISSION_COMPLETE]
    assert world.pose.distance_to(START_POSE) <= SearchParameters().home_tolerance_m + 0.05
    assert abs(normalize_angle(world.pose.yaw - START_POSE.yaw)) < math.radians(10.0)


def test_stops_within_contact_distance_of_bone():
    world = SimulatedWorld(bone_x=3.0, bone_y=0.2)
    mission = SearchMission(world.pose, 0.0, SearchParameters())
    now = 0.0
    while mission.phase is not SearchPhase.CELEBRATE and now < 60.0:
        step = mission.update(world.pose, world.observe_bone(), now)
        world.drive(step.velocity, DT)
        now += DT

    distance = math.hypot(world.bone_x - world.pose.x, world.bone_y - world.pose.y)
    assert distance <= SearchParameters().contact_distance_m + 0.05


def test_returns_home_without_bark_when_no_bone_in_search_area():
    world = SimulatedWorld(bone_x=-10.0, bone_y=0.0)  # Knochen liegt nicht im Suchbereich

    mission, phases, events = run_mission(world)

    assert mission.is_finished
    assert SearchPhase.APPROACH_BONE not in phases
    assert events == [SearchEvent.BONE_NOT_FOUND, SearchEvent.MISSION_COMPLETE]


def test_first_turns_in_place_towards_search_area():
    mission = SearchMission(START_POSE, 0.0, SearchParameters())

    step = mission.update(START_POSE, BoneObservation(), 0.0)

    assert step.velocity.linear == 0.0
    assert step.velocity.angular != 0.0


def test_goes_back_to_sweeping_when_bone_lost_too_long():
    params = SearchParameters()
    mission = SearchMission(Pose2D(0.0, 0.0, 0.0), 0.0, params)  # schaut schon falsch herum
    mission._enter(SearchPhase.APPROACH_BONE, 0.0)
    mission._bone_last_seen_at = 0.0

    short_gap = mission.update(Pose2D(), BoneObservation(), params.bone_lost_timeout_s / 2)
    assert mission.phase is SearchPhase.APPROACH_BONE
    assert short_gap.velocity.linear == params.approach_min_speed

    mission.update(Pose2D(), BoneObservation(), params.bone_lost_timeout_s + 0.1)
    assert mission.phase is SearchPhase.SWEEP_SEARCH_AREA


def test_respects_speed_limits_during_whole_mission():
    params = SearchParameters()
    world = SimulatedWorld(bone_x=3.5, bone_y=0.3)
    mission = SearchMission(world.pose, 0.0, params)
    now = 0.0
    while not mission.is_finished and now < 120.0:
        step = mission.update(world.pose, world.observe_bone(), now)
        assert 0.0 <= step.velocity.linear <= max(params.search_speed, params.return_speed)
        assert abs(step.velocity.angular) <= params.max_turn_rate
        world.drive(step.velocity, DT)
        now += DT
