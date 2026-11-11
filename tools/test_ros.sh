#!/usr/bin/env bash
set -euo pipefail

python tools/check_ros.py
export ROS_LOCALHOST_ONLY=1
export ROS_DOMAIN_ID=191
export ROS_LOG_DIR="$PWD/$WUJI_LOG_BASE/ros-smoke"
export WUJI_ROS_TESTS=1
exec python -m pytest tests/ros -q
