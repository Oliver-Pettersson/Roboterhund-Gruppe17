"""
Zustandsautomat des Hundes: entscheidet, wie der Hund auf einen Befehl reagiert.

Regeln:
    * Jede Quelle darf nur die Befehle aus der Aufgabenstellung geben (abschaltbar).
    * Waehrend SUCH laeuft, werden alle anderen Befehle ignoriert.
    * Am Ende von SUCH sitzt der Hund im Startfeld und gibt den Abschlusston
      (MISSION_COMPLETE) aus (Anforderung 5.8). Danach sind Befehle wieder frei.
    * SITZ, PLATZ und AUF aendern nur die Haltung; der Hund steht still.
    * HIER faehrt ein kurzes Stueck auf die Person zu.
    * BRAV gibt ein Lob-Signal aus, der Zustand bleibt gleich.

Der Automat ist unabhaengig von ROS und wird vom dog_behavior_node regelmaessig
mit Pose, Knochenbeobachtung und Zeit aufgerufen.
"""

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import List, Optional, Tuple

from pren_behavior.come_here import ComeHereManeuver, ComeHereParameters
from pren_behavior.commands import Command, CommandSource, is_allowed
from pren_behavior.motion import BoneObservation, Pose2D, STOP, Velocity
from pren_behavior.search_mission import (
    SearchEvent,
    SearchMission,
    SearchParameters,
)


class DogState(Enum):
    """Verhaltenszustaende des Hundes."""

    STANDING = 'Steht bereit'
    SITTING = 'Sitzt'
    LYING = 'Liegt'
    COMING = 'Kommt her'
    SEARCHING = 'Sucht den Knochen'


class Posture(IntEnum):
    """Koerperhaltung. Die Werte entsprechen pren_interfaces/Posture."""

    STAND = 0
    SIT = 1
    LIE = 2


class DogSignal(IntEnum):
    """Signale nach aussen. Die Werte entsprechen pren_interfaces/DogSignal."""

    BARK = 1
    PRAISE = 2
    MISSION_COMPLETE = 3


@dataclass(frozen=True)
class CommandResult:
    """Antwort auf einen Befehl: angenommen oder mit Begruendung abgelehnt."""

    accepted: bool
    reason: str = ''


@dataclass(frozen=True)
class BehaviorOutput:
    """Was der Hund in diesem Regelschritt tun soll."""

    velocity: Velocity
    posture: Posture
    signals: Tuple[DogSignal, ...] = ()


@dataclass(frozen=True)
class BehaviorParameters:
    """Alle einstellbaren Werte des Verhaltens."""

    enforce_command_sources: bool = True
    search: SearchParameters = field(default_factory=SearchParameters)
    come_here: ComeHereParameters = field(default_factory=ComeHereParameters)


_SEARCH_EVENT_TO_SIGNAL = {
    SearchEvent.BONE_FOUND: DogSignal.BARK,
    SearchEvent.MISSION_COMPLETE: DogSignal.MISSION_COMPLETE,
}


class DogStateMachine:
    """Setzt Befehle in Zustand, Haltung, Bewegung und Signale um."""

    def __init__(self, params: Optional[BehaviorParameters] = None):
        self._params = params or BehaviorParameters()
        self.reset()

    def reset(self) -> None:
        """Bricht alles ab und kehrt in den Ausgangszustand zurueck (steht, keine Aufgabe)."""
        self._state = DogState.STANDING
        self._posture = Posture.STAND
        self._pending_signals: List[DogSignal] = []
        self._search: Optional[SearchMission] = None
        self._come_here: Optional[ComeHereManeuver] = None
        self._pending_start: Optional[Command] = None
        self.last_command: Optional[Command] = None
        self.last_command_source: Optional[CommandSource] = None

    # ------------------------------------------------------------ Zustand

    @property
    def state(self) -> DogState:
        """Aktueller Verhaltenszustand."""
        return self._state

    @property
    def posture(self) -> Posture:
        """Aktuelle Koerperhaltung."""
        return self._posture

    @property
    def is_busy(self) -> bool:
        """Melde, ob SUCH laeuft und deshalb keine anderen Befehle angenommen werden."""
        return self._state is DogState.SEARCHING

    @property
    def activity(self) -> str:
        """Lesbare Beschreibung, was der Hund gerade tut."""
        if self._search is not None:
            return self._search.phase.value
        return self._state.value

    # ----------------------------------------------------------- Befehle

    def handle_command(self, command: Command, source: CommandSource) -> CommandResult:
        """Wertet einen Befehl aus. Bewegungen starten beim naechsten update()."""
        if self.is_busy:
            return CommandResult(False, 'Suche laeuft, Befehl wird ignoriert')
        if self._params.enforce_command_sources and not is_allowed(command, source):
            return CommandResult(False, f'{command.name} ist per {source.value} nicht erlaubt')

        self.last_command = command
        self.last_command_source = source
        self._come_here = None

        if command is Command.SITZ:
            self._become(DogState.SITTING, Posture.SIT)
        elif command is Command.PLATZ:
            self._become(DogState.LYING, Posture.LIE)
        elif command is Command.AUF:
            self._become(DogState.STANDING, Posture.STAND)
        elif command is Command.BRAV:
            self._pending_signals.append(DogSignal.PRAISE)
        elif command in (Command.HIER, Command.SUCH):
            # Startpose ist erst im naechsten update() bekannt.
            self._pending_start = command
            self._become(DogState.COMING if command is Command.HIER else DogState.SEARCHING,
                         Posture.STAND)
        return CommandResult(True)

    # ------------------------------------------------------- Regelschritt

    def update(self, pose: Pose2D, bone: BoneObservation, now: float) -> BehaviorOutput:
        """Berechnet Bewegung, Haltung und Signale fuer den aktuellen Zeitpunkt."""
        self._start_pending_maneuver(pose, now)
        velocity = STOP

        if self._state is DogState.SEARCHING and self._search is not None:
            step = self._search.update(pose, bone, now)
            velocity = step.velocity
            self._pending_signals.extend(
                _SEARCH_EVENT_TO_SIGNAL[event] for event in step.events
                if event in _SEARCH_EVENT_TO_SIGNAL)
            if self._search.is_finished:
                # Ende sitzend mit Ton: MISSION_COMPLETE kommt im selben Schritt als Signal.
                self._search = None
                self._become(DogState.SITTING, Posture.SIT)

        elif self._state is DogState.COMING and self._come_here is not None:
            velocity = self._come_here.update(pose)
            if self._come_here.is_finished:
                self._come_here = None
                self._become(DogState.STANDING, Posture.STAND)

        signals = tuple(self._pending_signals)
        self._pending_signals.clear()
        return BehaviorOutput(velocity=velocity, posture=self._posture, signals=signals)

    # -------------------------------------------------------------- Hilfen

    def _become(self, state: DogState, posture: Posture) -> None:
        self._state = state
        self._posture = posture

    def _start_pending_maneuver(self, pose: Pose2D, now: float) -> None:
        if self._pending_start is Command.SUCH:
            self._search = SearchMission(pose, now, self._params.search)
        elif self._pending_start is Command.HIER:
            self._come_here = ComeHereManeuver(pose, self._params.come_here)
        self._pending_start = None
