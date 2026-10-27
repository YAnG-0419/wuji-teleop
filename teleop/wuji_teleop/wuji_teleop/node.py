from pathlib import Path
import time

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState, PointCloud

from wuji_control.contract import fresh_stamp, joint_names
from .retarget import HandRetargeter


class RetargetNode(Node):
    def __init__(self):
        super().__init__("wuji_retarget")
        self.declare_parameter("side", "right")
        self.declare_parameter("config", "")
        self.declare_parameter("timeout", 0.25)
        self.side = self.get_parameter("side").value
        self.names = joint_names(self.side)
        self.timeout = float(self.get_parameter("timeout").value)
        if not 0 < self.timeout <= 1:
            raise ValueError("timeout must be in (0,1]")
        config = self.get_parameter("config").value
        if not config:
            config = Path(get_package_share_directory("wuji_teleop")) / "config" / (
                "retarget_manus_wuji_hand_2_" + self.side + ".yaml")
        self.retargeter = HandRetargeter(config, self.side)
        self.last_at = None
        self.publisher = self.create_publisher(JointState, "/wuji/" + self.side + "/target/teleop", 1)
        self.create_subscription(PointCloud, "/teleop/" + self.side + "/keypoints",
                                 self._keypoints, qos_profile_sensor_data)

    def _keypoints(self, message):
        try:
            if not fresh_stamp(message.header.stamp, self.get_clock().now().nanoseconds / 1e9, self.timeout):
                raise ValueError("landmark source timestamp expired")
            moment = time.monotonic()
            if self.last_at is None or moment - self.last_at > self.timeout:
                self.retargeter.reset()
            points = [(p.x, p.y, p.z) for p in message.points]
            output = self.retargeter.step(points)
            if not fresh_stamp(message.header.stamp, self.get_clock().now().nanoseconds / 1e9, self.timeout):
                raise ValueError("landmarks expired during retargeting")
            target = JointState()
            target.header = message.header
            target.name, target.position = list(self.names), output.tolist()
            self.publisher.publish(target)
            self.last_at = moment
        except (ValueError, RuntimeError) as error:
            self.get_logger().error(str(error))


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = RetargetNode()
        rclpy.spin(node)
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
