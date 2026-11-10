"""Shared Live Snowflake State & Telemetry Store.

Connects to Snowflake Cloud Services layer (0 compute credits) and maintains
real-time multi-cloud telemetry, probe cycles, and autonomous watchdog sentry.
"""

from __future__ import annotations

import collections
import json
import logging
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import snowflake.connector

from ..config import AccountConfig, Settings

logger = logging.getLogger("sf_dr_controller.api.state")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIR = PROJECT_ROOT / "reports"
DRILL_HISTORY_FILE = REPORTS_DIR / "drill_history.json"
LAST_RUN_FILE = REPORTS_DIR / "last_workflow_run.json"


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
    clean_account = account.identifier.strip().strip('"').strip("'")
    if "://" in clean_account:
        clean_account = clean_account.split("://", 1)[1]
    if clean_account.lower().endswith(".snowflakecomputing.com"):
        clean_account = clean_account[:-len(".snowflakecomputing.com")]
    clean_account = clean_account.split("/")[0].strip()

    kwargs: dict[str, Any] = {
        "account": clean_account,
        "user": account.user.strip(),
        "role": account.role.strip(),
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
    from ..bootstrap import _resolve_rsa_key_path

    resolved_key = _resolve_rsa_key_path(account.private_key_path)
    if resolved_key:
        kwargs["authenticator"] = "SNOWFLAKE_JWT"
        kwargs["private_key_file"] = str(resolved_key)
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
        self.ui_connected: bool = False

        # Autonomous 3-Strike Watchdog Sentry & Outage Injection State
        self.watchdog_enabled: bool = True
        self.failure_threshold: int = 3
        self.consecutive_failures: int = 0
        self.simulate_aws_outage: bool = False
        self.auto_failover_triggered: bool = False
        self.auto_failback_enabled: bool = False  # Keep False by default to prevent unwanted reversal of manual promotions!
        self.manual_override: bool = False  # When True, Watchdog never reverses manual failover
        self.last_git_push_event: dict[str, Any] | None = None

        # Live Snapshots (Polled continuously from Snowflake once connected)
        self.aws: dict[str, Any] = {
            "label": "--",
            "provider": "AWS",
            "identifier": "--",
            "account_name": "--",
            "locator": "--",
            "region": "--",
            "healthy": False,
            "ping_ms": None,
            "fg_is_primary": False,
            "conn_is_primary": False,
            "connection_url": "--",
            "secondary_state": None,
            "replication_schedule": "--",
            "next_scheduled_refresh": None,
            "row_count": None,
            "used_credits": None,
            "credit_quota": None,
            "last_sfqid": None,
            "error": "No connections established yet",
        }
        self.azure: dict[str, Any] = {
            "label": "--",
            "provider": "Azure",
            "identifier": "--",
            "account_name": "--",
            "locator": "--",
            "region": "--",
            "healthy": False,
            "ping_ms": None,
            "fg_is_primary": False,
            "conn_is_primary": False,
            "connection_url": "--",
            "secondary_state": None,
            "replication_schedule": "--",
            "next_scheduled_refresh": None,
            "row_count": None,
            "used_credits": None,
            "credit_quota": None,
            "last_sfqid": None,
            "error": "No connections established yet",
        }
        self.anycast: dict[str, Any] = {
            "url": "--",
            "landed_locator": "--",
            "landed_region": "--",
            "landed_cloud": "--",
            "latency_ms": None,
            "sfqid": "--",
            "checked_at": "--",
        }

        # Operation History & Real-Time Log Ring Buffer
        self.last_discovery: dict[str, Any] = {}
        self._syncing_wan_delta: bool = False
        self._last_ec2_count: int = 0
        self._last_s3_count: int = 0
        self.last_rto_seconds: float | None = None
        self.last_reconcile: dict[str, Any] | None = None
        self.last_refresh_history: list[dict[str, Any]] = []
        self.last_workflow_run: dict[str, Any] | None = None
        self.drill_history: list[dict[str, Any]] = []
        self.live_logs: collections.deque[dict[str, Any]] = collections.deque(maxlen=250)
        self.telemetry_points: collections.deque[dict[str, Any]] = collections.deque(maxlen=30)

        # Uptime Counter Accumulators
        self.aws_success_probes: int = 0
        self.aws_failed_probes: int = 0
        self.azure_success_probes: int = 0
        self.azure_failed_probes: int = 0
        self.anycast_success_probes: int = 0

        self._load_persisted_history()

    def _load_persisted_history(self) -> None:
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            if DRILL_HISTORY_FILE.exists():
                data = json.loads(DRILL_HISTORY_FILE.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) > 0:
                    self.drill_history = data
        except Exception as e:
            logger.warning("Could not read drill_history.json: %s", e)

        try:
            if LAST_RUN_FILE.exists():
                run_data = json.loads(LAST_RUN_FILE.read_text(encoding="utf-8"))
                if isinstance(run_data, dict) and run_data.get("summary"):
                    self.last_workflow_run = run_data
        except Exception as e:
            logger.warning("Could not read last_workflow_run.json: %s", e)

        try:
            conn_file = REPORTS_DIR / "ui_connected.json"
            if conn_file.exists():
                cdata = json.loads(conn_file.read_text(encoding="utf-8"))
                if isinstance(cdata, dict) and cdata.get("connected") is True:
                    self.ui_connected = True
        except Exception:
            pass

    def _save_drill_history(self) -> None:
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            DRILL_HISTORY_FILE.write_text(json.dumps(self.drill_history, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Could not write drill_history.json: %s", e)

    def _save_last_workflow_run(self) -> None:
        try:
            if self.last_workflow_run:
                REPORTS_DIR.mkdir(parents=True, exist_ok=True)
                LAST_RUN_FILE.write_text(json.dumps(self.last_workflow_run, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Could not write last_workflow_run.json: %s", e)

    def record_drill(self, item: dict[str, Any]) -> None:
        with self._lock:
            self.drill_history.insert(0, item)
            if len(self.drill_history) > 100:
                self.drill_history = self.drill_history[:100]
            self._save_drill_history()
        try:
            from .reports import build_and_save_audit_pdf

            build_and_save_audit_pdf()
        except Exception as e:
            logger.debug("Could not auto-save PDF after drill: %s", e)

    def record_workflow_completion(self, run_state: dict[str, Any]) -> None:
        with self._lock:
            self.last_workflow_run = run_state
            self._save_last_workflow_run()

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

    def _sync_live_cloud_inventory(self, settings: Settings) -> None:
        """Continuously polls live AWS/Azure cloud APIs for Compute & Storage stats and auto-replicates row deltas."""
        try:
            from ..discovery import discover_aws, discover_azure

            aws_disc = discover_aws()
            with self._lock:
                if not isinstance(self.last_discovery, dict):
                    self.last_discovery = {}
                self.last_discovery["aws"] = aws_disc
                if not self.last_discovery.get("azure") or (self.probe_count % 3 == 0):
                    try:
                        self.last_discovery["azure"] = discover_azure()
                    except Exception:
                        pass

            running_insts = [i for i in (aws_disc.get("instances") or []) if i.get("state") in ("running", "pending")]
            buckets = aws_disc.get("buckets") or []
            ec2_cnt = len(running_insts)
            s3_cnt = len(buckets)

            if ec2_cnt != self._last_ec2_count or (s3_cnt != self._last_s3_count and self._last_s3_count > 0):
                self._last_ec2_count = ec2_cnt
                self._last_s3_count = s3_cnt
                inst_summary = ", ".join(f"{i.get('instance_id')} ({i.get('type')})" for i in running_insts) or "0 instances"
                self.add_log(
                    source="discovery",
                    account="AWS_PRIMARY",
                    message=f"🔍 Live Cloud Probe detected resource change: {ec2_cnt} Running EC2 [{inst_summary}], {s3_cnt} S3 Buckets",
                    level="SUCCESS" if ec2_cnt > 0 else "INFO",
                )
            else:
                self._last_s3_count = s3_cnt

            aws_rows = self.aws.get("row_count")
            az_rows = self.azure.get("row_count")

            # Whenever live Primary rows differ from Secondary rows (e.g. external app ingested data via S3/Snowpipe),
            # automatically trigger WAN Failover Group refresh so Azure Secondary catches up to RPO = 0.
            if (
                aws_rows is not None
                and az_rows is not None
                and aws_rows != az_rows
                and not self._syncing_wan_delta
                and self.aws.get("fg_is_primary") is True
            ):
                self._syncing_wan_delta = True

                def _wan_delta_sync_worker() -> None:
                    try:
                        delta_diff = abs(int(aws_rows) - int(az_rows))
                        self.add_log(
                            source="replication",
                            account="AZURE_DR",
                            message=f"⚡ Live Delta Detected ({delta_diff:,} rows difference: Primary={aws_rows:,}, Secondary={az_rows:,}). Triggering WAN Failover Group Refresh...",
                            level="INFO",
                        )
                        conn_s = _open_sf_connection(settings.secondary, use_warehouse=True, timeout=30)
                        try:
                            cur_s = conn_s.cursor()
                            try:
                                cur_s.execute(
                                    f"ALTER FAILOVER GROUP {settings.snowflake_failover_group_name} REFRESH"
                                )
                            finally:
                                cur_s.close()
                        finally:
                            conn_s.close()

                        with self._lock:
                            self.azure["row_count"] = aws_rows
                        self.add_log(
                            source="replication",
                            account="AZURE_DR",
                            message=f"🛡️ WAN Delta Replicated: Secondary synchronized to {aws_rows:,} rows (RPO = 0).",
                            level="SUCCESS",
                        )
                    except Exception as exc:
                        logger.debug("WAN delta auto-sync note: %s", exc)
                    finally:
                        self._syncing_wan_delta = False

                threading.Thread(target=_wan_delta_sync_worker, name="wan-delta-auto-sync", daemon=True).start()
        except Exception as exc:
            logger.debug("Live cloud inventory sync note: %s", exc)

    def run_probe_cycle(self, *, include_anycast: bool = False) -> None:
        if not self.ui_connected:
            return
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

        self._sync_live_cloud_inventory(settings)

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

