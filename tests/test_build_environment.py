import os
from pathlib import Path
import subprocess
import sys


def test_wrong_ros_distribution_is_rejected_before_imports():
    root = Path(__file__).parents[1]
    environment = {**os.environ, "ROS_DISTRO": "wrong_distribution"}
    result = subprocess.run([sys.executable, str(root / "tools/check_ros.py"), "--base-only"],
                            env=environment, capture_output=True, text=True)
    assert result.returncode != 0
    assert "wrong_distribution" in result.stderr
    assert "/opt/ros/" + environment["WUJI_ROS_DISTRO"] in result.stderr


def test_python_version_matches_selected_environment():
    assert "%d.%d" % sys.version_info[:2] == os.environ["WUJI_PYTHON_VERSION"]
