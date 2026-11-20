"""
Zugriff auf die Webots-Welt: Motoren, Encoder, Knochen, Licht, Kamera und Anzeige.

Alle Aufrufe der Webots-API liegen hier. Der Rest der Simulation arbeitet nur mit
einfachen Zahlen und muss Webots nicht kennen.
"""

import math

START_TRANSLATION = [0.0, 0.0, 0.0975]
START_ROTATION = [0.0, 0.0, 1.0, math.pi]   # Blick zum Schiedsrichter
BONE_HEIGHT_M = 0.025
CONE_COLOR_SEARCHING = ([0.0, 0.8, 1.0], [0.0, 0.25, 0.5])
CONE_COLOR_DETECTED = ([1.0, 0.85, 0.0], [0.7, 0.5, 0.0])
LABEL_ID = 0
LABEL_COLOR = 0x000000


class WebotsWorld:
    """Duenne Huelle um den Webots-Supervisor."""

    def __init__(self, supervisor):
        self._robot = supervisor
        self.timestep_ms = int(supervisor.getBasicTimeStep())

        self._left_motor = supervisor.getDevice('left wheel')
        self._right_motor = supervisor.getDevice('right wheel')
        for motor in (self._left_motor, self._right_motor):
            motor.setPosition(float('inf'))
            motor.setVelocity(0.0)

        self._left_encoder = supervisor.getDevice('left wheel sensor')
        self._right_encoder = supervisor.getDevice('right wheel sensor')
        self._left_encoder.enable(self.timestep_ms)
        self._right_encoder.enable(self.timestep_ms)

        self._keyboard = supervisor.getKeyboard()
        self._keyboard.enable(self.timestep_ms)

        self._self_node = supervisor.getSelf()
        self._bone = supervisor.getFromDef('BONE')
        self._light = supervisor.getFromDef('CELEBRATION_LIGHT')
        self._cone_appearance = supervisor.getFromDef('VISION_CONE_APP')
        self._viewpoint = supervisor.getFromDef('VIEWPOINT')
        self._cone_detected = None

    def step(self) -> bool:
        """Fuehrt einen Simulationsschritt aus. False, wenn Webots beendet wird."""
        return self._robot.step(self.timestep_ms) != -1

    # ------------------------------------------------------------- Roboter

    def set_wheel_speeds(self, left: float, right: float) -> None:
        """Setzt die Raddrehzahlen in rad/s."""
        self._left_motor.setVelocity(left)
        self._right_motor.setVelocity(right)

    def wheel_positions(self) -> tuple:
        """Encoderwerte (links, rechts) in rad, 0 solange noch kein Wert vorliegt."""
        values = (self._left_encoder.getValue(), self._right_encoder.getValue())
        return tuple(0.0 if math.isnan(value) else value for value in values)

    def robot_position_and_orientation(self) -> tuple:
        """Position [x, y, z] und Rotationsmatrix des Roboters (Ground Truth)."""
        return self._self_node.getPosition(), self._self_node.getOrientation()

    def move_robot_to_start(self) -> None:
        """Setzt den Roboter ins Startfeld mit Blick zum Schiedsrichter."""
        self.set_wheel_speeds(0.0, 0.0)
        self._self_node.getField('translation').setSFVec3f(START_TRANSLATION)
        self._self_node.getField('rotation').setSFRotation(START_ROTATION)
        self._self_node.resetPhysics()

    # -------------------------------------------------------------- Knochen

    def bone_position(self):
        """Position (x, y) des Knochens oder None, falls die Welt keinen hat."""
        if self._bone is None:
            return None
        x, y, _ = self._bone.getPosition()
        return x, y

    def place_bone(self, x: float, y: float) -> None:
        """Legt den Knochen an die Position und das Feierlicht darueber."""
        if self._bone is None:
            return
        self._bone.getField('translation').setSFVec3f([x, y, BONE_HEIGHT_M])
        self._bone.resetPhysics()
        if self._light is not None:
            self._light.getField('location').setSFVec3f([x, y, 0.4])

    # ------------------------------------------------------------- Anzeige

    def highlight_vision_cone(self, bone_visible: bool) -> None:
        """Faerbt den Sichtkegel gelb, wenn der Knochen sichtbar ist, sonst blau."""
        if self._cone_appearance is None or bone_visible == self._cone_detected:
            return
        base, emissive = CONE_COLOR_DETECTED if bone_visible else CONE_COLOR_SEARCHING
        self._cone_appearance.getField('baseColor').setSFVec3f(base)
        self._cone_appearance.getField('emissiveColor').setSFVec3f(emissive)
        self._cone_detected = bone_visible

    def set_light_intensity(self, intensity: float) -> None:
        """Setzt die Helligkeit des Feierlichts beim Knochen."""
        if self._light is not None:
            self._light.getField('intensity').setSFFloat(intensity)

    def show_status(self, text: str) -> None:
        """Zeigt einen Text oben links im 3D-Fenster."""
        self._robot.setLabel(LABEL_ID, text, 0.01, 0.01, 0.12, LABEL_COLOR, 0.0, 'Arial')

    def center_camera(self) -> None:
        """Kamera erhoeht ueber dem Startfeld mit Blick in den Suchsektor."""
        if self._viewpoint is None:
            return
        self._viewpoint.getField('position').setSFVec3f([-4.2, 0.0, 2.8])
        self._viewpoint.getField('orientation').setSFRotation([0.0, 1.0, 0.0, 0.40])
        self._viewpoint.getField('fieldOfView').setSFFloat(0.95)

    def reset_key_pressed(self) -> bool:
        """Melde, ob im 3D-Fenster die Taste R gedrueckt wurde."""
        return self._keyboard.getKey() in (ord('R'), ord('r'))
