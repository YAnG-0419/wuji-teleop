from pathlib import Path
import math

from geometry_msgs.msg import Point32
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import PointCloud

from .manus import ManusBridge, canonical_landmarks


class ManusNode(Node):
    def __init__(self):
        super().__init__("wuji_manus")
        self.declare_parameter("library", "")
        self.declare_parameter("calibration_dir", "")
        self.declare_parameter("rate_hz", 60.0)
        library = self.get_parameter("library").value
        if not library or not Path(library).is_file():
            raise ValueError("library must point to the built MANUS bridge .so")
        rate = float(self.get_parameter("rate_hz").value)
        if not math.isfinite(rate) or not 0 < rate <= 200:
            raise ValueError("rate_hz must be in (0,200]")
        self.bridge = ManusBridge(Path(library))
        self.publishers_by_side = {
            side: self.create_publisher(PointCloud, "/teleop/" + side + "/keypoints", qos_profile_sensor_data)
            for side in ("left", "right")
        }
        self.last_sequence = {}
        try:
            self.bridge.connect(Path(self.get_parameter("calibration_dir").value))
            self.create_timer(1 / rate, self._tick)
        except BaseException:
            self.bridge.close()
            raise

    def _tick(self):
        for side, publisher in self.publishers_by_side.items():
            try:
                frame = self.bridge.read(side)
                if frame is None or self.last_sequence.get(side) == frame.sequence:
                    continue
                points = canonical_landmarks(frame)
                message = PointCloud()
                message.header.stamp = self.get_clock().now().to_msg()
                message.header.frame_id = "manus_" + side
                message.points = [Point32(x=float(p[0]), y=float(p[1]), z=float(p[2])) for p in points]
                publisher.publish(message)
                self.last_sequence[side] = frame.sequence
            except (ValueError, RuntimeError) as error:
                self.get_logger().error(str(error))

    def destroy_node(self):
        self.bridge.close()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ManusNode()
        rclpy.spin(node)
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
