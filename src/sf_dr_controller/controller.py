"""
Automated Snowflake Health Monitor and Failover Controller.

Monitors the primary Snowflake account and, after N consecutive failed probes,
promotes the secondary Failover Group and Client Redirect Connection.
"""

from __future__ import annotations

import logging
import signal
import threading
from collections.abc import Callable

from .config import Settings
from .connection import SqlRunner
from .failover import FailoverExecutor, FailoverReport
from .health import HealthProber
from .notifications import NotificationService
from .state import Decision, DRState, FailoverStateMachine

logger = logging.getLogger("sf_dr_controller")


class SnowflakeDRController:
    """Monitors Primary Snowflake Account health and triggers Client Redirect
    and Failover Group switchover upon failure.
    """

    def __init__(self, settings: Settings, runner: SqlRunner) -> None:
        self.settings = settings
        self.prober = HealthProber(runner)
        self.state = FailoverStateMachine(settings.dr_failure_threshold)
        self.executor = FailoverExecutor(
            runner,
            settings.snowflake_failover_group_name,
            settings.snowflake_redirect_connection_name,
            dry_run=settings.dr_dry_run,
        )
        self.notifier = NotificationService(settings.dr_webhook_url)
        self._stop = threading.Event()
        self.last_report: FailoverReport | None = None

    # -- single iteration ---------------------------------------------------
    def tick(self) -> DRState:
        p, s = self.prober.probe_both(self.settings.primary, self.settings.secondary)
        prev_failures = self.state.consecutive_failures
        decision = self.state.observe(p.healthy, s.healthy)
        logger.info(
            "probe",
            extra={
                "event": "probe",
                "state": self.state.state.value,
                "consecutive_failures": self.state.consecutive_failures,
                "primary": p.to_dict(),
                "secondary": s.to_dict(),
            },
        )
        if not p.healthy and not s.healthy:
            logger.critical("BOTH accounts unhealthy - failover impossible", extra={"event": "dual_outage"})
            self.notifier.send_alert(
                "DUAL CLOUD OUTAGE DETECTED",
                "Both Primary (AWS) and Secondary (Azure) Snowflake accounts are reporting UNHEALTHY!",
                level="CRITICAL",
                fields={"Primary": p.error or "Down", "Secondary": s.error or "Down"},
            )

        if not p.healthy and self.state.consecutive_failures > prev_failures:
            # Emit strike warning
            strikes = self.state.consecutive_failures
            max_s = self.settings.dr_failure_threshold
            self.notifier.send_alert(
                f"Heartbeat Failure ({strikes}/{max_s})",
                f"Primary probe failed. Strike count: {strikes}/{max_s}.",
                level="WARNING" if strikes < max_s else "CRITICAL",
                fields={
                    "Primary Account": self.settings.primary.identifier,
                    "Error": p.error or "Probe timeout / connection failure",
                },
            )

        if decision is Decision.FAILOVER:
            if self.settings.dr_auto_failover:
                self.trigger_failover()
            else:
                logger.critical(
                    "Failover threshold reached; auto-failover disabled - operator action required",
                    extra={"event": "failover_required"},
                )
                self.notifier.send_alert(
                    "AUTOMATIC FAILOVER REQUIRED",
                    "3-Strike threshold reached on AWS Primary, but auto-failover is disabled in configuration.",
                    level="CRITICAL",
                    fields={"Target Secondary": self.settings.secondary.identifier},
                )
        return self.state.state

    def trigger_failover(self) -> FailoverReport:
        """Promotes Secondary Failover Group to Primary and redirects global Connection handle to Azure."""
        logger.critical(
            "Triggering failover",
            extra={
                "event": "failover_start",
                "from": self.settings.primary.identifier,
                "to": self.settings.secondary.identifier,
            },
        )
        msg = (
            f"Switching active database and global client redirection from "
            f"AWS ({self.settings.primary.identifier}) to Azure ({self.settings.secondary.identifier})."
        )
        self.notifier.send_alert(
            "INITIATING AUTONOMOUS ZERO-TOUCH FAILOVER",
            msg,
            level="CRITICAL",
            fields={"Trigger": "3-Strike Watchdog Expiry", "Destination Cloud": "Azure East US 2"},
        )
        report = self.executor.failover(self.settings.secondary)
        self.state.mark_failover_result(report.success)
        self.last_report = report
        logger.critical("Failover finished", extra={"event": "failover_end", "report": report.to_dict()})
        step_summary = ", ".join(f"{s.name}: {'OK' if s.ok else 'FAIL'}" for s in report.steps)
        self.notifier.send_alert(
            "FAILOVER COMPLETE" if report.success else "FAILOVER FAILED",
            f"Failover completed in {report.total_seconds:.2f}s." if report.success else "Failover execution failed.",
            level="SUCCESS" if report.success else "CRITICAL",
            fields={
                "RTO Duration": f"{report.total_seconds:.2f}s",
                "Status": "ACTIVE ON AZURE" if report.success else "ERROR",
                "Steps": step_summary,
            },
        )
        return report

    # -- loop ---------------------------------------------------------------
    def stop(self, *_: object) -> None:
        self._stop.set()

    def run_forever(self, max_ticks: int | None = None, on_tick: Callable[[DRState], None] | None = None) -> None:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self.stop)
            except ValueError:  # not in main thread (tests)
                pass
        ticks = 0
        logger.info(
            "controller started",
            extra={
                "event": "start",
                "dry_run": self.settings.dr_dry_run,
                "threshold": self.settings.dr_failure_threshold,
            },
        )
        while not self._stop.is_set():
            st = self.tick()
            ticks += 1
            if on_tick:
                on_tick(st)
            if st in (DRState.FAILED_OVER, DRState.FAILOVER_ERROR):
                logger.warning("controller latched in %s - exiting loop", st.value)
                break
            if max_ticks is not None and ticks >= max_ticks:
                break
            self._stop.wait(self.settings.dr_probe_interval_seconds)
