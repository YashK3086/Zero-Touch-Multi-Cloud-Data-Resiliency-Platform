"""Failover / failback execution with per-step timing (feeds RTO benchmarks)."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from . import sql
from .config import AccountConfig
from .connection import SqlRunner

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    name: str
    statement: str
    seconds: float
    ok: bool
    error: str | None = None


@dataclass
class FailoverReport:
    operation: str  # "failover" | "failback"
    target_account: str
    started_at: str
    dry_run: bool
    steps: list[StepResult] = field(default_factory=list)
    total_seconds: float = 0.0
    success: bool = False
    replication_lag_seconds: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class FailoverExecutor:
    def __init__(self, runner: SqlRunner, failover_group: str, connection: str, *, dry_run: bool = False) -> None:
        self.runner = runner
        self.group = sql.validate_identifier(failover_group)
        self.connection = sql.validate_identifier(connection)
        self.dry_run = dry_run

    def _execute(self, op: str, target: AccountConfig, steps: list[tuple[str, str]]) -> FailoverReport:
        report = FailoverReport(
            operation=op,
            target_account=target.label,
            started_at=datetime.now(timezone.utc).isoformat(),
            dry_run=self.dry_run,
        )
        t0 = time.perf_counter()
        for name, stmt in steps:
            s0 = time.perf_counter()
            if self.dry_run:
                logger.warning("[DRY-RUN] %s on %s: %s", name, target.label, stmt)
                report.steps.append(StepResult(name, stmt, 0.0, True))
                continue
            try:
                self.runner.run(target, [stmt])
                report.steps.append(StepResult(name, stmt, round(time.perf_counter() - s0, 3), True))
                logger.info("%s step '%s' OK on %s", op, name, target.label)
            except Exception as exc:
                report.steps.append(
                    StepResult(name, stmt, round(time.perf_counter() - s0, 3), False, f"{type(exc).__name__}: {exc}")
                )
                logger.error("%s step '%s' FAILED on %s: %s", op, name, target.label, exc)
                break
        report.total_seconds = round(time.perf_counter() - t0, 3)
        report.success = all(s.ok for s in report.steps) and len(report.steps) == len(steps)
        return report

    def failover(self, secondary: AccountConfig) -> FailoverReport:
        """Run on the SECONDARY: promote replicated data first, then move client traffic."""
        return self._execute(
            "failover",
            secondary,
            [
                ("promote_failover_group", sql.promote_failover_group(self.group)),
                ("promote_client_redirect", sql.promote_connection(self.connection)),
            ],
        )

    def failback(self, original_primary: AccountConfig) -> FailoverReport:
        """Run on the ORIGINAL primary once healthy: catch up, promote, redirect."""
        return self._execute(
            "failback",
            original_primary,
            [
                ("refresh_failover_group", sql.refresh_failover_group(self.group)),
                ("promote_failover_group", sql.promote_failover_group(self.group)),
                ("promote_client_redirect", sql.promote_connection(self.connection)),
            ],
        )
