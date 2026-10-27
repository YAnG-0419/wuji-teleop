import math


class Motion:
    def __init__(self, limits, *, timeout=0.25, source="teleop"):
        self.limits = tuple(tuple(pair) for pair in limits)
        if len(self.limits) != 20 or any(
            len(pair) != 2 or not all(math.isfinite(v) for v in pair) or pair[0] >= pair[1]
            for pair in self.limits
        ):
            raise ValueError("expected 20 finite ordered joint limits")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive")
        self.timeout = timeout
        self.enabled = False
        self.feedback = None
        self.feedback_at = None
        self.targets = {}
        self.output = None
        self.last_at = None
        self.select(source)

    def select(self, source):
        if source not in ("teleop", "program"):
            raise ValueError("source must be teleop or program")
        self.source = source
        self.enabled = False
        self.targets.clear()

    def _vector(self, values, *, bounded):
        values = tuple(float(v) for v in values)
        if len(values) != 20 or not all(math.isfinite(v) for v in values):
            raise ValueError("expected 20 finite joint positions")
        if bounded and any(v < lo or v > hi for v, (lo, hi) in zip(values, self.limits)):
            raise ValueError("target exceeds joint limits")
        return values

    def observe(self, positions, now):
        self.feedback = self._vector(positions, bounded=False)
        self.feedback_at = now

    def target(self, source, positions, now):
        if source not in ("teleop", "program"):
            raise ValueError("unknown target source")
        self.targets[source] = (self._vector(positions, bounded=True), now)

    def _fresh(self, timestamp, now):
        return timestamp is not None and 0 <= now - timestamp <= self.timeout

    def enable(self, now):
        if not self._fresh(self.feedback_at, now):
            raise RuntimeError("fresh measured feedback required")
        target = self.targets.get(self.source)
        if target is None or not self._fresh(target[1], now):
            raise RuntimeError("fresh selected target required")
        self._vector(self.feedback, bounded=True)
        self.output = self.feedback
        self.last_at = now
        self.enabled = True

    def disable(self):
        self.enabled = False

    def next(self, now):
        if not self.enabled:
            return None
        if not self._fresh(self.feedback_at, now):
            self.disable()
            raise RuntimeError("feedback expired; motion disabled")
        target = self.targets.get(self.source)
        if target is None or not self._fresh(target[1], now):
            self.disable()
            return self.feedback
        if now < self.last_at:
            self.disable()
            raise RuntimeError("clock moved backwards; motion disabled")
        self.output = target[0]
        self.last_at = now
        return self.output
