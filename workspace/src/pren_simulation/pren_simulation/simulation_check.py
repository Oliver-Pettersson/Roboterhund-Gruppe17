"""
Automatischer Abnahmetest gegen die laufende Simulation.

Spielt alle Befehle ueber /pren/dog_command ein (Quelle "gui") und prueft die Reaktion:
    * SITZ, PLATZ, AUF aendern die Haltung, BRAV gibt ein Lob-Signal, HIER faehrt 0,5 m.
    * SUCH: Knochen finden, genau einmal bellen, zurueck ins Startfeld, dort sitzen und
      den Abschlusston geben (MISSION_COMPLETE), Dauer messen.
    * Waehrend SUCH werden andere Befehle ignoriert.
Die Suche wird mehrmals mit jeweils neu platziertem Knochen wiederholt.

Aufruf (Simulation muss laufen):
    ros2 run pren_simulation simulation_check --ros-args -p search_runs:=5
Exit-Code 0 = alles bestanden.
"""

from dataclasses import dataclass
import math
import sys
import time
from typing import Callable, List

from nav_msgs.msg import Odometry
from pren_interfaces.msg import DogCommand, DogSignal, Posture, RobotState
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import Empty

LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)


@dataclass
class CheckResult:
    """Ergebnis einer einzelnen Pruefung."""

    name: str
    passed: bool
    detail: str = ''


class SimulationCheck(Node):
    """Sendet Befehle und beobachtet Zustand, Haltung, Signale und Position."""

    def __init__(self):
        super().__init__('simulation_check')
        self.declare_parameter('search_runs', 3)
        self.declare_parameter('search_timeout_s', 90.0)
        self._command_pub = self.create_publisher(DogCommand, '/pren/dog_command', 10)
        self._reset_pub = self.create_publisher(Empty, '/pren/reset', 10)
        self.state = RobotState()
        self.posture = None
        self.signals: List[int] = []
        self.position = (math.nan, math.nan)
        self.create_subscription(RobotState, '/pren/robot_state', self._on_state, 10)
        self.create_subscription(Posture, '/pren/posture', self._on_posture, LATCHED)
        self.create_subscription(DogSignal, '/pren/dog_signal', self._on_signal, 10)
        self.create_subscription(Odometry, '/odom', self._on_odometry, 10)
        self.results: List[CheckResult] = []

    # ------------------------------------------------------------ Hilfen

    def _on_state(self, msg):
        self.state = msg

    def _on_posture(self, msg):
        self.posture = msg.posture

    def _on_signal(self, msg):
        self.signals.append(msg.signal)

    def _on_odometry(self, msg):
        self.position = (msg.pose.pose.position.x, msg.pose.pose.position.y)

    def wait_until(self, condition: Callable[[], bool], timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            if condition():
                return True
        return False

    def wait(self, seconds: float) -> None:
        self.wait_until(lambda: False, seconds)

    def send(self, command: int) -> None:
        self._command_pub.publish(
            DogCommand(command=command, source=DogCommand.SOURCE_GUI, confidence=1.0))

    def record(self, name: str, passed: bool, detail: str = '') -> None:
        self.results.append(CheckResult(name, passed, detail))
        mark = 'OK  ' if passed else 'FEHL'
        self.get_logger().info(f'[{mark}] {name} {detail}')

    def reset_world(self) -> bool:
        self._reset_pub.publish(Empty())
        self.wait(2.0)
        return self.wait_until(lambda: self.state.state == 'STANDING'
                               and math.hypot(*self.position) < 0.1, 10.0)

    # ----------------------------------------------------------- Pruefungen

    def check_connection(self) -> bool:
        connected = self.wait_until(lambda: self.state.state != ''
                                    and not math.isnan(self.position[0]), 30.0)
        self.record('Verbindung zu Verhalten und Simulation', connected)
        return connected

    def check_postures(self) -> None:
        for name, command, posture, state in (
                ('SITZ', DogCommand.SITZ, Posture.SIT, 'SITTING'),
                ('PLATZ', DogCommand.PLATZ, Posture.LIE, 'LYING'),
                ('AUF', DogCommand.AUF, Posture.STAND, 'STANDING')):
            self.send(command)
            ok = self.wait_until(lambda: self.posture == posture
                                 and self.state.state == state, 3.0)
            self.record(f'{name} -> Haltung {state}', ok)

    def check_praise(self) -> None:
        self.signals.clear()
        self.send(DogCommand.BRAV)
        ok = self.wait_until(lambda: DogSignal.PRAISE in self.signals, 3.0)
        self.record('BRAV -> Lob-Signal', ok)

    def check_come_here(self) -> None:
        start = self.position
        self.send(DogCommand.HIER)
        self.wait_until(lambda: self.state.state == 'COMING', 2.0)
        finished = self.wait_until(lambda: self.state.state == 'STANDING', 10.0)
        travelled = math.dist(start, self.position)
        self.record('HIER -> faehrt auf Person zu', finished and 0.35 <= travelled <= 0.7,
                    f'({travelled:.2f} m)')

    def check_search(self, run: int) -> None:
        self.signals.clear()
        started = time.monotonic()
        self.send(DogCommand.SUCH)
        busy = self.wait_until(lambda: self.state.busy, 3.0)

        # Waehrend der Suche muss SITZ ignoriert werden.
        self.wait(2.0)
        self.send(DogCommand.SITZ)
        self.wait(0.5)
        locked = self.state.busy and self.state.state == 'SEARCHING'

        timeout = self.get_parameter('search_timeout_s').value
        done = self.wait_until(lambda: DogSignal.MISSION_COMPLETE in self.signals, timeout)
        duration = time.monotonic() - started
        barks = self.signals.count(DogSignal.BARK)
        home = math.hypot(*self.position)
        # Ende sitzend mit Ton (Anforderung 5.8), danach keine Sperre mehr.
        sitting = self.wait_until(lambda: self.posture == Posture.SIT
                                  and self.state.state == 'SITTING' and not self.state.busy, 3.0)
        finals = self.signals.count(DogSignal.MISSION_COMPLETE)
        self.record(f'SUCH Lauf {run}',
                    busy and locked and done and barks == 1 and home < 0.25 and sitting
                    and finals == 1,
                    f'({duration:.1f} s, {barks}x gebellt, {home:.2f} m vom Start, '
                    f'{"sitzt" if sitting else "sitzt NICHT"}, {finals}x Abschlusston, '
                    f'Sperre {"aktiv" if locked else "FEHLT"})')

    def run_all(self) -> bool:
        if not self.check_connection():
            return False
        self.reset_world()
        self.check_postures()
        self.check_praise()
        self.check_come_here()
        for run in range(1, self.get_parameter('search_runs').value + 1):
            self.reset_world()
            self.check_search(run)
        passed = sum(result.passed for result in self.results)
        self.get_logger().info(f'Ergebnis: {passed}/{len(self.results)} Pruefungen bestanden.')
        return passed == len(self.results)


def main(args=None):
    """Fuehrt alle Pruefungen aus. Exit-Code 0, wenn alle bestanden sind."""
    rclpy.init(args=args)
    node = SimulationCheck()
    try:
        success = node.run_all()
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
