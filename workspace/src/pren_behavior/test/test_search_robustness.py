"""
Stabilitaetstest der Suche: viele zufaellige Knochenpositionen mit unsicherer Kamera.

Jeder Lauf muss den Knochen finden, genau einmal bellen, ins Startfeld zurueckkehren
und wieder zum Schiedsrichter schauen. Die Kamera rauscht und verpasst Bilder.
"""

import math
import random

from pren_behavior.motion import normalize_angle
from pren_behavior.search_mission import (
    SearchEvent,
    SearchMission,
    SearchParameters,
    SearchPhase,
)
import pytest

from simulated_world import SimulatedWorld, START_POSE

DT = 0.05
MAX_MISSION_S = 90.0
PARAMS = SearchParameters()


def random_bone(seed: int) -> tuple:
    """Knochen im Suchsektor wie in der Webots-Welt (2 bis 4 m, +-12 Grad)."""
    rng = random.Random(seed)
    distance, angle = rng.uniform(2.0, 4.0), math.radians(rng.uniform(-12.0, 12.0))
    return distance * math.cos(angle), distance * math.sin(angle)


def run(world: SimulatedWorld):
    mission = SearchMission(world.pose, 0.0, PARAMS)
    events, now, distance_at_bark = [], 0.0, None
    while not mission.is_finished and now < MAX_MISSION_S:
        step = mission.update(world.pose, world.observe_bone(), now)
        if SearchEvent.BONE_FOUND in step.events:
            distance_at_bark = math.hypot(world.bone_x - world.pose.x,
                                          world.bone_y - world.pose.y)
        events.extend(step.events)
        world.drive(step.velocity, DT)
        now += DT
    return mission, events, now, distance_at_bark


def assert_complete_mission(world, mission, events, distance_at_bark):
    assert mission.is_finished, f'Suche nicht fertig, haengt in {mission.phase.name}'
    assert events == [SearchEvent.BONE_FOUND, SearchEvent.MISSION_COMPLETE]
    assert distance_at_bark <= PARAMS.contact_distance_m + 0.1
    assert world.pose.distance_to(START_POSE) <= PARAMS.home_tolerance_m + 0.05
    assert abs(normalize_angle(world.pose.yaw - START_POSE.yaw)) <= math.radians(10.0)


@pytest.mark.parametrize('seed', range(40))
def test_finds_random_bone_with_perfect_camera(seed):
    bone_x, bone_y = random_bone(seed)
    world = SimulatedWorld(bone_x=bone_x, bone_y=bone_y)

    mission, events, _, distance_at_bark = run(world)

    assert_complete_mission(world, mission, events, distance_at_bark)


@pytest.mark.parametrize('seed', range(40))
def test_finds_random_bone_with_noisy_camera(seed):
    bone_x, bone_y = random_bone(1000 + seed)
    world = SimulatedWorld(bone_x=bone_x, bone_y=bone_y,
                           bearing_noise_rad=math.radians(3.0), distance_noise_m=0.05,
                           dropout_probability=0.3, rng=random.Random(seed))

    mission, events, _, distance_at_bark = run(world)

    assert_complete_mission(world, mission, events, distance_at_bark)


@pytest.mark.parametrize('bone', [(2.0, 0.42), (2.0, -0.42), (4.0, 0.85), (4.0, -0.85),
                                  (1.2, 0.0), (4.4, 0.0)],
                         ids=['nah_links', 'nah_rechts', 'fern_links', 'fern_rechts',
                              'sehr_nah', 'sehr_fern'])
def test_finds_bone_at_edge_of_search_sector(bone):
    world = SimulatedWorld(bone_x=bone[0], bone_y=bone[1])

    mission, events, _, distance_at_bark = run(world)

    assert_complete_mission(world, mission, events, distance_at_bark)


def test_typical_mission_is_fast_enough():
    world = SimulatedWorld(bone_x=3.0, bone_y=0.3)

    _, _, duration, _ = run(world)

    assert duration < 30.0


def test_mission_without_bone_ends_at_home_and_never_barks():
    world = SimulatedWorld(bone_x=-20.0, bone_y=0.0)

    mission, events, _, _ = run(world)

    assert mission.phase is SearchPhase.FINISHED
    assert SearchEvent.BONE_FOUND not in events
    assert world.pose.distance_to(START_POSE) <= PARAMS.home_tolerance_m + 0.05
