import json
import math
from pathlib import Path
import time

from ament_index_python.packages import get_package_share_directory
import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState
from std_srvs.srv import SetBool

from .contract import fresh_stamp, joint_names, ordered_positions
from .motion import Motion


class ControlNode(Node):
    def __init__(self):
        super().__init__("wuji_control")
        for name, value in (("side", "right"), ("source", "teleop"),
                            ("rate_hz", 100.0), ("timeout", 0.25), ("ready_timeout", 2.0)):
            self.declare_parameter(name, value)
        self.side = self.get_parameter("side").value
        self.names = joint_names(self.side)
        self.prefix = "/wuji/" + self.side
        share = Path(get_package_share_directory("wuji_control"))
        limits = json.loads((share / "config/joint_limits.json").read_text())[self.side]
        self.motion = Motion(limits, timeout=self.get_parameter("timeout").value,
                             source=self.get_parameter("source").value)
        self.ready_timeout = float(self.get_parameter("ready_timeout").value)
        if not math.isfinite(self.ready_timeout) or self.ready_timeout <= 0:
            raise ValueError("ready_timeout must be positive")
        rate = float(self.get_parameter("rate_hz").value)
        if not 0 < rate <= 200:
            raise ValueError("rate_hz must be in (0,200]")
        self.publisher = self.create_publisher(JointState, self.prefix + "/command", 1)
        self.create_subscription(JointState, self.prefix + "/joint_states",
                                 self._feedback, qos_profile_sensor_data)
        for source in ("teleop", "program"):
            self.create_subscription(JointState, self.prefix + "/target/" + source,
                                     lambda msg, source=source: self._target(source, msg), 1)
        self.services_group = ReentrantCallbackGroup()
        self.generation = 0
        self.enabling = False
        self.hardware = self.create_client(SetBool, self.prefix + "/hardware_enable")
        self.create_service(SetBool, self.prefix + "/enable", self._enable,
                            callback_group=self.services_group)
        self.create_service(SetBool, self.prefix + "/select_teleop", self._select)
        self.create_timer(1 / rate, self._tick)

    def _valid(self, message):
        now = self.get_clock().now().nanoseconds / 1e9
        if not fresh_stamp(message.header.stamp, now, self.motion.timeout):
            raise ValueError("stale or future source timestamp")
        return ordered_positions(message, self.names)

    def _feedback(self, message):
        try:
            self.motion.observe(self._valid(message), time.monotonic())
        except ValueError as error:
            self.get_logger().error(str(error))

    def _target(self, source, message):
        try:
            self.motion.target(source, self._valid(message), time.monotonic())
        except ValueError as error:
            self.get_logger().error(str(error))

    async def _wait_ready(self, generation):
        from rclpy.task import Future

        future = Future(executor=self.executor)
        deadline = time.monotonic() + self.ready_timeout

        def poll():
            if future.done():
                return
            if generation != self.generation:
                future.set_exception(RuntimeError("enable cancelled by stop or source change"))
                return
            try:
                self.motion.check_ready(time.monotonic())
            except (RuntimeError, ValueError) as error:
                if time.monotonic() >= deadline:
                    future.set_exception(RuntimeError("waiting for fresh input timed out: " + str(error)))
            else:
                future.set_result(True)

        timer = self.create_timer(0.01, poll)
        try:
            poll()
            await future
        finally:
            self.destroy_timer(timer)

    async def _hardware(self, enabled):
        if not self.hardware.service_is_ready():
            raise RuntimeError("hardware enable service unavailable")
        future = self.hardware.call_async(SetBool.Request(data=enabled))

        def timeout():
            if not future.done():
                future.set_exception(TimeoutError("hardware enable result unknown"))

        timer = self.create_timer(7.0, timeout)
        try:
            result = await future
            if result is None or not result.success:
                raise RuntimeError(result.message if result else "hardware enable result unknown")
        finally:
            self.destroy_timer(timer)

    async def _enable(self, request, response):
        if request.data and self.enabling:
            response.success, response.message = False, "enable already in progress"
            return response
        self.generation += 1
        generation = self.generation
        if request.data:
            self.enabling = True
        self.motion.disable()
        try:
            if request.data:
                await self._wait_ready(generation)
            await self._hardware(request.data)
            if request.data:
                if generation != self.generation:
                    raise RuntimeError("enable cancelled by stop or source change")
                self.motion.enable(time.monotonic())
            response.success = True
            response.message = "motion enabled" if request.data else "motion disabled"
        except Exception as error:
            if request.data:
                try:
                    await self._hardware(False)
                except Exception as disable_error:
                    self.get_logger().error("hardware stop unconfirmed: " + str(disable_error))
            response.success, response.message = False, str(error)
        finally:
            if request.data:
                self.enabling = False
        return response

    def _select(self, request, response):
        self.generation += 1
        self.motion.select("teleop" if request.data else "program")
        response.success, response.message = True, "selected %s; motion disabled" % self.motion.source
        return response

    def _tick(self):
        try:
            positions = self.motion.next(time.monotonic())
            if positions is None:
                return
            message = JointState()
            message.header.stamp = self.get_clock().now().to_msg()
            message.name, message.position = list(self.names), list(positions)
            self.publisher.publish(message)
        except RuntimeError as error:
            self.get_logger().error(str(error))


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ControlNode()
        rclpy.spin(node)
    finally:
        if node is not None:
            node.motion.disable()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
