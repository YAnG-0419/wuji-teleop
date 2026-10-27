from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from wuji_control.contract import joint_names, model_names, ordered_positions
from wuji_teleop.retarget import HandRetargeter


ROOT = Path(__file__).parents[1]


def landmarks():
    points = np.zeros((21, 3))
    for finger, x in enumerate([-0.04, -0.03, -0.01, 0.01, 0.03]):
        for j in range(4):
            points[1 + finger * 4 + j] = (x, 0.03 * (j + 1), 0.005 * finger)
    return points


@pytest.mark.parametrize("side", ["left", "right"])
def test_real_retarget_named_order_limits_and_reset(side):
    config = ROOT / "teleop/wuji_teleop/config" / ("retarget_manus_wuji_hand_2_" + side + ".yaml")
    hand = HandRetargeter(config, side)
    assert hand.order.tolist() == [16, 17, 18, 19, 0, 1, 2, 3, 4, 5, 6, 7, 12, 13, 14, 15, 8, 9, 10, 11]
    assert tuple(hand.retargeter.optimizer.robot.dof_joint_names[i] for i in hand.order) == model_names(side)
    result = hand.step(landmarks())
    assert result.shape == (20,) and np.isfinite(result).all()
    assert np.all(result >= hand.limits[:, 0])
    assert np.all(result <= hand.limits[:, 1])
    hand.reset()
    np.testing.assert_allclose(hand.step(landmarks()), result, atol=1e-6)
    with pytest.raises(ValueError, match="degenerate"):
        hand.step(np.zeros((21, 3)))


def test_wire_joint_names_are_explicit_and_reordered():
    names = joint_names("right")
    message = SimpleNamespace(name=list(reversed(names)), position=list(range(20)))
    assert ordered_positions(message, names) == tuple(reversed(range(20)))
    message.name[0] = message.name[1]
    with pytest.raises(ValueError, match="exactly once"):
        ordered_positions(message, names)


def test_manus_native_bridge_loads_without_connecting():
    from wuji_teleop.manus import ManusBridge
    library = ROOT / "build/manus_bridge/libmanus_skeleton_bridge.so"
    if not library.is_file():
        pytest.skip("run pixi run --locked build-manus to check the optional bridge")
    bridge = ManusBridge(library)
    assert not bridge.connected
    bridge.close()
