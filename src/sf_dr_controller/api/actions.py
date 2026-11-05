"""Direct Execution & Action API Endpoints.

Provides synchronous HTTP POST triggers for Failover, Failback, Chaos Drill,
Ingestion, Reconcile, Immediate Probes, and Watchdog toggles.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .state import state
from .telemetry import get_system_status
from .workflows import _execute_real_workflow

router = APIRouter(prefix="/api/actions", tags=["Actions"])


class ActionRequest(BaseModel):
    operator: str = Field(default="Live SRE Console")
    batch_rows: int = Field(default=1000, ge=100, le=50000)


def _consume_workflow_sync(workflow_type: str, req: ActionRequest) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    for raw in _execute_real_workflow(workflow_type, batch_rows=req.batch_rows, operator=req.operator):
        if raw.startswith("data: "):
            events.append(json.loads(raw[6:].strip()))
    last = events[-1] if events else {}
    if last.get("type") == "workflow_error":
        raise HTTPException(status_code=409, detail=last.get("error", "Workflow failed"))
    return {"success": True, "events": events, "result": last}


@router.post("/failover")
def execute_manual_failover(req: ActionRequest) -> dict[str, Any]:
    return _consume_workflow_sync("failover", req)


@router.post("/chaos-drill")
def execute_chaos_drill(req: ActionRequest) -> dict[str, Any]:
    return _consume_workflow_sync("chaos", req)


@router.post("/failback")
def execute_manual_failback(req: ActionRequest) -> dict[str, Any]:
    return _consume_workflow_sync("failback", req)


@router.post("/ingest-sync")
def execute_ingest_sync(req: ActionRequest) -> dict[str, Any]:
    return _consume_workflow_sync("ingest_sync", req)


@router.post("/reconcile")
def run_hash_reconciliation() -> dict[str, Any]:
    out = _consume_workflow_sync("reconcile", ActionRequest())
    return out["result"].get("reconcile", out)


@router.post("/probe-now")
def trigger_live_probe() -> dict[str, Any]:
    state.run_probe_cycle(include_anycast=True)
    return get_system_status()


class WatchdogConfigRequest(BaseModel):
    enabled: bool | None = None
    simulate_aws_outage: bool | None = None


@router.post("/watchdog")
def configure_watchdog_and_outage(req: WatchdogConfigRequest) -> dict[str, Any]:
    with state._lock:
        if req.enabled is not None:
            state.watchdog_enabled = req.enabled
            state.add_log(
                source="watchdog",
                account="SENTRY",
                message=f"Autonomous 3-Strike Watchdog Sentry {'ENABLED' if req.enabled else 'PAUSED'} by operator.",
                level="INFO",
            )
        if req.simulate_aws_outage is not None:
            state.simulate_aws_outage = req.simulate_aws_outage
            if req.simulate_aws_outage:
                state.consecutive_failures = 0
                state.auto_failover_triggered = False
                state.add_log(
                    source="watchdog",
                    account="SENTRY",
                    message="🚨 Regional AWS us-east-1 Outage Injected! Watchdog will now probe every 5s and trigger automatic failover after 3 consecutive strikes.",
                    level="WARN",
                )
            else:
                state.consecutive_failures = 0
                state.auto_failover_triggered = False
                state.add_log(
                    source="watchdog",
                    account="SENTRY",
                    message="✅ Simulated AWS Outage cleared. AWS us-east-1 health probes restored to normal.",
                    level="SUCCESS",
                )
    state.trigger_immediate_probe()
    return get_system_status()

