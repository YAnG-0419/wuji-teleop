import argparse
import importlib
import os
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-only", action="store_true")
    args = parser.parse_args()
    expected = os.environ["WUJI_ROS_DISTRO"]
    actual = os.environ.get("ROS_DISTRO")
    version = "%d.%d" % sys.version_info[:2]
    if actual != expected:
        raise SystemExit("当前 Pixi 环境要求 ROS %s，请在干净终端 source /opt/ros/%s/setup.bash；当前 ROS_DISTRO=%s" % (expected, expected, actual))
    if version != os.environ["WUJI_PYTHON_VERSION"]:
        raise SystemExit("ROS %s 与 Python %s 不匹配" % (expected, version))
    modules = ["rclpy", "ament_index_python", "sensor_msgs.msg", "geometry_msgs.msg", "std_srvs.srv"]
    if not args.base_only:
        modules.extend(["wuji_hand_driver.node", "wuji_control.node", "wuji_control.client",
                        "wuji_teleop.node", "wuji_teleop.manus_node", "wuji_teleop.switch"])
    for module in modules:
        importlib.import_module(module)
    print("ROS %s / Python %s: imports passed; no device connection" % (expected, version))


if __name__ == "__main__":
    main()
