import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState
from std_srvs.srv import SetBool

from .contract import fresh_stamp, joint_names, ordered_positions


class WujiClient(Node):
    def __init__(self, side="right"):
        super().__init__("wuji_program_" + side)
        self.names = joint_names(side)
        self.prefix = "/wuji/" + side
        self.feedback = None
        self.feedback_at = None
        self.target = None
        self.publisher = self.create_publisher(JointState, self.prefix + "/target/program", 1)
        self.create_subscription(JointState, self.prefix + "/joint_states", self._feedback, qos_profile_sensor_data)
        self.create_timer(1 / 50, self._publish)

    def _feedback(self, message):
        if fresh_stamp(message.header.stamp, self.get_clock().now().nanoseconds / 1e9):
            self.feedback = ordered_positions(message, self.names)
            self.feedback_at = time.monotonic()

    def _publish(self):
        if self.target is not None:
            message = JointState()
            message.header.stamp = self.get_clock().now().to_msg()
            message.name, message.position = list(self.names), list(self.target)
            self.publisher.publish(message)

    def _service(self, suffix, value, timeout=7.0):
        client = self.create_client(SetBool, self.prefix + "/" + suffix)
        try:
            if not client.wait_for_service(timeout_sec=timeout):
                raise TimeoutError(suffix + " service unavailable")
            future = client.call_async(SetBool.Request(data=value))
            rclpy.spin_until_future_complete(self, future, timeout_sec=timeout)
            if not future.done():
                raise TimeoutError(suffix + " result unknown")
            result = future.result()
            if result is None or not result.success:
                raise RuntimeError(suffix + ": " + (result.message if result else "no response"))
        finally:
            self.destroy_client(client)

    def _require_feedback(self):
        if self.feedback_at is None or time.monotonic() - self.feedback_at > 0.25:
            raise RuntimeError("measured feedback unavailable or stale")

    def start(self, timeout=5.0):
        deadline = time.monotonic() + timeout
        while self.feedback is None and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.02)
        self._require_feedback()
        self._service("select_teleop", False)
        self.target = self.feedback
        self._publish()
        self._service("enable", True)

    def move_to(self, positions, *, duration=2.0, settle_timeout=10.0, tolerance=0.05):
        goal = tuple(float(v) for v in positions)
        if len(goal) != 20 or not all(math.isfinite(v) for v in goal):
            raise ValueError("positions must contain 20 finite radians")
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("duration must be positive")
        self._require_feedback()
        initial = self.feedback
        started = time.monotonic()
        deadline = started + duration + settle_timeout
        while time.monotonic() < deadline:
            self._require_feedback()
            alpha = min(1.0, (time.monotonic() - started) / duration)
            blend = alpha * alpha * (3 - 2 * alpha)
            self.target = tuple(a + blend * (b - a) for a, b in zip(initial, goal))
            rclpy.spin_once(self, timeout_sec=0.01)
            if alpha == 1 and max(abs(a - b) for a, b in zip(self.feedback, goal)) <= tolerance:
                return
        raise TimeoutError("target not reached in measured feedback")

    def stop(self):
        self.target = None
        failures = []
        for suffix in ("enable", "hardware_enable"):
            try:
                self._service(suffix, False)
            except Exception as error:
                failures.append(str(error))
        if failures:
            raise RuntimeError("; ".join(failures))

    def __enter__(self):
        try:
            self.start()
        except BaseException:
            try:
                self.stop()
            finally:
                self.destroy_node()
            raise
        return self

    def __exit__(self, *error):
        try:
            self.stop()
        finally:
            self.destroy_node()
