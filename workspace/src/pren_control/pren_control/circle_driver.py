import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class CircleDriver(Node):

    def __init__(self):
        super().__init__("circle_driver")

        # ROS-Parameter
        self.declare_parameter("radius", 1.0)
        self.declare_parameter("linear_speed", 0.2)

        # Publisher
        self.publisher = self.create_publisher(
            Twist,
            "/cmd_vel",
            10
        )

        # 10 Befehle pro Sekunde
        self.timer = self.create_timer(
            0.1,
            self.drive_circle
        )

        self.get_logger().info("Circle driver started")


    def drive_circle(self):

        radius = float(
            self.get_parameter("radius").value
        )

        linear_speed = float(
            self.get_parameter("linear_speed").value
        )

        if abs(radius) < 0.01:
            self.get_logger().error(
                "Radius darf nicht 0 sein."
            )
            return

        # Kreisbewegung:
        # v = omega * r
        #
        # daraus:
        # omega = v / r

        angular_speed = linear_speed / radius

        msg = Twist()

        msg.linear.x = linear_speed
        msg.angular.z = angular_speed

        self.publisher.publish(msg)


def main(args=None):

    rclpy.init(args=args)

    node = CircleDriver()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        # Beim Beenden STOP senden
        stop = Twist()
        node.publisher.publish(stop)

        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()