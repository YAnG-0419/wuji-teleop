import numpy as np

from wuji_control.contract import model_names
from .vendor.wuji_retargeting import Retargeter


class HandRetargeter:
    def __init__(self, config, side):
        self.retargeter = Retargeter.from_yaml(str(config), side)
        source = self.retargeter.optimizer.robot.dof_joint_names
        destination = model_names(side)
        if len(source) != 20 or set(source) != set(destination):
            raise ValueError("retarget model must contain the 20 named Hand 2 joints")
        self.order = np.asarray([source.index(name) for name in destination])
        self.limits = self.retargeter.optimizer.robot.joint_limits[self.order]

    def reset(self):
        self.retargeter.reset()

    def step(self, keypoints):
        points = np.asarray(keypoints, dtype=np.float64)
        if points.shape != (21, 3) or not np.isfinite(points).all():
            raise ValueError("expected 21 finite 3D landmarks in metres")
        palm = np.cross(points[5] - points[0], points[9] - points[0])
        if np.linalg.norm(palm) < 1e-7:
            raise ValueError("degenerate hand landmarks")
        output = self.retargeter.retarget(points)[self.order]
        if output.shape != (20,) or not np.isfinite(output).all():
            raise ValueError("retargeter produced invalid joint positions")
        if np.any(output < self.limits[:, 0] - 1e-6) or np.any(output > self.limits[:, 1] + 1e-6):
            raise ValueError("retargeter exceeded model limits")
        return np.clip(output.astype(np.float64), self.limits[:, 0], self.limits[:, 1])
