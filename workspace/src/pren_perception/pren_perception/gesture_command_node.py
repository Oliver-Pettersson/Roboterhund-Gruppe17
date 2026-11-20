"""
ROS-2-Node fuer Gestenbefehle: Kamerabild -> MediaPipe -> /pren/dog_command.

Abonniert:
    /camera/image_raw    sensor_msgs/Image
Veroeffentlicht:
    /pren/dog_command    pren_interfaces/DogCommand   (source = "gesture")

Parameter:
    model_path           Datei hand_landmarker.task
    window_size, min_agreeing, cooldown_s   Glaettung (siehe GestureDebouncer)
    open_palm_window_size, open_palm_min_agreeing   strengere Glaettung fuer SITZ (0 = gleich)
"""

from pathlib import Path
import time

from cv_bridge import CvBridge
from pren_interfaces.msg import DogCommand
from pren_perception.gesture.gesture_command_detector import GestureCommandDetector
from pren_perception.gesture.gesture_debouncer import GestureDebouncer
from pren_perception.gesture.hand_landmark_detector import HandLandmarkDetector
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class GestureCommandNode(Node):
    """Erkennt Handgesten im Kamerabild und veroeffentlicht die Befehle."""

    def __init__(self):
        super().__init__('gesture_command')
        self.declare_parameter('model_path', '')
        self.declare_parameter('window_size', 5)
        self.declare_parameter('min_agreeing', 4)
        self.declare_parameter('cooldown_s', 1.0)
        self.declare_parameter('open_palm_window_size', 0)
        self.declare_parameter('open_palm_min_agreeing', 0)

        self._hands = HandLandmarkDetector(Path(self.get_parameter('model_path').value))
        self._detector = GestureCommandDetector(
            find_hands=self._hands.detect,
            debouncer=GestureDebouncer(
                window_size=self.get_parameter('window_size').value,
                min_agreeing=self.get_parameter('min_agreeing').value,
                cooldown_s=self.get_parameter('cooldown_s').value,
                open_palm_window_size=self.get_parameter('open_palm_window_size').value,
                open_palm_min_agreeing=self.get_parameter('open_palm_min_agreeing').value,
            ),
        )
        self._bridge = CvBridge()
        self._command_pub = self.create_publisher(DogCommand, '/pren/dog_command', 10)
        # Tiefe 1: immer nur das neueste Bild auswerten, alte verwerfen.
        self.create_subscription(Image, '/camera/image_raw', self._on_image, 1)
        self.get_logger().info('Gestenerkennung bereit (SITZ, PLATZ, AUF).')

    def _on_image(self, msg: Image) -> None:
        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        command = self._detector.process(frame, time.monotonic())
        if command is None:
            return
        result = self._detector.last_result
        out = DogCommand(command=int(command), source=DogCommand.SOURCE_GESTURE,
                         confidence=result.confidence)
        out.header.stamp = self.get_clock().now().to_msg()
        self._command_pub.publish(out)
        self.get_logger().info(f'Geste erkannt: {command.name} ({result.description})')

    def destroy_node(self):
        """Gibt MediaPipe frei."""
        self._hands.close()
        super().destroy_node()


def main(args=None):
    """Startet den gesture_command-Node."""
    rclpy.init(args=args)
    node = GestureCommandNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
