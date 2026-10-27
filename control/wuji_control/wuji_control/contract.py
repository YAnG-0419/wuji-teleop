import math


FINGERS = ("thumb", "index_finger", "middle_finger", "ring_finger", "pinky")


def joint_names(side):
    if side not in ("left", "right"):
        raise ValueError("side must be left or right")
    return tuple("%s_finger%d_joint%d" % (side, finger, joint)
                 for finger in range(1, 6) for joint in range(1, 5))


def model_names(side):
    joint_names(side)
    result = []
    for finger in FINGERS:
        suffixes = ("cmc_flex", "cmc_abd", "mcp", "ip") if finger == "thumb" else (
            "mcp_flex", "mcp_abd", "pip", "dip")
        result.extend("%s_%s_%s" % (side[0], finger, suffix) for suffix in suffixes)
    return tuple(result)


def ordered_positions(message, expected):
    names, positions = tuple(message.name), tuple(message.position)
    if len(names) != 20 or len(set(names)) != 20 or set(names) != set(expected):
        raise ValueError("message must name all 20 joints exactly once")
    if len(positions) != 20 or not all(math.isfinite(v) for v in positions):
        raise ValueError("message must contain 20 finite positions")
    values = dict(zip(names, positions))
    return tuple(values[name] for name in expected)


def fresh_stamp(stamp, now, timeout=0.25):
    sampled = stamp.sec + stamp.nanosec / 1e9
    return sampled > 0 and -0.05 <= now - sampled <= timeout
