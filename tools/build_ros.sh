#!/usr/bin/env bash
set -euo pipefail

if [[ "${ROS_DISTRO:-}" != foxy ]]; then
    echo '请先在干净终端 source /opt/ros/foxy/setup.bash；当前工程固定使用 Foxy/Python 3.8。' >&2
    exit 1
fi
python -c 'import sys; assert sys.version_info[:2] == (3, 8); import rclpy, ament_index_python'
exec colcon build --base-paths hardware control teleop --symlink-install --executor sequential
