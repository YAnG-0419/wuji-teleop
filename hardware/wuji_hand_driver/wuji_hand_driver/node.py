from __future__ import annotations

import contextlib
import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState
from std_srvs.srv import SetBool

from wuji_hand_driver.driver import (
    JOINT_COUNT,
    feedback_values,
    joint_names,
    normalize_command,
)


class WujiHand2DriverNode(Node):
    def __init__(self) -> None:
        super().__init__("wuji_hand_2_driver")
        self.declare_parameter("serial", "")
        self.declare_parameter("hand_side", "right")
        self.declare_parameter("command_topic", "")
        self.declare_parameter("state_topic", "")
        self.declare_parameter("state_publish_rate_hz", 200.0)
        self.declare_parameter("mit_kp", 3.0)
        self.declare_parameter("mit_kd", 0.05)
        self.declare_parameter("effort_limit", 1.5)
        self.declare_parameter("auto_enable", False)
        self.declare_parameter("command_timeout_sec", 0.3)
        self.declare_parameter("feedback_timeout_sec", 0.25)
        self.declare_parameter("enable_timeout_sec", 5.0)
        self.declare_parameter("require_all_joints_online", True)
        self.declare_parameter("enable_sdk_bridge", False)

        self._hand = None
        self._state_subscription = None
        self._command_publisher = None
        self._enabled_by_driver = False
        self._closed = False
        self._last_command_at = None
        self._last_feedback_at = None

        side = str(self.get_parameter("hand_side").value).strip().lower()
        self._joint_names = joint_names(side)
        self._side = side
        command_topic = str(self.get_parameter("command_topic").value).strip()
        state_topic = str(self.get_parameter("state_topic").value).strip()
        command_topic = command_topic or f"/wuji/{side}/command"
        state_topic = state_topic or f"/wuji/{side}/joint_states"
        state_rate_hz = float(self.get_parameter("state_publish_rate_hz").value)
        if not math.isfinite(state_rate_hz) or state_rate_hz <= 0.0:
            raise ValueError("state_publish_rate_hz must be positive")
        for parameter in ("command_timeout_sec", "feedback_timeout_sec"):
            value = float(self.get_parameter(parameter).value)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(parameter + " must be finite and positive")

        self._state_publisher = self.create_publisher(
            JointState, state_topic, qos_profile_sensor_data
        )
        self._command_subscription = self.create_subscription(
            JointState, command_topic, self._on_command, 10
        )

        try:
            self._connect()
            self._state_timer = self.create_timer(
                1.0 / state_rate_hz, self._publish_latest_state
            )
            self._enable_service = self.create_service(
                SetBool, f"/wuji/{side}/hardware_enable", self._set_enabled
            )
            self._watchdog_timer = self.create_timer(0.05, self._watchdog)
        except Exception:
            self._close_sdk()
            raise

        self.get_logger().info(
            f"Wuji Hand 2 connected: side={side}, "
            f"serial={self._hand.serial_number}, command={command_topic}, "
            f"state={state_topic}"
        )

    def _connect(self) -> None:
        from wuji_sdk import (
            ConnectOptions,
            Handedness,
            JointCommand,
            SdkManager,
            WujiHand2,
        )

        self._joint_command_type = JointCommand
        self._manager = SdkManager.instance()
        serial = str(self.get_parameter("serial").value).strip()
        connect_target = (
            {"sn": serial}
            if serial
            else {
                "handedness": (
                    Handedness.Left if self._side == "left" else Handedness.Right
                )
            }
        )
        hand = self._manager.connect(
            **connect_target,
            device_name=f"lychee_wuji_hand_2_{self._side}",
            options=ConnectOptions(
                enable_bridge=bool(
                    self.get_parameter("enable_sdk_bridge").value
                )
            ),
        )
        if not isinstance(hand, WujiHand2):
            hand.disconnect()
            raise RuntimeError("connected Wuji device is not a Wuji Hand 2")
        self._hand = hand

        reported_handedness = str(hand.handedness().get()).strip().lower()
        if reported_handedness != self._side:
            raise RuntimeError(
                f"connected Wuji Hand 2 does not match requested {self._side} side"
            )

        online_count = int(hand.online_joints_count().get())
        if online_count == 0:
            raise RuntimeError("Wuji Hand 2 has no online joints")
        if (
            bool(self.get_parameter("require_all_joints_online").value)
            and online_count != JOINT_COUNT
        ):
            raise RuntimeError(
                f"Wuji Hand 2 has {online_count}/{JOINT_COUNT} joints online"
            )

        hand.effort_limit().set(float(self.get_parameter("effort_limit").value))
        hand.mit_params().set(
            (
                float(self.get_parameter("mit_kp").value),
                float(self.get_parameter("mit_kd").value),
            )
        )
        if bool(self.get_parameter("auto_enable").value):
            hand.enable()
            self._enabled_by_driver = True
            self._last_command_at = time.monotonic()
            self._wait_until_enabled(
                float(self.get_parameter("enable_timeout_sec").value)
            )

        self._command_publisher = hand.joint_command().publish()
        self._state_subscription = hand.joint_states().subscribe()

    def _wait_until_enabled(self, timeout_sec: float) -> None:
        if timeout_sec <= 0.0:
            raise ValueError("enable_timeout_sec must be positive")
        diagnostics = self._hand.joint_diagnostics().subscribe()
        deadline = time.monotonic() + timeout_sec
        try:
            while time.monotonic() < deadline:
                frame = diagnostics.recv()
                if frame is not None and len(frame.joints) == JOINT_COUNT and all(
                    entry.status_word.ext_state == 2 for entry in frame.joints
                ):
                    return
                time.sleep(0.02)
        finally:
            diagnostics.close()
        raise RuntimeError(
            f"Wuji Hand 2 did not enable within {timeout_sec:.3f}s"
        )

    def _on_command(self, message: JointState) -> None:
        try:
            if not self._enabled_by_driver:
                raise ValueError("hardware output is disabled")
            moment = time.monotonic()
            self._require_feedback(moment)
            stamp = message.header.stamp
            age = self.get_clock().now().nanoseconds / 1e9 - stamp.sec - stamp.nanosec / 1e9
            if stamp.sec == 0 or age < -0.05 or age > float(self.get_parameter("command_timeout_sec").value):
                raise ValueError("command source timestamp is stale or in the future")
            command = normalize_command(
                names=message.name,
                positions=message.position,
                velocities=message.velocity,
                efforts=message.effort,
                expected_names=self._joint_names,
            )
            values = [
                self._joint_command_type(position, velocity, effort)
                for position, velocity, effort in zip(
                    command.positions,
                    command.velocities,
                    command.efforts,
                )
            ]
            self._command_publisher.send(values)
            self._last_command_at = moment
        except Exception as exc:
            self.get_logger().error(f"rejected Wuji Hand 2 command: {exc}")

    def _publish_latest_state(self) -> None:
        try:
            latest = None
            while (frame := self._state_subscription.recv()) is not None:
                latest = frame
            if latest is None:
                return
            feedback = feedback_values(latest, side=self._side)
            if len(feedback.positions) != JOINT_COUNT:
                raise ValueError("incomplete 20-joint feedback")
            self._last_feedback_at = time.monotonic()
            message = JointState()
            message.header.stamp = self.get_clock().now().to_msg()
            message.header.frame_id = feedback.frame_id
            message.name = list(feedback.names)
            message.position = list(feedback.positions)
            message.velocity = list(feedback.velocities)
            message.effort = list(feedback.efforts)
            self._state_publisher.publish(message)
        except Exception as exc:
            self.get_logger().error(f"failed to publish Wuji Hand 2 state: {exc}")

    def _require_feedback(self, moment):
        timeout = float(self.get_parameter("feedback_timeout_sec").value)
        if self._last_feedback_at is None or moment - self._last_feedback_at > timeout:
            raise RuntimeError("fresh 20-joint feedback required")

    def _set_enabled(self, request, response):
        try:
            if request.data and not self._enabled_by_driver:
                self._require_feedback(time.monotonic())
                self._hand.enable()
                self._enabled_by_driver = True
                try:
                    self._wait_until_enabled(float(self.get_parameter("enable_timeout_sec").value))
                except Exception:
                    self._hand.disable()
                    self._enabled_by_driver = False
                    raise
                self._last_command_at = time.monotonic()
            elif not request.data:
                self._hand.disable()
                self._enabled_by_driver = False
            response.success = True
            response.message = "hardware enabled" if request.data else "hardware disabled"
        except Exception as error:
            response.success, response.message = False, str(error)
        return response

    def _watchdog(self):
        if not self._enabled_by_driver:
            return
        try:
            moment = time.monotonic()
            self._require_feedback(moment)
            if self._last_command_at is None or moment - self._last_command_at > float(self.get_parameter("command_timeout_sec").value):
                raise RuntimeError("command stream expired")
        except Exception as error:
            self.get_logger().error(str(error) + "; disabling motors")
            try:
                self._hand.disable()
                self._enabled_by_driver = False
            except Exception as disable_error:
                self.get_logger().error("motor disable failed: " + str(disable_error))

    def destroy_node(self) -> bool:
        self._close_sdk()
        return super().destroy_node()

    def _close_sdk(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._state_subscription is not None:
            with contextlib.suppress(Exception):
                self._state_subscription.close()
        if self._command_publisher is not None:
            with contextlib.suppress(Exception):
                self._command_publisher.close()
        if self._hand is not None:
            if self._enabled_by_driver:
                with contextlib.suppress(Exception):
                    self._hand.disable()
            with contextlib.suppress(Exception):
                self._hand.disconnect()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = WujiHand2DriverNode()
        rclpy.spin(node)
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
