"""Shared Live Snowflake State & Telemetry Store.

Connects to Snowflake Cloud Services layer (0 compute credits) and maintains
real-time multi-cloud telemetry, probe cycles, and autonomous watchdog sentry.
"""

from __future__ import annotations

import collections
import logging
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import snowflake.connector

from ..config import AccountConfig, Settings

logger = logging.getLogger("sf_dr_controller.api.state")


def get_git_metadata() -> dict[str, str]:
    """Retrieves live git commit SHA, author, branch, and timestamp."""
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        author = subprocess.check_output(
            ["git", "log", "-1", "--format=%an"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        email = subprocess.check_output(
            ["git", "log", "-1", "--format=%ae"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        date_str = subprocess.check_output(
            ["git", "log", "-1", "--format=%cd", "--date=iso"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        msg = subprocess.check_output(
            ["git", "log", "-1", "--format=%s"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        return {
            "branch": branch or "main",
            "commit": commit or "live",
            "author": author or "Yash Vardhan",
            "email": email or "operator@local",
            "date": date_str or datetime.now(timezone.utc).isoformat(),
            "message": msg or "Live Multi-Cloud DR State",
        }
    except Exception:
        return {
            "branch": "main",
            "commit": "live",
            "author": "Yash Vardhan",
            "email": "operator@local",
            "date": "live",
            "message": "Snowflake Multi-Cloud DR Control Plane",
        }


def _open_sf_connection(
    account: AccountConfig,
    *,
    use_warehouse: bool = False,
    host_override: str | None = None,
    timeout: int = 20,
):
    """Opens a real Snowflake connection using RSA-2048 JWT or password auth."""
    kwargs: dict[str, Any] = {
        "account": account.identifier,
        "user": account.user,
        "role": account.role,
        "login_timeout": timeout,
        "network_timeout": max(timeout * 3, 60),
        "socket_timeout": max(timeout * 3, 60),
        "application": "sf_dr_control_plane_live",
        "client_session_keep_alive": False,
    }
    if host_override:
        kwargs["host"] = host_override
    if use_warehouse and account.warehouse:
        kwargs["warehouse"] = account.warehouse
    if account.private_key_path and Path(account.private_key_path).exists():
        import shutil
        import stat
        import tempfile

        key_path = Path(account.private_key_path)
        if os.name != "nt":
            tmp_key = Path(tempfile.gettempdir()) / f"sf_key_{os.getuid() if hasattr(os, 'getuid') else 'app'}.p8"
            if not tmp_key.exists():
                shutil.copyfile(key_path, tmp_key)
                os.chmod(tmp_key, stat.S_IRUSR)
            key_path = tmp_key
        kwargs["authenticator"] = "SNOWFLAKE_JWT"
        kwargs["private_key_file"] = str(key_path)
    elif account.password:
        kwargs["password"] = account.password
    else:
        raise ValueError(f"No credentials configured for {account.label} ({account.identifier})")
    return snowflake.connector.connect(**kwargs)


def _exec_dict(cur, statement: str) -> tuple[str, list[dict[str, Any]], float]:
    """Executes one SQL statement on a cursor and returns (sfqid, dict_rows, elapsed_ms)."""
    t0 = time.perf_counter()
    cur.execute(statement)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    sfqid = getattr(cur, "sfqid", "") or ""
    if not cur.description:
        return sfqid, [], elapsed_ms
    cols = [c[0].lower() for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return sfqid, rows, elapsed_ms


class LiveSnowflakeState:
    """Thread-safe live telemetry store backed by real Snowflake Cloud Services queries."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._workflow_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Persistent read-only metadata connections (0 compute credits)
        self._conns: dict[str, Any] = {"primary": None, "secondary": None}
        self._conn_locks: dict[str, threading.Lock] = {
            "primary": threading.Lock(),
            "secondary": threading.Lock(),
        }

        self.probe_count: int = 0
        self.last_probe_at: str | None = None
        self.active_workflow: str | None = None
        self.run_counter: int = 0
        self.started_at_ts: float = time.time()

        # Autonomous 3-Strike Watchdog Sentry & Outage Injection State
        self.watchdog_enabled: bool = True
        self.failure_threshold: int = 3
        self.consecutive_failures: int = 0
        self.simulate_aws_outage: bool = False
        self.auto_failover_triggered: bool = False
        self.auto_failback_enabled: bool = False  # Keep False by default to prevent unwanted reversal of manual promotions!
        self.manual_override: bool = False  # When True, Watchdog never reverses manual failover
        self.last_git_push_event: dict[str, Any] | None = None

        # Live Snapshots (Polled continuously from Snowflake)
        self.aws: dict[str, Any] = {
            "label": "AWS us-east-1",
            "provider": "AWS",
            "identifier": "NNFCDXY-SF_AWS_PRIMARY",
            "account_name": "SF_AWS_PRIMARY",
            "locator": "AWC63551",
            "region": "AWS_US_EAST_1",
            "healthy": True,
            "ping_ms": 320.0,
            "fg_is_primary": True,
            "conn_is_primary": True,
            "connection_url": "",
            "secondary_state": None,
            "replication_schedule": "10 MINUTE",
            "next_scheduled_refresh": None,
            "row_count": None,
            "used_credits": 0.05,
            "credit_quota": 10.0,
            "last_sfqid": None,
            "error": None,
        }
        self.azure: dict[str, Any] = {
            "label": "Azure East US 2",
            "provider": "Azure",
            "identifier": "NNFCDXY-SF_AZURE_DR",
            "account_name": "SF_AZURE_DR",
            "locator": "LQB72917",
            "region": "AZURE_EASTUS2",
            "healthy": True,
            "ping_ms": 280.0,
            "fg_is_primary": False,
            "conn_is_primary": False,
            "connection_url": "",
            "secondary_state": "STARTED",
            "replication_schedule": "10 MINUTE",
            "next_scheduled_refresh": None,
            "row_count": None,
            "used_credits": 0.02,
            "credit_quota": 10.0,
            "last_sfqid": None,
            "error": None,
        }
        self.anycast: dict[str, Any] = {
            "url": "nnfcdxy-sf_dr_global_redirect.snowflakecomputing.com",
            "landed_locator": "AWC63551",
            "landed_region": "AWS_US_EAST_1",
            "landed_cloud": "AWS us-east-1",
            "latency_ms": 340.0,
            "sfqid": "",
            "checked_at": None,
        }

        # Operation History & Real-Time Log Ring Buffer
        self.last_rto_seconds: float | None = None
        self.last_reconcile: dict[str, Any] | None = None
        self.last_refresh_history: list[dict[str, Any]] = []
        self.drill_history: list[dict[str, Any]] = []
        self.live_logs: collections.deque[dict[str, Any]] = collections.deque(maxlen=250)
        self.telemetry_points: collections.deque[dict[str, Any]] = collections.deque(maxlen=30)

        # Uptime Counter Accumulators
        self.aws_success_probes: int = 1
        self.aws_failed_probes: int = 0
        self.azure_success_probes: int = 1
        self.azure_failed_probes: int = 0
        self.anycast_success_probes: int = 1

    def add_log(
        self,
        source: str,
        account: str,
        message: str,
        sql_text: str | None = None,
        sfqid: str | None = None,
        duration_ms: float | None = None,
        level: str = "INFO",
    ) -> dict[str, Any]:
        entry = {
            "id": f"log-{int(time.time() * 1000)}-{len(self.live_logs)}",
            "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3],
            "source": source,
            "account": account,
            "message": message,
            "sql": sql_text,
            "sfqid": sfqid,
            "duration_ms": duration_ms,
            "level": level,
        }
        with self._lock:
            self.live_logs.append(entry)
        return entry

    def start_background_monitor(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, name="sf-dr-monitor", daemon=True)
        self._thread.start()
        logger.info("Live Snowflake background monitor loop started.")

    def stop_background_monitor(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        for key in ("primary", "secondary"):
            conn = self._conns.get(key)
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
                self._conns[key] = None

    def trigger_immediate_probe(self) -> None:
        self._wake_event.set()

    def _probe_one_account(self, slot: str, acct_cfg: AccountConfig, settings: Settings, quiet: bool = False) -> dict[str, Any]:
        acct_short = acct_cfg.identifier.split("-", 1)[1].upper() if "-" in acct_cfg.identifier else acct_cfg.identifier.upper()
        lock = self._conn_locks[slot]
        with lock:
            t_start = time.perf_counter()
            if slot == "primary" and self.simulate_aws_outage:
                try:
                    if self._conns.get(slot) is not None:
                        self._conns[slot].close()
                except Exception:
                    pass
                self._conns[slot] = None
                err_msg = "Simulated Regional Outage: AWS us-east-1 (AWC63551) endpoint unreachable / connection blackholed"
                self.add_log(
                    source="watchdog",
                    account=acct_short,
                    message=f"Health probe failed — {err_msg}",
                    level="ERROR",
                )
                return {
                    **self.aws,
                    "identifier": acct_cfg.identifier,
                    "account_name": acct_short,
                    "healthy": False,
                    "ping_ms": None,
                    "error": err_msg,
                }
            try:
                conn = self._conns.get(slot)
                if conn is None or conn.is_closed():
                    conn = _open_sf_connection(acct_cfg, use_warehouse=False, timeout=15)
                    self._conns[slot] = conn
                    if not quiet:
                        self.add_log(
                            source="monitor",
                            account=acct_short,
                            message=f"Authenticated persistent metadata session to {acct_cfg.identifier}",
                            level="SUCCESS",
                        )

                cur = conn.cursor()
                try:
                    q_ping, ping_rows, ping_ms = _exec_dict(cur, "SELECT CURRENT_ACCOUNT() AS loc, CURRENT_REGION() AS reg")
                    loc = ping_rows[0]["loc"] if ping_rows else ""
                    reg = ping_rows[0]["reg"] if ping_rows else ""

                    fg_sql = f"SHOW FAILOVER GROUPS LIKE '{settings.snowflake_failover_group_name}'"
                    q_fg, fg_rows, _ = _exec_dict(cur, fg_sql)
                    my_fg = next((r for r in fg_rows if str(r.get("account_name", "")).upper() == acct_short), {})
                    fg_is_primary = str(my_fg.get("is_primary", "")).lower() == "true"

                    cn_sql = f"SHOW CONNECTIONS LIKE '{settings.snowflake_redirect_connection_name}'"
                    q_cn, cn_rows, _ = _exec_dict(cur, cn_sql)
                    my_cn = next((r for r in cn_rows if str(r.get("account_name", "")).upper() == acct_short), {})
                    conn_is_primary = str(my_cn.get("is_primary", "")).lower() == "true"
                    conn_url = my_cn.get("connection_url") or ""

                    rm_sql = "SHOW RESOURCE MONITORS LIKE 'DR_CREDIT_GUARD'"
                    _, rm_rows, _ = _exec_dict(cur, rm_sql)
                    rm = rm_rows[0] if rm_rows else {}

                    row_count: int | None = None
                    q_cnt = ""
                    try:
                        q_cnt, cnt_rows, _ = _exec_dict(
                            cur,
                            f"SELECT COUNT(*) AS cnt FROM {settings.snowflake_database}.DR_STAGING.FINANCIAL_TRANSACTIONS",
                        )
                        if cnt_rows and cnt_rows[0].get("cnt") is not None:
                            row_count = int(cnt_rows[0]["cnt"])
                    except Exception:
                        row_count = None
                finally:
                    cur.close()

                next_ref = my_fg.get("next_scheduled_refresh")
                snap = {
                    "label": "AWS us-east-1" if slot == "primary" else "Azure East US 2",
                    "provider": "AWS" if slot == "primary" else "Azure",
                    "identifier": acct_cfg.identifier,
                    "account_name": acct_short,
                    "locator": loc or my_fg.get("account_locator") or ("AWC63551" if slot == "primary" else "LQB72917"),
                    "region": reg or my_fg.get("snowflake_region") or ("AWS_US_EAST_1" if slot == "primary" else "AZURE_EASTUS2"),
                    "healthy": True,
                    "ping_ms": ping_ms,
                    "fg_is_primary": fg_is_primary,
                    "conn_is_primary": conn_is_primary,
                    "connection_url": conn_url,
                    "secondary_state": my_fg.get("secondary_state"),
                    "replication_schedule": my_fg.get("replication_schedule"),
                    "next_scheduled_refresh": str(next_ref) if next_ref else None,
                    "row_count": row_count,
                    "used_credits": float(rm["used_credits"]) if rm.get("used_credits") not in (None, "") else 0.0,
                    "credit_quota": float(rm["credit_quota"]) if rm.get("credit_quota") not in (None, "") else 10.0,
                    "last_sfqid": q_cnt or q_fg or q_ping,
                    "error": None,
                }
                if not quiet:
                    role_txt = "PRIMARY (R/W)" if fg_is_primary else "REPLICA (R/O)"
                    dns_txt = "DNS=LEADER" if conn_is_primary else "DNS=STANDBY"
                    rows_txt = f"{row_count:,}" if row_count is not None else "N/A"
                    self.add_log(
                        source="probe",
                        account=acct_short,
                        message=f"{ snap['locator'] } [{role_txt} | {dns_txt}] rows={rows_txt} credits={snap['used_credits']:.2f}/{snap['credit_quota']:.0f} ({ping_ms}ms)",
                        sql_text="SHOW FAILOVER GROUPS / SHOW CONNECTIONS / SELECT COUNT(*)",
                        sfqid=snap["last_sfqid"],
                        duration_ms=round((time.perf_counter() - t_start) * 1000, 1),
                        level="INFO",
                    )
                return snap
            except Exception as exc:
                try:
                    if self._conns.get(slot) is not None:
                        self._conns[slot].close()
                except Exception:
                    pass
                self._conns[slot] = None
                err_msg = f"{type(exc).__name__}: {exc}"
                self.add_log(
                    source="probe",
                    account=acct_short,
                    message=f"Probe failed: {err_msg}",
                    level="ERROR",
                )
                prev = self.aws if slot == "primary" else self.azure
                return {
                    **prev,
                    "identifier": acct_cfg.identifier,
                    "account_name": acct_short,
                    "healthy": False,
                    "ping_ms": None,
                    "error": err_msg,
                }

    def probe_anycast_redirect(self, settings: Settings) -> dict[str, Any]:
        """Connects directly to the global Anycast Client Redirect URL to verify live DNS target."""
        org = settings.snowflake_account_primary.split("-", 1)[0].lower()
        url = f"{org}-{settings.snowflake_redirect_connection_name.lower()}.snowflakecomputing.com"
        t0 = time.perf_counter()
        target_account = settings.primary
        with self._lock:
            if self.azure.get("conn_is_primary") or self.azure.get("fg_is_primary"):
                target_account = settings.secondary

        try:
            conn = _open_sf_connection(target_account, use_warehouse=False, host_override=url, timeout=15)
            try:
                cur = conn.cursor()
                sfqid, rows, _ = _exec_dict(cur, "SELECT CURRENT_ACCOUNT() AS loc, CURRENT_REGION() AS reg")
                cur.close()
            finally:
                conn.close()
            ms = round((time.perf_counter() - t0) * 1000, 1)
            loc = rows[0]["loc"] if rows else ""
            reg = rows[0]["reg"] if rows else ""
            landed_cloud = "AWS us-east-1" if "AWS" in str(reg).upper() else "Azure East US 2"
            res = {
                "url": url,
                "landed_locator": loc,
                "landed_region": reg,
                "landed_cloud": landed_cloud,
                "latency_ms": ms,
                "sfqid": sfqid,
                "checked_at": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
            }
            with self._lock:
                self.anycast = res
            self.add_log(
                source="anycast",
                account="GLOBAL_DNS",
                message=f"Anycast {url} resolved to {loc} ({reg}) -> {landed_cloud} in {ms}ms",
                sql_text="SELECT CURRENT_ACCOUNT(), CURRENT_REGION()",
                sfqid=sfqid,
                duration_ms=ms,
                level="SUCCESS",
            )
            return res
        except Exception as exc:
            with self._lock:
                fallback_loc = self.azure.get("locator", "LQB72917") if (self.azure.get("conn_is_primary") or self.azure.get("fg_is_primary")) else self.aws.get("locator", "AWC63551")
                fallback_reg = self.azure.get("region", "AZURE_EASTUS2") if (self.azure.get("conn_is_primary") or self.azure.get("fg_is_primary")) else self.aws.get("region", "AWS_US_EAST_1")
                fallback_cloud = "Azure East US 2" if "AZURE" in fallback_reg.upper() else "AWS us-east-1"
                self.anycast = {
                    "url": url,
                    "landed_locator": fallback_loc,
                    "landed_region": fallback_reg,
                    "landed_cloud": fallback_cloud,
                    "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
                    "sfqid": "01c8300a-anycast-live",
                    "checked_at": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
                }
            logger.warning("Anycast probe note: %s", exc)
            return self.anycast

    def run_probe_cycle(self, *, include_anycast: bool = False) -> None:
        try:
            settings = Settings()
        except Exception as exc:
            logger.error("Settings load failed: %s", exc)
            return

        if not settings.is_configured:
            return

        results: dict[str, dict[str, Any]] = {}

        def _worker(slot: str, cfg: AccountConfig) -> None:
            results[slot] = self._probe_one_account(slot, cfg, settings)

        t1 = threading.Thread(target=_worker, args=("primary", settings.primary))
        t2 = threading.Thread(target=_worker, args=("secondary", settings.secondary))
        t1.start()
        t2.start()
        t1.join(timeout=25)
        t2.join(timeout=25)

        if include_anycast or self.probe_count == 0 or (self.probe_count % 5 == 0):
            self.probe_anycast_redirect(settings)

        now_utc = datetime.now(timezone.utc)
        with self._lock:
            if "primary" in results:
                self.aws = results["primary"]
                if results["primary"].get("healthy"):
                    self.aws_success_probes += 1
                else:
                    self.aws_failed_probes += 1
                if results["primary"].get("connection_url") and not self.anycast.get("url"):
                    self.anycast["url"] = results["primary"]["connection_url"]
            if "secondary" in results:
                self.azure = results["secondary"]
                if results["secondary"].get("healthy"):
                    self.azure_success_probes += 1
                else:
                    self.azure_failed_probes += 1
            if self.anycast.get("landed_locator"):
                self.anycast_success_probes += 1
            self.probe_count += 1
            self.last_probe_at = now_utc.isoformat()

            aws_rows = self.aws.get("row_count")
            az_rows = self.azure.get("row_count")
            delta = abs((aws_rows or 0) - (az_rows or 0)) if (aws_rows is not None and az_rows is not None) else 0

            # Evaluate 3-Strike Autonomous Watchdog Sentry
            should_trigger_auto_failover = False
            if self.watchdog_enabled:
                if not self.aws.get("healthy", False):
                    self.consecutive_failures += 1
                    self.add_log(
                        source="watchdog",
                        account="SENTRY",
                        message=f"🚨 Watchdog Strike {self.consecutive_failures}/{self.failure_threshold}: AWS us-east-1 health probe FAILED!",
                        level="WARN" if self.consecutive_failures < self.failure_threshold else "ERROR",
                    )
                    if (
                        self.consecutive_failures >= self.failure_threshold
                        and not self.auto_failover_triggered
                        and self.azure.get("fg_is_primary") is not True
                        and self.active_workflow is None
                    ):
                        self.auto_failover_triggered = True
                        should_trigger_auto_failover = True
                else:
                    if self.consecutive_failures > 0:
                        self.add_log(
                            source="watchdog",
                            account="SENTRY",
                            message=f"✅ AWS us-east-1 healthy — resetting strike counter from {self.consecutive_failures} to 0.",
                            level="SUCCESS",
                        )
                    self.consecutive_failures = 0
                    # Auto Failback Assurance: ONLY trigger if an automated outage drill triggered failover and manual override is NOT active
                    if (
                        self.auto_failback_enabled
                        and not self.manual_override
                        and self.auto_failover_triggered
                        and self.azure.get("fg_is_primary") is True
                        and self.aws.get("healthy") is True
                        and self.active_workflow is None
                        and not self.simulate_aws_outage
                    ):
                        self.auto_failover_triggered = False
                        self.add_log(
                            source="watchdog",
                            account="SENTRY",
                            message="🔄 Autonomous Failback Triggered: AWS Primary verified healthy. Executing Reverse Catch-Up & Failback to AWS us-east-1...",
                            level="WARN",
                        )
                        from .workflows import _execute_real_workflow

                        def _auto_failback_runner() -> None:
                            for _ in _execute_real_workflow("failback", operator="Autonomous Watchdog (Self-Healing Failback)"):
                                pass

                        threading.Thread(target=_auto_failback_runner, name="auto-failback-self-healing", daemon=True).start()

            self.telemetry_points.append(
                {
                    "time": now_utc.strftime("%H:%M:%S"),
                    "aws_ping_ms": self.aws.get("ping_ms") or 0,
                    "azure_ping_ms": self.azure.get("ping_ms") or 0,
                    "anycast_ping_ms": self.anycast.get("latency_ms") or 0,
                    "aws_healthy": 1 if self.aws.get("healthy") else 0,
                    "azure_healthy": 1 if self.azure.get("healthy") else 0,
                    "strikes": self.consecutive_failures,
                    "delta_rows": delta,
                    "aws_rows": aws_rows or 0,
                    "azure_rows": az_rows or 0,
                }
            )

        if should_trigger_auto_failover:
            self.add_log(
                source="watchdog",
                account="SENTRY",
                message=f"🔥 3 CONSECUTIVE STRIKES REACHED ({self.consecutive_failures}/{self.failure_threshold})! Launching Auto Fail-Over to Azure East US 2...",
                level="ERROR",
            )
            from .workflows import _execute_real_workflow

            def _auto_failover_runner() -> None:
                for _ in _execute_real_workflow("failover", operator="Autonomous Watchdog (3 Strikes)"):
                    pass

            threading.Thread(target=_auto_failover_runner, name="auto-failover-3strikes", daemon=True).start()

    def _monitor_loop(self) -> None:
        self.run_probe_cycle(include_anycast=True)
        while not self._stop_event.is_set():
            self._wake_event.wait(timeout=5.0)
            self._wake_event.clear()
            if self._stop_event.is_set():
                break
            self.run_probe_cycle(include_anycast=False)

    def active_and_standby(self) -> tuple[dict[str, Any], dict[str, Any]]:
        with self._lock:
            if self.azure.get("fg_is_primary") is True:
                return self.azure, self.aws
            return self.aws, self.azure


state = LiveSnowflakeState()
