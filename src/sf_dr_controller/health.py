"""Health probes for primary/secondary accounts."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

from . import sql
from .config import AccountConfig
from .connection import SqlRunner

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProbeResult:
    account: str
    healthy: bool
    latency_ms: float
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class HealthProber:
    def __init__(self, runner: SqlRunner) -> None:
        self.runner = runner

    def probe(self, account: AccountConfig) -> ProbeResult:
        start = time.perf_counter()
        try:
            rows = self.runner.run(account, [sql.HEALTH_PROBE])
            ok = bool(rows and rows[0] and rows[0][0][0] == 1)
            err = None if ok else f"unexpected probe result: {rows!r}"
        except Exception as exc:  # any failure (network, auth, timeout) == unhealthy
            ok, err = False, f"{type(exc).__name__}: {exc}"
        latency = round((time.perf_counter() - start) * 1000, 1)
        return ProbeResult(account=account.label, healthy=ok, latency_ms=latency, error=err)

    def probe_both(self, primary: AccountConfig, secondary: AccountConfig) -> tuple[ProbeResult, ProbeResult]:
        """Probe both accounts concurrently so a hung primary does not delay the secondary check."""
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="probe") as pool:
            fp = pool.submit(self.probe, primary)
            fs = pool.submit(self.probe, secondary)
            return fp.result(), fs.result()

    def replication_lag_seconds(self, secondary: AccountConfig, database: str, group: str) -> int | None:
        """Lag measured on the secondary. Uses a warehouse -> call sparingly."""
        try:
            rows = self.runner.run(secondary, [sql.replication_lag(database, group)], use_warehouse=True)
            return int(rows[0][0][0]) if rows and rows[0] else None
        except Exception as exc:
            logger.warning("replication lag check failed: %s", exc)
            return None
