"""
ROS-2-Node fuer die Knochenerkennung: Kamerabild -> YOLO -> /pren/bone_detection.

Abonniert:
    /camera/image_raw    sensor_msgs/Image
Veroeffentlicht:
    /pren/bone_detection pren_interfaces/BoneDetection

In der Simulation wird dieser Node nicht gestartet; dort liefert die Webots-Bridge
die Knochenposition. Auf dem Roboter ersetzt er sie, das Topic bleibt gleich.
"""

import math
from pathlib import Path

from cv_bridge import CvBridge
from pren_interfaces.msg import BoneDetection
from pren_perception.bone.bone_localizer import CameraGeometry, locate_bone
from pren_perception.bone.yolo_bone_detector import YoloBoneDetector
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class BoneDetectionNode(Node):
    """Sucht den Knochen im Kamerabild und meldet Distanz und Winkel."""

    def __init__(self):
        super().__init__('bone_detection')
        self.declare_parameter('model_path', '')
        self.declare_parameter('min_confidence', 0.5)
        self.declare_parameter('camera.horizontal_fov_deg', 66.0)
        self.declare_parameter('camera.vertical_fov_deg', 41.0)
        self.declare_parameter('camera.mounting_height_m', 0.25)
        self.declare_parameter('camera.tilt_down_deg', 10.0)

        self._detector = YoloBoneDetector(Path(self.get_parameter('model_path').value),
                                          self.get_parameter('min_confidence').value)
        self._bridge = CvBridge()
        self._camera = None
        self._detection_pub = self.create_publisher(BoneDetection, '/pren/bone_detection', 10)
        self.create_subscription(Image, '/camera/image_raw', self._on_image, 1)
        self.get_logger().info('Knochenerkennung bereit.')

    def _camera_geometry(self, width: int, height: int) -> CameraGeometry:
        if self._camera is None or self._camera.image_width != width:
            value = self.get_parameter
            self._camera = CameraGeometry(
                image_width=width, image_height=height,
                horizontal_fov_rad=math.radians(value('camera.horizontal_fov_deg').value),
                vertical_fov_rad=math.radians(value('camera.vertical_fov_deg').value),
                mounting_height_m=value('camera.mounting_height_m').value,
                tilt_down_rad=math.radians(value('camera.tilt_down_deg').value),
            )
        return self._camera

    def _on_image(self, msg: Image) -> None:
        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        detection = BoneDetection()
        detection.header.stamp = msg.header.stamp
        detection.header.frame_id = 'base_link'

        box = self._detector.detect(frame)
        location = None
        if box is not None:
            location = locate_bone(box, self._camera_geometry(msg.width, msg.height))
        if location is not None:
            detection.detected = True
            detection.distance_m = location.distance_m
            detection.bearing_rad = location.bearing_rad
            detection.confidence = box.confidence
        self._detection_pub.publish(detection)


def main(args=None):
    """Startet den bone_detection-Node."""
    rclpy.init(args=args)
    node = BoneDetectionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
