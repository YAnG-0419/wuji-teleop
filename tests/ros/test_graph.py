import os
import subprocess
import sys
import time

import pytest


pytestmark = pytest.mark.skipif(os.environ.get("WUJI_ROS_TESTS") != "1",
                                reason="run the explicit test-ros task with system ROS loaded")


def test_retarget_control_and_switch_over_real_ros_without_devices():
    import numpy as np
    import rclpy
    from geometry_msgs.msg import Point32
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import JointState, PointCloud
    from std_srvs.srv import SetBool

    from wuji_control.contract import joint_names
    from wuji_control.node import ControlNode
    from wuji_teleop.node import RetargetNode

    rclpy.init(args=[])
    nodes = []
    executor = SingleThreadedExecutor()
    state = {"enabled": False, "input": True, "positions": [0.0] * 20, "commands": []}
    process = None
    try:
        control = ControlNode()
        nodes.append(control)
        retarget = RetargetNode()
        nodes.append(retarget)
        hardware = Node("wuji_test_hardware")
        nodes.append(hardware)
        feedback = hardware.create_publisher(JointState, "/wuji/right/joint_states", qos_profile_sensor_data)
        landmarks = hardware.create_publisher(PointCloud, "/teleop/right/keypoints", qos_profile_sensor_data)
        names = list(joint_names("right"))

        def enabled(request, response):
            state["enabled"] = request.data
            response.success = True
            return response

        def command(message):
            state["commands"].append(message)
            if state["enabled"]:
                state["positions"] = list(message.position)

        def publish():
            message = JointState()
            message.header.stamp = hardware.get_clock().now().to_msg()
            message.name, message.position = names, state["positions"]
            feedback.publish(message)
            if state["input"]:
                cloud = PointCloud()
                cloud.header.stamp = message.header.stamp
                cloud.points = [Point32()]
                for finger, x in enumerate([-0.04, -0.03, -0.01, 0.01, 0.03]):
                    for joint in range(4):
                        cloud.points.append(Point32(x=x, y=0.03 * (joint + 1), z=0.005 * finger))
                landmarks.publish(cloud)

        hardware.create_service(SetBool, "/wuji/right/hardware_enable", enabled)
        hardware.create_subscription(JointState, "/wuji/right/command", command, 1)
        hardware.create_timer(0.02, publish)
        for node in nodes:
            executor.add_node(node)

        def until(predicate, timeout=8.0):
            deadline = time.monotonic() + timeout
            while not predicate() and time.monotonic() < deadline:
                executor.spin_once(timeout_sec=0.01)
            assert predicate(), "ROS condition timed out"

        def switch(action, expected=0):
            nonlocal process
            process = subprocess.Popen([sys.executable, "-m", "wuji_teleop.switch", action, "--side", "right"],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            until(lambda: process.poll() is not None, timeout=20.0)
            output, _ = process.communicate(timeout=1)
            assert process.returncode == expected, output
            process = None

        until(lambda: control.motion.feedback is not None and "teleop" in control.motion.targets
              and control.hardware.service_is_ready())
        assert not control.motion.enabled and not state["enabled"]
        switch("on")
        until(lambda: bool(state["commands"]))
        assert control.motion.enabled and state["enabled"]
        assert state["commands"][-1].name == names
        assert len(state["commands"][-1].position) == 20
        assert np.isfinite(state["commands"][-1].position).all()
        switch("off")
        assert not control.motion.enabled and not state["enabled"]
        state["commands"].clear()
        switch("on")
        until(lambda: bool(state["commands"]))
        state["input"] = False
        until(lambda: not control.motion.enabled)
        deadline = time.monotonic() + 0.1
        until(lambda: time.monotonic() >= deadline)
        count = len(state["commands"])
        deadline = time.monotonic() + 0.1
        until(lambda: time.monotonic() >= deadline)
        assert len(state["commands"]) == count
        switch("off")
        assert not state["enabled"]
        switch("on", expected=1)
        assert not state["enabled"] and not control.motion.enabled
    finally:
        if process is not None:
            process.kill()
            process.communicate()
        executor.shutdown()
        for node in reversed(nodes):
            node.destroy_node()
        rclpy.shutdown()
