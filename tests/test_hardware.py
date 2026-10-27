import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def driver(monkeypatch):
    for name in ("rclpy", "rclpy.node", "rclpy.qos", "sensor_msgs", "sensor_msgs.msg", "std_srvs", "std_srvs.srv"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    sys.modules["rclpy.node"].Node = object
    sys.modules["rclpy.qos"].qos_profile_sensor_data = None
    sys.modules["sensor_msgs.msg"].JointState = object
    sys.modules["std_srvs.srv"].SetBool = object
    path = Path(__file__).parents[1] / "hardware/wuji_hand_driver/wuji_hand_driver/node.py"
    spec = importlib.util.spec_from_file_location("hardware_under_test", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    node = object.__new__(module.WujiHand2DriverNode)
    options = {"command_timeout_sec": 0.3, "feedback_timeout_sec": 0.25, "enable_timeout_sec": 0.01}
    node.get_parameter = lambda key: SimpleNamespace(value=options[key])
    node.get_logger = lambda: SimpleNamespace(error=lambda message: None)
    node._enabled_by_driver = True
    node._last_feedback_at = 10.0
    node._last_command_at = 10.0
    node.events = []
    node._hand = SimpleNamespace(disable=lambda: node.events.append("disable"),
                                 enable=lambda: node.events.append("enable"))
    monkeypatch.setattr(module.time, "monotonic", lambda: 10.1)
    return module, node


def test_hardware_watchdog_disables_expired_command_with_fresh_feedback(driver, monkeypatch):
    module, node = driver
    monkeypatch.setattr(module.time, "monotonic", lambda: 10.4)
    node._last_feedback_at = 10.4
    node._watchdog()
    assert node.events == ["disable"]
    assert not node._enabled_by_driver
    node._watchdog()
    assert node.events == ["disable"]


def test_hardware_watchdog_disables_expired_feedback(driver, monkeypatch):
    module, node = driver
    monkeypatch.setattr(module.time, "monotonic", lambda: 10.3)
    node._last_command_at = 10.3
    node._watchdog()
    assert node.events == ["disable"]


def test_disabled_hardware_rejects_commands_and_enable_needs_feedback(driver):
    _, node = driver
    node._enabled_by_driver = False
    node._on_command(object())
    assert node.events == []
    node._last_feedback_at = None
    result = node._set_enabled(SimpleNamespace(data=True), SimpleNamespace())
    assert not result.success and node.events == []


def test_enable_failure_disables_motor_before_returning_error(driver):
    _, node = driver
    node._enabled_by_driver = False

    def fail(timeout):
        raise RuntimeError("diagnostics did not confirm enable")

    node._wait_until_enabled = fail
    result = node._set_enabled(SimpleNamespace(data=True), SimpleNamespace())
    assert not result.success
    assert node.events == ["enable", "disable"]
    assert not node._enabled_by_driver
