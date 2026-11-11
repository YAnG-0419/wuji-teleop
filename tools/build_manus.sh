#!/usr/bin/env bash
set -euo pipefail

cmake -S teleop/manus_bridge -B "$WUJI_BUILD_BASE/manus_bridge" -G Ninja
cmake --build "$WUJI_BUILD_BASE/manus_bridge"
