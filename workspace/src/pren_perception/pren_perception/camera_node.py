"""
ROS-2-Node, der Kamerabilder veroeffentlicht. Die Kamera wird nur hier geoeffnet.

Veroeffentlicht:
    /camera/image_raw    sensor_msgs/Image (bgr8)

Parameter:
    device               Kameraindex fuer OpenCV (Laptop-Kamera = 0)
    width, height        gewuenschte Aufloesung
    fps                  Bildrate

Auf dem Raspberry Pi mit Pi Camera Module 3 wird spaeter ein Picamera2-Backend
ergaenzt; Topic und Format bleiben gleich.
"""

import cv2
from cv_bridge import CvBridge
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class CameraNode(Node):
    """Liest Bilder von einer OpenCV-Kamera und veroeffentlicht sie."""

    def __init__(self):
        super().__init__('camera')
        self.declare_parameter('device', 0)
        self.declare_parameter('width', 640)
        self.declare_parameter('height', 480)
        self.declare_parameter('fps', 15.0)

        device = self.get_parameter('device').value
        self._capture = cv2.VideoCapture(device)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.get_parameter('width').value)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.get_parameter('height').value)
        if not self._capture.isOpened():
            raise RuntimeError(f'Kamera {device} laesst sich nicht oeffnen. '
                               'Windows: Kamerazugriff fuer Desktop-Apps erlauben.')

        self._bridge = CvBridge()
        self._image_pub = self.create_publisher(Image, '/camera/image_raw', 1)
        self.create_timer(1.0 / self.get_parameter('fps').value, self._publish_frame)
        self.get_logger().info(f'Kamera {device} geoeffnet.')

    def _publish_frame(self) -> None:
        ok, frame = self._capture.read()
        if not ok:
            self.get_logger().warning('Kein Bild von der Kamera.', throttle_duration_sec=2.0)
            return
        msg = self._bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'camera'
        self._image_pub.publish(msg)

    def destroy_node(self):
        """Gibt die Kamera frei."""
        self._capture.release()
        super().destroy_node()


def main(args=None):
    """Startet den camera-Node."""
    rclpy.init(args=args)
    node = CameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
