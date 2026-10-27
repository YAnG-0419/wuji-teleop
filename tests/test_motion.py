import pytest

from wuji_control.motion import Motion


def ready():
    motion = Motion([(-1, 2)] * 20)
    motion.observe([0.0] * 20, 10.0)
    motion.target("teleop", [1.0] * 20, 10.0)
    motion.enable(10.0)
    return motion


def test_selected_target_is_forwarded_without_rate_limiting():
    motion = ready()
    motion.target("program", [-0.9] * 20, 10.0)
    assert motion.next(10.001) == (1.0,) * 20
    motion.target("teleop", [-0.8] * 20, 10.002)
    assert motion.next(10.002) == (-0.8,) * 20


def test_expired_target_disables_and_requires_explicit_reenable():
    motion = ready()
    motion.observe([0.02] * 20, 10.3)
    assert motion.next(10.3) == (0.02,) * 20
    assert not motion.enabled
    motion.target("teleop", [1.0] * 20, 10.31)
    assert motion.next(10.31) is None


def test_expired_feedback_does_not_issue_hold_from_old_state():
    motion = ready()
    motion.target("teleop", [1.0] * 20, 10.3)
    with pytest.raises(RuntimeError, match="feedback expired"):
        motion.next(10.3)
    assert not motion.enabled


def test_source_change_disables_and_discards_old_targets():
    motion = ready()
    motion.select("program")
    assert motion.next(10.1) is None
    assert motion.targets == {}
    with pytest.raises(ValueError, match="limits"):
        motion.target("program", [3.0] * 20, 10.1)


def test_missing_feedback_and_backward_clock():
    motion = Motion([(-1, 2)] * 20)
    with pytest.raises(RuntimeError, match="feedback"):
        motion.enable(10.0)
    motion = ready()
    with pytest.raises(RuntimeError):
        motion.next(9.9)
    assert not motion.enabled


def test_bad_target_does_not_replace_valid_target():
    motion = ready()
    with pytest.raises(ValueError, match="finite"):
        motion.target("teleop", [float("nan")] * 20, 10.05)
    assert motion.next(10.1) == (1.0,) * 20
