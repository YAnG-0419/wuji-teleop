import pytest

from wuji_teleop.switch import TeleopSwitch, keyboard


def test_start_selects_teleop_then_enables_control():
    calls = []
    switch = TeleopSwitch(lambda service, value: calls.append((service, value)))
    switch.start()
    assert calls == [("select_teleop", True), ("enable", True)]


def test_stop_attempts_hardware_disable_when_control_unavailable():
    calls = []

    def call(service, value):
        calls.append((service, value))
        if service == "enable":
            raise TimeoutError("control unavailable")

    with pytest.raises(RuntimeError, match="未完全确认"):
        TeleopSwitch(call).stop()
    assert calls == [("enable", False), ("hardware_enable", False)]


def test_failed_start_cleans_up_both_outputs():
    calls = []

    def call(service, value):
        calls.append((service, value))
        if service == "enable" and value:
            raise RuntimeError("missing fresh target")

    with pytest.raises(RuntimeError, match="missing fresh target"):
        TeleopSwitch(call).start()
    assert calls[-2:] == [("enable", False), ("hardware_enable", False)]


@pytest.mark.parametrize("ending", ["q", EOFError(), KeyboardInterrupt()])
def test_keyboard_opens_disengaged_and_stops_on_exit(ending):
    calls = []
    commands = iter(["s", "x", ending])

    def read(prompt):
        command = next(commands)
        if isinstance(command, BaseException):
            raise command
        return command

    keyboard(TeleopSwitch(lambda service, value: calls.append((service, value))),
             read=read, write=lambda message: None)
    assert calls[:2] == [("enable", False), ("hardware_enable", False)]
    assert calls[2:4] == [("select_teleop", True), ("enable", True)]
    assert calls[-2:] == [("enable", False), ("hardware_enable", False)]
