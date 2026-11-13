"""
Ablauf des Befehls SUCH: Knochen im Suchbereich finden und ins Startfeld zurueckkehren.

Der Ablauf ist unabhaengig von ROS. Er bekommt Pose, Knochenbeobachtung und Zeit
herein und gibt einen Fahrbefehl sowie Ereignisse (Knochen gefunden, fertig) zurueck.

Ablauf:
    1. Um 180 Grad zum Suchbereich drehen.
    2. Den Suchbereich in Schlangenlinien abfahren, bis der Knochen gesehen wird.
    3. Auf den Knochen zufahren, bis der Kontaktabstand erreicht ist.
    4. Kurz anhalten und bellen.
    5. Zurueck zur Startposition fahren.
    6. Wieder zum Schiedsrichter drehen.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import List, Tuple

from pren_behavior.motion import (
    BoneObservation,
    clamp,
    normalize_angle,
    Pose2D,
    STOP,
    turn_towards,
    Velocity,
)


class SearchPhase(Enum):
    """Phasen der Suche mit lesbarer Beschreibung."""

    TURN_TO_SEARCH_AREA = 'Zum Suchbereich drehen'
    SWEEP_SEARCH_AREA = 'Suchbereich absuchen'
    APPROACH_BONE = 'Knochen anfahren'
    CELEBRATE = 'Knochen gefunden'
    RETURN_HOME = 'Zurueck zum Startfeld fahren'
    FACE_REFEREE = 'Zum Schiedsrichter drehen'
    FINISHED = 'Suche abgeschlossen'


class SearchEvent(Enum):
    """Einmalige Ereignisse waehrend der Suche."""

    BONE_FOUND = 'bone_found'
    BONE_NOT_FOUND = 'bone_not_found'
    MISSION_COMPLETE = 'mission_complete'


@dataclass(frozen=True)
class SearchParameters:
    """Einstellbare Werte der Suche. Standardwerte entsprechen dem Simulationsstand."""

    search_speed: float = 0.36             # m/s beim Absuchen und Anfahren
    return_speed: float = 0.44             # m/s bei der Rueckfahrt
    approach_min_speed: float = 0.12       # m/s, langsamste Anfahrt
    max_turn_rate: float = 2.0             # rad/s
    sweep_amplitude_rad: float = math.radians(18.0)
    sweep_period_s: float = 3.0
    search_area_length_m: float = 4.6      # danach wird ohne Fund umgekehrt
    contact_distance_m: float = 0.32       # Abstand, ab dem der Knochen als erreicht gilt
    bone_lost_timeout_s: float = 1.5       # so lange darf der Knochen beim Anfahren fehlen
    celebrate_duration_s: float = 2.2
    home_tolerance_m: float = 0.15
    turn_tolerance_rad: float = math.radians(5.0)
    face_referee_tolerance_rad: float = math.radians(10.0)
    return_turn_in_place_rad: float = math.radians(25.0)


@dataclass(frozen=True)
class SearchStep:
    """Ergebnis eines Regelschritts."""

    velocity: Velocity
    events: Tuple[SearchEvent, ...] = ()


class SearchMission:
    """Fuehrt eine einzelne Suche vom Startfeld bis zur Rueckkehr aus."""

    def __init__(self, start_pose: Pose2D, now: float, params: SearchParameters):
        self._params = params
        self._start_pose = start_pose
        # Der Hund steht mit Blick zum Schiedsrichter, der Suchbereich liegt hinter ihm.
        self._search_heading = normalize_angle(start_pose.yaw + math.pi)
        self._phase = SearchPhase.TURN_TO_SEARCH_AREA
        self._phase_started_at = now
        self._bone_last_seen_at = now
        self._events: List[SearchEvent] = []

    @property
    def phase(self) -> SearchPhase:
        """Aktuelle Phase der Suche."""
        return self._phase

    @property
    def is_finished(self) -> bool:
        """Melde, ob der Hund wieder im Startfeld zum Schiedsrichter schaut."""
        return self._phase is SearchPhase.FINISHED

    def update(self, pose: Pose2D, bone: BoneObservation, now: float) -> SearchStep:
        """Berechnet den Fahrbefehl fuer den aktuellen Zeitpunkt."""
        self._events = []
        handlers = {
            SearchPhase.TURN_TO_SEARCH_AREA: self._turn_to_search_area,
            SearchPhase.SWEEP_SEARCH_AREA: self._sweep_search_area,
            SearchPhase.APPROACH_BONE: self._approach_bone,
            SearchPhase.CELEBRATE: self._celebrate,
            SearchPhase.RETURN_HOME: self._return_home,
            SearchPhase.FACE_REFEREE: self._face_referee,
            SearchPhase.FINISHED: lambda *_: STOP,
        }
        velocity = handlers[self._phase](pose, bone, now)
        return SearchStep(velocity=velocity, events=tuple(self._events))

    # ------------------------------------------------------------------ Phasen

    def _turn_to_search_area(self, pose: Pose2D, bone: BoneObservation, now: float) -> Velocity:
        heading_error = normalize_angle(self._search_heading - pose.yaw)
        if abs(heading_error) < self._params.turn_tolerance_rad:
            self._enter(SearchPhase.SWEEP_SEARCH_AREA, now)
            return STOP
        return Velocity(angular=turn_towards(pose.yaw, self._search_heading, 2.5,
                                             self._params.max_turn_rate))

    def _sweep_search_area(self, pose: Pose2D, bone: BoneObservation, now: float) -> Velocity:
        if bone.detected:
            self._bone_last_seen_at = now
            self._enter(SearchPhase.APPROACH_BONE, now)
            return STOP
        if self._distance_into_search_area(pose) > self._params.search_area_length_m:
            self._events.append(SearchEvent.BONE_NOT_FOUND)
            self._enter(SearchPhase.RETURN_HOME, now)
            return STOP

        elapsed = now - self._phase_started_at
        sweep_offset = self._params.sweep_amplitude_rad * math.sin(
            2.0 * math.pi * elapsed / self._params.sweep_period_s)
        target_yaw = self._search_heading + sweep_offset
        return Velocity(
            linear=self._params.search_speed,
            angular=turn_towards(pose.yaw, target_yaw, 3.0, self._params.max_turn_rate),
        )

    def _approach_bone(self, pose: Pose2D, bone: BoneObservation, now: float) -> Velocity:
        if not bone.detected:
            if now - self._bone_last_seen_at > self._params.bone_lost_timeout_s:
                self._enter(SearchPhase.SWEEP_SEARCH_AREA, now)
                return STOP
            # Kurz aus dem Blick: langsam geradeaus weiter.
            return Velocity(linear=self._params.approach_min_speed)

        self._bone_last_seen_at = now
        if bone.distance_m <= self._params.contact_distance_m:
            self._events.append(SearchEvent.BONE_FOUND)
            self._enter(SearchPhase.CELEBRATE, now)
            return STOP

        remaining = bone.distance_m - self._params.contact_distance_m
        speed = min(self._params.search_speed,
                    max(self._params.approach_min_speed, 0.4 * remaining + 0.12))
        return Velocity(linear=speed,
                        angular=clamp(3.5 * bone.bearing_rad, self._params.max_turn_rate))

    def _celebrate(self, pose: Pose2D, bone: BoneObservation, now: float) -> Velocity:
        if now - self._phase_started_at >= self._params.celebrate_duration_s:
            self._enter(SearchPhase.RETURN_HOME, now)
        return STOP

    def _return_home(self, pose: Pose2D, bone: BoneObservation, now: float) -> Velocity:
        distance_home = pose.distance_to(self._start_pose)
        if distance_home <= self._params.home_tolerance_m:
            self._enter(SearchPhase.FACE_REFEREE, now)
            return STOP

        heading_home = pose.heading_to(self._start_pose)
        heading_error = normalize_angle(heading_home - pose.yaw)
        if abs(heading_error) > self._params.return_turn_in_place_rad:
            return Velocity(angular=turn_towards(pose.yaw, heading_home, 3.0,
                                                 self._params.max_turn_rate))

        speed = min(self._params.return_speed,
                    max(self._params.approach_min_speed, 0.5 * distance_home + 0.10))
        return Velocity(linear=speed, angular=turn_towards(pose.yaw, heading_home, 2.5, 1.5))

    def _face_referee(self, pose: Pose2D, bone: BoneObservation, now: float) -> Velocity:
        referee_heading = self._start_pose.yaw
        if abs(normalize_angle(referee_heading - pose.yaw)) < \
                self._params.face_referee_tolerance_rad:
            self._events.append(SearchEvent.MISSION_COMPLETE)
            self._enter(SearchPhase.FINISHED, now)
            return STOP
        return Velocity(angular=turn_towards(pose.yaw, referee_heading, 2.5, 1.8))

    # --------------------------------------------------------------- Hilfen

    def _enter(self, phase: SearchPhase, now: float) -> None:
        self._phase = phase
        self._phase_started_at = now

    def _distance_into_search_area(self, pose: Pose2D) -> float:
        """Wie weit der Hund entlang der Suchrichtung vom Start entfernt ist."""
        dx = pose.x - self._start_pose.x
        dy = pose.y - self._start_pose.y
        return dx * math.cos(self._search_heading) + dy * math.sin(self._search_heading)
