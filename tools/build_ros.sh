#!/usr/bin/env bash
set -euo pipefail

python tools/check_ros.py --base-only
exec colcon --log-base "$WUJI_LOG_BASE" build \
    --base-paths hardware control teleop --symlink-install --executor sequential \
    --build-base "$WUJI_BUILD_BASE" --install-base "$WUJI_INSTALL_BASE"
