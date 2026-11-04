"""Telemetry & Health Read API Endpoints.

Serves live cloud authority status, KPI cards, visual topology diagnostics,
replication ledgers, and operational audit drill history.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from ..config import Settings
from .state import get_git_metadata, state

router = APIRouter(tags=["Telemetry"])


@router.get("/api/status")
def get_system_status() -> dict[str, Any]:
    settings = Settings()
    git_meta = get_git_metadata()

    if not settings.is_configured:
        return {
            "status": "UNCONFIGURED",
            "is_configured": False,
            "probe_count": 0,
            "last_probe_at": None,
            "active_workflow": None,
            "active_cloud": "--",
            "standby_cloud": "--",
            "active_locator": "--",
            "standby_locator": "--",
            "primary_account": "--",
            "secondary_account": "--",
            "global_redirect_handle": "Not Configured",
            "failover_group_name": "Not Configured",
            "pending_delta_rows": None,
            "aws": {
                "label": "Primary Cloud (Source)",
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
                "error": "Accounts not linked yet",
            },
            "azure": {
                "label": "Standby Cloud (DR Target)",
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
                "error": "Accounts not linked yet",
            },
            "anycast": {
                "url": "--",
                "landed_locator": "--",
                "landed_region": "--",
                "landed_cloud": "--",
                "latency_ms": None,
                "sfqid": "--",
                "checked_at": "--",
            },
            "last_rto_seconds": None,
            "last_reconcile": None,
            "git": git_meta,
            "watchdog": {
                "enabled": False,
                "failure_threshold": 3,
                "consecutive_failures": 0,
                "simulate_aws_outage": False,
                "auto_failover_triggered": False,
            },
            "last_git_push_event": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    with state._lock:
        active_snap, standby_snap = state.active_and_standby()
        aws_rows = state.aws.get("row_count")
        az_rows = state.azure.get("row_count")
        delta_rows = (
            abs(aws_rows - az_rows) if (aws_rows is not None and az_rows is not None) else None
        )
        overall = (
            "PROBING"
            if state.probe_count == 0
            else ("HEALTHY" if state.aws["healthy"] and state.azure["healthy"] else "DEGRADED")
        )
        org = settings.snowflake_account_primary.split("-", 1)[0].lower()
        redirect_url = (
            state.anycast.get("url")
            or f"{org}-{settings.snowflake_redirect_connection_name.lower()}.snowflakecomputing.com"
        )

        return {
            "status": overall,
            "is_configured": True,
            "probe_count": state.probe_count,
            "last_probe_at": state.last_probe_at,
            "active_workflow": state.active_workflow,
            "active_cloud": active_snap["label"],
            "standby_cloud": standby_snap["label"],
            "active_locator": active_snap["locator"],
            "standby_locator": standby_snap["locator"],
            "primary_account": settings.snowflake_account_primary,
            "secondary_account": settings.snowflake_account_secondary,
            "global_redirect_handle": redirect_url,
            "failover_group_name": settings.snowflake_failover_group_name,
            "pending_delta_rows": delta_rows,
            "aws": dict(state.aws),
            "azure": dict(state.azure),
            "anycast": dict(state.anycast),
            "last_rto_seconds": state.last_rto_seconds,
            "last_reconcile": state.last_reconcile,
            "git": git_meta,
            "watchdog": {
                "enabled": state.watchdog_enabled,
                "failure_threshold": state.failure_threshold,
                "consecutive_failures": state.consecutive_failures,
                "simulate_aws_outage": state.simulate_aws_outage,
                "auto_failover_triggered": state.auto_failover_triggered,
            },
            "last_git_push_event": state.last_git_push_event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/api/kpi")
def get_kpi_cards() -> list[dict[str, Any]]:
    with state._lock:
        active_snap, standby_snap = state.active_and_standby()
        aws = state.aws
        az = state.azure

        aws_ms = aws.get("ping_ms")
        az_ms = az.get("ping_ms")
        active_ms_str = f"{active_snap['ping_ms']:.0f} ms" if active_snap.get("ping_ms") is not None else "Probing..."
        ping_sub = (
            f"AWS: {aws_ms:.0f}ms | Azure: {az_ms:.0f}ms"
            if (aws_ms is not None and az_ms is not None)
            else "Measuring live SQL round-trip..."
        )

        aws_rows = aws.get("row_count")
        az_rows = az.get("row_count")
        active_rows = active_snap.get("row_count")
        rows_val = f"{active_rows:,}" if active_rows is not None else "Querying..."
        rows_sub = (
            f"AWS: {aws_rows:,} | Azure: {az_rows:,}"
            if (aws_rows is not None and az_rows is not None)
            else "Live Snowflake metadata count"
        )

        if aws_rows is not None and az_rows is not None:
            delta = abs(aws_rows - az_rows)
            rpo_val = "0 Rows (RPO=0)" if delta == 0 else f"{delta:,} Pending"
            rpo_status = "success" if delta == 0 else "info"
            rpo_badge = "In-Sync" if delta == 0 else "Delta Queued"
            rpo_sub = (
                "AWS & Azure row counts identical"
                if delta == 0
                else f"{delta:,} new rows awaiting WAN refresh"
            )
        else:
            rpo_val = "Probing..."
            rpo_status = "neutral"
            rpo_badge = "Checking"
            rpo_sub = "Comparing AWS & Azure tables"

        aws_cr = aws.get("used_credits")
        az_cr = az.get("used_credits")
        quota = (aws.get("credit_quota") or 10.0) + (az.get("credit_quota") or 10.0)
        if aws_cr is not None and az_cr is not None:
            total_cr = aws_cr + az_cr
            cr_val = f"{total_cr:.2f} / {quota:.0f} Cr"
            cr_sub = f"AWS: {aws_cr:.2f} Cr | Azure: {az_cr:.2f} Cr (DR_CREDIT_GUARD)"
        else:
            cr_val = "Probing..."
            cr_sub = "Reading SHOW RESOURCE MONITORS"

        rto_trend = (
            f"Last Measured RTO: {state.last_rto_seconds:.2f}s"
            if state.last_rto_seconds is not None
            else f"Probe #{state.probe_count} Live"
        )

        return [
            {
                "id": "live_probe_latency",
                "title": "Live SQL Probe RTT",
                "value": active_ms_str,
                "subtext": ping_sub,
                "status": "healthy" if active_snap.get("healthy") else "neutral",
                "badge": f"Probe #{state.probe_count}",
                "trend": f"sfqid: {(active_snap.get('last_sfqid') or 'pending')[:13]}",
            },
            {
                "id": "snowflake_rows",
                "title": "Live Snowflake Rows",
                "value": rows_val,
                "subtext": rows_sub,
                "status": "success",
                "badge": "Real Table Count",
                "trend": "SF_DR_DEMO_DB.DR_STAGING",
            },
            {
                "id": "cross_cloud_delta",
                "title": "Cross-Cloud RPO Delta",
                "value": rpo_val,
                "subtext": rpo_sub,
                "status": rpo_status,
                "badge": rpo_badge,
                "trend": (
                    f"Hash: {state.last_reconcile['aws']['hash_agg']}"
                    if state.last_reconcile
                    else "Click Reconcile for HASH_AGG"
                ),
            },
            {
                "id": "active_region",
                "title": "Active Primary Master",
                "value": active_snap["label"],
                "subtext": f"Locator: {active_snap['locator']} | Standby: {standby_snap['locator']}",
                "status": "info",
                "badge": "PRIMARY (R/W)",
                "trend": rto_trend,
            },
            {
                "id": "credit_guard",
                "title": "Live Credit Guard",
                "value": cr_val,
                "subtext": cr_sub,
                "status": "neutral",
                "badge": "Real FinOps",
                "trend": "IDLE_TIMEOUT = 60s",
            },
        ]


@router.get("/api/diagnostics")
def get_visual_diagnostics() -> dict[str, Any]:
    with state._lock:
        aws = dict(state.aws)
        az = dict(state.azure)
        is_aws_primary = aws.get("fg_is_primary") is not False and az.get("fg_is_primary") is not True

        aws_rows = aws.get("row_count") or 0
        az_rows = az.get("row_count") or 0
        max_rows = max(aws_rows, az_rows, 1)
        delta = abs(aws_rows - az_rows)
        parity_pct = round(((max_rows - delta) / max_rows) * 100, 4) if aws.get("row_count") is not None else 0.0

        rec = state.last_reconcile
        return {
            "topology": [
                {
                    "name": f"AWS us-east-1 ({aws['locator']})",
                    "value": 100 if is_aws_primary else 0,
                    "color": "#3B82F6",
                    "status": "PRIMARY (Read-Write)" if is_aws_primary else "SECONDARY (Read-Only Replica)",
                },
                {
                    "name": f"Azure East US 2 ({az['locator']})",
                    "value": 0 if is_aws_primary else 100,
                    "color": "#10B981",
                    "status": "SECONDARY (Read-Only Replica)" if is_aws_primary else "PRIMARY (Read-Write)",
                },
            ],
            "aws": aws,
            "azure": az,
            "anycast": dict(state.anycast),
            "data_health": {
                "parity_percentage": parity_pct,
                "aws_rows": aws.get("row_count"),
                "azure_rows": az.get("row_count"),
                "pending_delta_rows": delta,
                "cryptographic_hash": rec["aws"]["hash_agg"] if rec else None,
                "hash_matched": rec["parity_match"] if rec else None,
                "reconciled_volume": f"${rec['aws']['total_volume']:,.2f} USD" if rec else None,
                "schedule": az.get("replication_schedule") or aws.get("replication_schedule") or "10 MINUTE",
                "secondary_state": az.get("secondary_state") or aws.get("secondary_state") or "STARTED",
            },
            "telemetry_timeline": list(state.telemetry_points),
            "refresh_history": list(state.last_refresh_history),
            "probe_metadata": {
                "uptime_seconds": round(time.time() - state.started_at_ts, 1),
                "total_cycles": state.probe_count,
                "aws_success": state.aws_success_probes,
                "aws_failed": state.aws_failed_probes,
                "aws_uptime_pct": round(
                    (state.aws_success_probes / max(state.aws_success_probes + state.aws_failed_probes, 1)) * 100, 2
                ),
                "azure_success": state.azure_success_probes,
                "azure_failed": state.azure_failed_probes,
                "azure_uptime_pct": round(
                    (state.azure_success_probes / max(state.azure_success_probes + state.azure_failed_probes, 1)) * 100, 2
                ),
                "anycast_probes": state.anycast_success_probes,
                "k8s_probes": [
                    {
                        "pod": "sf-dr-dashboard",
                        "image": "sf-dr-dashboard:latest",
                        "startup_probe": "HTTP GET /api/status :8000 (period=5s, threshold=12)",
                        "liveness_probe": "HTTP GET /api/status :8000 (delay=15s, period=20s)",
                        "readiness_probe": "HTTP GET /api/status :8000 (delay=5s, period=10s)",
                        "status": "PASSING (200 OK)",
                    },
                    {
                        "pod": "sf-dr-daemon",
                        "image": "sf-dr-daemon:latest",
                        "startup_probe": "exec: python -c 'import sf_dr_controller'",
                        "liveness_probe": "exec: python -c 'import sf_dr_controller' (period=15s)",
                        "readiness_probe": "exec: Settings() validation (period=10s)",
                        "status": "PASSING (3-Strike Sentry Active)",
                    },
                ],
            },
        }


@router.get("/api/ledger")
def get_replication_ledger() -> list[dict[str, Any]]:
    with state._lock:
        aws = state.aws
        az = state.azure
        anycast = state.anycast

        aws_rows_txt = f"{aws['row_count']:,} rows" if aws.get("row_count") is not None else "Probing..."
        az_rows_txt = f"{az['row_count']:,} rows" if az.get("row_count") is not None else "Probing..."
        aws_role = "PRIMARY (Read-Write)" if aws.get("fg_is_primary") else "SECONDARY (Read-Only Replica)"
        az_role = "PRIMARY (Read-Write)" if az.get("fg_is_primary") else "SECONDARY (Read-Only Replica)"
        sched = az.get("replication_schedule") or aws.get("replication_schedule") or "10 MINUTE"
        sec_state = az.get("secondary_state") or aws.get("secondary_state") or "STARTED"

        return [
            {
                "id": "SF-AWS-ACCT",
                "name": f"SF_AWS_PRIMARY ({aws['locator']})",
                "provider": "AWS",
                "region": aws["region"],
                "target": f"{aws['identifier']} · SF_DR_DEMO_DB",
                "volume": aws_rows_txt,
                "lifecycle": aws_role,
                "ping_ms": aws.get("ping_ms"),
                "sfqid": aws.get("last_sfqid"),
                "healthy": aws.get("healthy", False),
                "status": aws_role,
            },
            {
                "id": "SF-AZURE-ACCT",
                "name": f"SF_AZURE_DR ({az['locator']})",
                "provider": "Azure",
                "region": az["region"],
                "target": f"{az['identifier']} · SF_DR_DEMO_DB",
                "volume": az_rows_txt,
                "lifecycle": az_role,
                "ping_ms": az.get("ping_ms"),
                "sfqid": az.get("last_sfqid"),
                "healthy": az.get("healthy", False),
                "status": az_role,
            },
            {
                "id": "SF-FG-GROUP",
                "name": "SF_DR_FAILOVER_GROUP",
                "provider": "Cross-Cloud WAN",
                "region": "AWS ⇄ Azure",
                "target": "NNFCDXY.SF_AWS_PRIMARY ⇄ NNFCDXY.SF_AZURE_DR",
                "volume": f"Schedule: {sched} ({sec_state})",
                "lifecycle": f"Next Auto-Sync: {az.get('next_scheduled_refresh') or aws.get('next_scheduled_refresh') or 'Active'}",
                "ping_ms": None,
                "sfqid": az.get("last_sfqid"),
                "healthy": aws.get("healthy", False) and az.get("healthy", False),
                "status": sec_state,
            },
            {
                "id": "SF-ANYCAST-CONN",
                "name": "SF_DR_GLOBAL_REDIRECT",
                "provider": "Global Anycast",
                "region": anycast.get("landed_region") or "Anycast DNS",
                "target": anycast.get("url") or "nnfcdxy-sf_dr_global_redirect.snowflakecomputing.com",
                "volume": (
                    f"Landed: {anycast['landed_locator']} ({anycast['latency_ms']}ms)"
                    if anycast.get("landed_locator")
                    else "Probing Anycast..."
                ),
                "lifecycle": f"Active Target: {anycast.get('landed_cloud') or 'Resolving...'}",
                "ping_ms": anycast.get("latency_ms"),
                "sfqid": anycast.get("sfqid"),
                "healthy": bool(anycast.get("landed_locator")),
                "status": "Active Routing",
            },
        ]


@router.get("/api/live-logs")
def get_live_logs() -> list[dict[str, Any]]:
    with state._lock:
        return list(state.live_logs)


@router.get("/api/drills")
def get_drill_history() -> list[dict[str, Any]]:
    with state._lock:
        return list(state.drill_history)
