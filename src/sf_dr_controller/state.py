"""Failure-threshold state machine that decides when to fail over."""

from __future__ import annotations

from enum import Enum


class DRState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"  # primary failing, below threshold
    FAILING_OVER = "FAILING_OVER"  # failover decided / in progress
    FAILED_OVER = "FAILED_OVER"  # secondary is primary; manual failback required
    FAILOVER_ERROR = "FAILOVER_ERROR"


class Decision(str, Enum):
    NONE = "NONE"
    FAILOVER = "FAILOVER"


class FailoverStateMachine:
    """HEALTHY -> DEGRADED (n failures) -> FAILING_OVER (n >= threshold).

    Once failed over the machine latches: it never auto-fails back, preventing
    flapping / split-brain. Failback is an explicit operator action.
    """

    def __init__(self, threshold: int) -> None:
        if threshold < 1:
            raise ValueError("threshold must be >= 1")
        self.threshold = threshold
        self.state = DRState.HEALTHY
        self.consecutive_failures = 0

    def observe(self, primary_healthy: bool, secondary_healthy: bool = True) -> Decision:
        if self.state in (DRState.FAILING_OVER, DRState.FAILED_OVER, DRState.FAILOVER_ERROR):
            return Decision.NONE

        if primary_healthy:
            self.consecutive_failures = 0
            self.state = DRState.HEALTHY
            return Decision.NONE

        self.consecutive_failures += 1
        self.state = DRState.DEGRADED
        if self.consecutive_failures >= self.threshold and secondary_healthy:
            self.state = DRState.FAILING_OVER
            return Decision.FAILOVER
        return Decision.NONE

    def mark_failover_result(self, success: bool) -> None:
        self.state = DRState.FAILED_OVER if success else DRState.FAILOVER_ERROR

    def reset(self) -> None:
        self.state = DRState.HEALTHY
        self.consecutive_failures = 0
