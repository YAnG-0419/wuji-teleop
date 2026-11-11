import asyncio
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

from wuji_control.motion import Motion


@pytest.fixture
def control(monkeypatch):
    for name in ("rclpy", "rclpy.node", "rclpy.qos", "rclpy.callback_groups",
                 "sensor_msgs", "sensor_msgs.msg", "std_srvs", "std_srvs.srv",
                 "ament_index_python", "ament_index_python.packages"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    sys.modules["rclpy.node"].Node = object
    sys.modules["rclpy.qos"].qos_profile_sensor_data = None
    sys.modules["rclpy.callback_groups"].ReentrantCallbackGroup = object
    sys.modules["sensor_msgs.msg"].JointState = object
    sys.modules["std_srvs.srv"].SetBool = SimpleNamespace(Request=lambda **values: SimpleNamespace(**values))
    sys.modules["ament_index_python.packages"].get_package_share_directory = lambda _: ""
    path = Path(__file__).parents[1] / "control/wuji_control/wuji_control/node.py"
    spec = importlib.util.spec_from_file_location("wuji_control.test_node", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    node = object.__new__(module.ControlNode)
    node.generation, node.enabling = 0, False
    node.motion = Motion([(-1, 2)] * 20)
    node.motion.observe([0.0] * 20, 10.0)
    node.motion.target("teleop", [1.0] * 20, 10.0)
    node.get_logger = lambda: SimpleNamespace(error=lambda _: None)
    monkeypatch.setattr(module.time, "monotonic", lambda: 10.1)

    async def ready(generation):
        node.motion.check_ready(10.1)

    node._wait_ready = ready
    return node


def test_control_enables_hardware_then_reanchors_motion(control):
    events = []

    async def hardware(enabled):
        events.append(enabled)
        assert not control.motion.enabled
        control.motion.observe([0.2] * 20, 10.1)

    control._hardware = hardware
    result = asyncio.run(control._enable(SimpleNamespace(data=True), SimpleNamespace()))
    assert result.success and events == [True]
    assert control.motion.output == (0.2,) * 20


def test_source_switch_during_enable_fences_late_hardware_result(control):
    events = []

    async def hardware(enabled):
        events.append(enabled)
        if enabled:
            control._select(SimpleNamespace(data=False), SimpleNamespace())

    control._hardware = hardware
    result = asyncio.run(control._enable(SimpleNamespace(data=True), SimpleNamespace()))
    assert not result.success and events == [True, False]
    assert not control.motion.enabled


def test_stop_can_cancel_pending_enable(control):
    events = []

    async def hardware(enabled):
        events.append(enabled)
        if enabled:
            await control._enable(SimpleNamespace(data=False), SimpleNamespace())

    control._hardware = hardware
    result = asyncio.run(control._enable(SimpleNamespace(data=True), SimpleNamespace()))
    assert not result.success and events == [True, False, False]
    assert not control.motion.enabled


def test_hardware_timeout_finishes_with_unknown_result(control):
    async def run():
        future = asyncio.get_running_loop().create_future()
        control.hardware = SimpleNamespace(service_is_ready=lambda: True,
                                          call_async=lambda request: future)

        def timer(period, callback):
            callback()
            return object()

        control.create_timer = timer
        control.destroy_timer = lambda timer: None
        with pytest.raises(TimeoutError, match="result unknown"):
            await control._hardware(True)

    asyncio.run(run())
