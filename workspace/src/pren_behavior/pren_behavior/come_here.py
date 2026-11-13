"""Ablauf des Befehls HIER: ein kurzes Stueck geradeaus auf die Person zufahren."""

from dataclasses import dataclass

from pren_behavior.motion import Pose2D, STOP, Velocity


@dataclass(frozen=True)
class ComeHereParameters:
    """Einstellbare Werte fuer HIER."""

    distance_m: float = 0.5
    speed: float = 0.2


class ComeHereManeuver:
    """Faehrt von der Startpose aus geradeaus, bis die Distanz erreicht ist."""

    def __init__(self, start_pose: Pose2D, params: ComeHereParameters):
        self._start_pose = start_pose
        self._params = params
        self._finished = False

    @property
    def is_finished(self) -> bool:
        """Melde, ob die Distanz gefahren ist."""
        return self._finished

    def update(self, pose: Pose2D) -> Velocity:
        """Gibt den Fahrbefehl fuer die aktuelle Pose zurueck."""
        if self._finished or pose.distance_to(self._start_pose) >= self._params.distance_m:
            self._finished = True
            return STOP
        return Velocity(linear=self._params.speed)
