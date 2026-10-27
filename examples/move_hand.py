import argparse
import json
from pathlib import Path

import rclpy
from wuji_control.client import WujiClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--side", choices=("left", "right"), default="right")
    parser.add_argument("--positions", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=2.0)
    args = parser.parse_args()
    goal = json.loads(args.positions.read_text())
    rclpy.init()
    try:
        with WujiClient(args.side) as hand:
            hand.move_to(goal, duration=args.duration)
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
