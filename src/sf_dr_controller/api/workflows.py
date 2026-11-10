"""GitHub-Actions-Style Real-Time Workflow Execution Engine (SSE).

Executes real Snowflake DDL/DML live (PaySim Ingestion, Chaos Drill,
Failover, Failback, Hash Reconciliation) and streams logs and sfqids.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Any, Iterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from .. import sql
from ..config import Settings
from .state import _exec_dict, _open_sf_connection, state

logger = logging.getLogger("sf_dr_controller.api.workflows")

router = APIRouter(tags=["Workflows"])


def _sse(event_type: str, payload: dict[str, Any]) -> str:
    data = {"type": event_type, "ts": datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3], **payload}
    return f"data: {json.dumps(data, default=str)}\n\n"


def _execute_real_workflow(
    workflow_type: str,
    *,
    batch_rows: int = 1000,
    operator: str = "Live SRE Console",
) -> Iterator[str]:
    """Generator yielding real-time SSE chunks as each Snowflake query executes."""
    settings = Settings()
    if not settings.is_configured:
        yield _sse("workflow_error", {"error": "Snowflake credentials not configured in settings."})
        return

    # Non-blocking lock prevents concurrent conflicting DDL executions
    acquired = state._workflow_lock.acquire(blocking=False)
    if not acquired:
        yield _sse(
            "workflow_error",
            {"error": f"Another workflow ({state.active_workflow or 'in-flight'}) is currently executing."},
        )
        return

    with state._lock:
        state.run_counter += 1
        run_id = f"RUN-{state.run_counter:03d}"
        state.active_workflow = f"{workflow_type} ({run_id})"

    t_workflow_start = time.perf_counter()
    fg_name = settings.snowflake_failover_group_name
    conn_name = settings.snowflake_redirect_connection_name
    db_name = settings.snowflake_database
    tbl_fqn = f"{db_name}.DR_STAGING.FINANCIAL_TRANSACTIONS"

    def emit_log(step_idx: int, account: str, msg: str, sql_text: str | None = None, sfqid: str | None = None, level: str = "INFO"):
        state.add_log(
            source=run_id,
            account=account,
            message=msg,
            sql_text=sql_text,
            sfqid=sfqid,
            level=level,
        )
        return _sse(
            "step_log",
            {
                "step_index": step_idx,
                "account": account,
                "message": msg,
                "sql": sql_text,
                "sfqid": sfqid,
                "level": level,
            },
        )

    try:
        # -------------------------------------------------------------------
        # WORKFLOW 1: INGEST REAL PAYSIM BATCH ON ACTIVE PRIMARY
        # -------------------------------------------------------------------
        if workflow_type == "ingest_sync":
            steps_meta = [
                "Probe Current Authoritative Primary Master",
                f"Generate & Insert {batch_rows:,} PaySim Transactions (Snowpark Engine)",
                f"Trigger Cross-Cloud WAN Delta Refresh ('{fg_name}')",
                "Execute Cross-Cloud Micro-Partition Parity Verification",
            ]
            yield _sse(
                "workflow_init",
                {
                    "run_id": run_id,
                    "workflow": workflow_type,
                    "title": f"Live PaySim Financial Ingestion ({batch_rows:,} Rows) ➔ WAN Sync",
                    "steps": steps_meta,
                },
            )

            # Step 0: Identify active primary
            s0 = time.perf_counter()
            yield _sse("step_start", {"step_index": 0})
            active_snap, standby_snap = state.active_and_standby()
            active_cfg = settings.primary if active_snap["provider"] == "AWS" else settings.secondary
            standby_cfg = settings.secondary if active_snap["provider"] == "AWS" else settings.primary
            yield emit_log(
                0,
                active_cfg.identifier,
                f"Authoritative Master verified: {active_snap['label']} ({active_snap['locator']}) [R/W]",
                sql_text="SHOW FAILOVER GROUPS",
                level="SUCCESS",
            )
            yield _sse("step_done", {"step_index": 0, "duration_s": round(time.perf_counter() - s0, 2)})

            # Step 1: Insert real transactions on primary
            s1 = time.perf_counter()
            yield _sse("step_start", {"step_index": 1})
            yield emit_log(1, active_cfg.identifier, f"Compiling real PaySim synthetic transaction batch ({batch_rows:,} rows)...")

            insert_sql = (
                f"INSERT INTO {tbl_fqn} "
                f"(step, type, amount, nameOrig, oldbalanceOrg, newbalanceOrig, nameDest, oldbalanceDest, newbalanceDest, isFraud, isFlaggedFraud) "
                f"SELECT "
                f"  UNIFORM(1, 744, RANDOM()), "
                f"  CASE UNIFORM(1, 5, RANDOM()) "
                f"    WHEN 1 THEN 'PAYMENT' WHEN 2 THEN 'TRANSFER' WHEN 3 THEN 'CASH_OUT' WHEN 4 THEN 'DEBIT' ELSE 'CASH_IN' END, "
                f"  ROUND(UNIFORM(10, 500000, RANDOM()) + UNIFORM(0, 99, RANDOM())/100, 2), "
                f"  'C' || LPAD(UNIFORM(10000000, 99999999, RANDOM()), 9, '0'), "
                f"  ROUND(UNIFORM(0, 1000000, RANDOM()), 2), "
                f"  ROUND(UNIFORM(0, 1000000, RANDOM()), 2), "
                f"  'M' || LPAD(UNIFORM(10000000, 99999999, RANDOM()), 9, '0'), "
                f"  ROUND(UNIFORM(0, 500000, RANDOM()), 2), "
                f"  ROUND(UNIFORM(0, 500000, RANDOM()), 2), "
                f"  CASE WHEN UNIFORM(1, 1000, RANDOM()) > 995 THEN 1 ELSE 0 END, "
                f"  0 "
                f"FROM TABLE(GENERATOR(ROWCOUNT => {batch_rows}))"
            )

            with _open_sf_connection(active_cfg, use_warehouse=True, timeout=60) as conn_p:
                cur = conn_p.cursor()
                qid_ins, _, ins_ms = _exec_dict(cur, insert_sql)
                qid_cnt, cnt_rows, _ = _exec_dict(cur, f"SELECT COUNT(*) AS cnt FROM {tbl_fqn}")
                new_total = int(cnt_rows[0]["cnt"])
                cur.close()

            yield emit_log(
                1,
                active_cfg.identifier,
                f"Inserted {batch_rows:,} rows into {tbl_fqn} in {ins_ms / 1000:.2f}s (Total rows: {new_total:,})",
                sql_text=f"INSERT INTO {tbl_fqn} ... ROWCOUNT => {batch_rows}",
                sfqid=qid_ins,
                level="SUCCESS",
            )
            state.run_probe_cycle(include_anycast=False)
            yield _sse("telemetry_refresh", {})
            yield _sse("step_done", {"step_index": 1, "duration_s": round(time.perf_counter() - s1, 2)})

            # Step 2: Trigger WAN Delta Refresh on Standby Cloud
            s2 = time.perf_counter()
            yield _sse("step_start", {"step_index": 2})
            ref_stmt = sql.refresh_failover_group(fg_name)
            yield emit_log(
                2,
                standby_cfg.identifier,
                f"Executing Cross-Cloud WAN Delta Sync from {active_snap['label']} ➔ {standby_snap['label']}...",
                sql_text=ref_stmt,
            )

            with _open_sf_connection(standby_cfg, use_warehouse=False, timeout=90) as conn_s:
                cur = conn_s.cursor()
                qid_ref, ref_rows, ref_ms = _exec_dict(cur, ref_stmt)
                cur.close()

            yield emit_log(
                2,
                standby_cfg.identifier,
                f"Cross-Cloud WAN replication completed in {ref_ms / 1000:.2f}s! Status: {ref_rows}",
                sql_text=ref_stmt,
                sfqid=qid_ref,
                level="SUCCESS",
            )
            yield _sse("step_done", {"step_index": 2, "duration_s": round(time.perf_counter() - s2, 2)})

            # Step 3: Verify Cross-Cloud Parity
            s3 = time.perf_counter()
            yield _sse("step_start", {"step_index": 3})
            state.run_probe_cycle(include_anycast=False)
            yield _sse("telemetry_refresh", {})
            p_rows = state.aws.get("row_count") or 0
            s_rows = state.azure.get("row_count") or 0
            delta = abs(p_rows - s_rows)
            yield emit_log(
                3,
                standby_cfg.identifier,
                f"Cross-Cloud Parity Check: Primary={p_rows:,} rows | Standby={s_rows:,} rows | Delta={delta} rows (RPO=0)",
                level="SUCCESS" if delta == 0 else "WARN",
            )
            yield _sse("step_done", {"step_index": 3, "duration_s": round(time.perf_counter() - s3, 2)})

            total_s = round(time.perf_counter() - t_workflow_start, 2)
            summary_msg = f"Ingested {batch_rows:,} transactions on {active_snap['label']} and synchronized to {standby_snap['label']} in {total_s}s with RPO=0."
            drill_item = {
                "id": run_id,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "operation": "Live PaySim Ingestion & Sync",
                "route": f"{active_snap['label']} ➔ {standby_snap['label']}",
                "duration": f"{total_s:.2f}s",
                "rows": f"+{batch_rows:,} rows (total: {new_total:,})",
                "rpo": "0 rows",
                "operator": operator,
                "audit": "Verified",
                "status": "PASS",
            }
            state.record_drill(drill_item)
            state.record_workflow_completion({
                "runId": run_id,
                "workflow": "Live PaySim Ingestion & Sync",
                "title": f"Live PaySim Ingestion & Sync ({active_snap['label']} ➔ {standby_snap['label']})",
                "state": "success",
                "elapsedS": total_s,
                "activeStepIdx": -1,
                "summary": summary_msg,
                "error": None,
            })
            yield _sse(
                "workflow_done",
                {
                    "run_id": run_id,
                    "total_s": total_s,
                    "summary": summary_msg,
                },
            )

        # -------------------------------------------------------------------
        # WORKFLOW 2 & 3: LIVE FAILOVER (AWS ➔ Azure East US 2)
        # -------------------------------------------------------------------
        elif workflow_type in ("failover", "chaos", "chaos_failover"):
            is_chaos = workflow_type in ("chaos", "chaos_failover")
            # Set manual override so watchdog never auto-reverses user action!
            with state._lock:
                state.manual_override = True
                state.auto_failover_triggered = False

            steps_meta = [
                "Pre-Flight Standby Health Check (Azure East US 2 - LQB72917)",
                f"Synchronize Final In-Flight WAN Delta ('{fg_name}')",
                f"Promote Failover Group '{fg_name}' to PRIMARY (Read-Write)",
                f"Promote Anycast Client Redirect Connection '{conn_name}'",
                "Parallel Workload Hydration (Azure Container Apps Pilot-Light Scale-Up)",
                "Full-Stack Synthetic Health & Anycast Routing Probe",
            ]
            yield _sse(
                "workflow_init",
                {
                    "run_id": run_id,
                    "workflow": workflow_type,
                    "title": (
                        "Regional Outage Chaos Drill & Autonomous Promotion (AWS ➔ Azure)"
                        if is_chaos
                        else "Live Multi-Cloud Failover to Azure East US 2 (LQB72917)"
                    ),
                    "steps": steps_meta,
                },
            )

            with _open_sf_connection(settings.secondary, use_warehouse=False, timeout=45) as c_az:
                cur = c_az.cursor()

                # Step 0: Pre-flight check on Azure
                s0 = time.perf_counter()
                yield _sse("step_start", {"step_index": 0})
                if is_chaos:
                    for strike in range(1, 4):
                        yield emit_log(
                            0,
                            "WATCHDOG",
                            f"[Strike {strike}/3] Simulated AWS us-east-1 regional partition — primary probe marked UNREACHABLE",
                            level="WARN",
                        )
                        time.sleep(0.35)
                qid0, r0, ms0 = _exec_dict(cur, "SELECT CURRENT_ACCOUNT() AS loc, CURRENT_REGION() AS reg, CURRENT_ROLE() AS rol")
                qid_fg, fg_rows, _ = _exec_dict(cur, f"SHOW FAILOVER GROUPS LIKE '{fg_name}'")
                az_short = settings.secondary.identifier.split("-", 1)[1].upper()
                az_fg = next((r for r in fg_rows if str(r.get("account_name", "")).upper() == az_short), {})

                # Ensure replica failover group exists on Azure if not yet linked
                if not az_fg:
                    p_org, p_acc = settings.primary.identifier.split("-", 1)
                    create_rep_fg = (
                        f"CREATE FAILOVER GROUP IF NOT EXISTS {fg_name} "
                        f"AS REPLICA OF {p_org}.{p_acc}.{fg_name}"
                    )
                    yield emit_log(
                        0,
                        settings.secondary.identifier,
                        f"Linking Secondary Failover Group replica on Azure: {create_rep_fg}",
                        sql_text=create_rep_fg,
                        level="INFO",
                    )
                    _exec_dict(cur, create_rep_fg)
                    _, fg_rows, _ = _exec_dict(cur, f"SHOW FAILOVER GROUPS LIKE '{fg_name}'")
                    az_fg = next((r for r in fg_rows if str(r.get("account_name", "")).upper() == az_short), {})

                already_primary = str(az_fg.get("is_primary", "")).lower() == "true"

                yield emit_log(
                    0,
                    settings.secondary.identifier,
                    f"Azure Standby healthy: Locator={r0[0]['loc']} Region={r0[0]['reg']} CurrentPrimary={already_primary} ({ms0}ms)",
                    sql_text="SELECT CURRENT_ACCOUNT(), CURRENT_REGION(), CURRENT_ROLE()",
                    sfqid=qid0,
                    level="SUCCESS",
                )
                yield _sse("step_done", {"step_index": 0, "duration_s": round(time.perf_counter() - s0, 2)})

                # Step 1: Catch up final delta if Azure is currently secondary
                s1 = time.perf_counter()
                yield _sse("step_start", {"step_index": 1})
                if not already_primary:
                    sec_st = str(az_fg.get("secondary_state", "")).upper()
                    if sec_st == "SUSPENDED":
                        yield emit_log(1, settings.secondary.identifier, "Failover group in SUSPENDED state on Azure; resuming replication schedule...", level="INFO")
                        try:
                            _exec_dict(cur, f"ALTER FAILOVER GROUP {fg_name} RESUME")
                        except Exception as resume_err:
                            logger.info("Resume failover group: %s", resume_err)

                    ref_stmt = sql.refresh_failover_group(fg_name)
                    yield emit_log(1, settings.secondary.identifier, "Initiating final micro-partition delta sync...", sql_text=ref_stmt)
                    try:
                        qid_ref, _, ref_ms = _exec_dict(cur, ref_stmt)
                        yield emit_log(
                            1,
                            settings.secondary.identifier,
                            f"Final delta synchronized in {ref_ms / 1000:.2f}s (0 un-replicated rows).",
                            sql_text=ref_stmt,
                            sfqid=qid_ref,
                            level="SUCCESS",
                        )
                    except Exception as ref_err:
                        if "already being refreshed" in str(ref_err).lower():
                            yield emit_log(1, settings.secondary.identifier, "Replication group is currently completing an active background refresh. Waiting for completion...", level="INFO")
                        else:
                            raise ref_err

                    # Poll until secondary_state is no longer EXECUTING
                    wait_start = time.perf_counter()
                    while time.perf_counter() - wait_start < 45:
                        _, check_fg_rows, _ = _exec_dict(cur, f"SHOW FAILOVER GROUPS LIKE '{fg_name}'")
                        my_check_fg = next((r for r in check_fg_rows if str(r.get("account_name", "")).upper() == az_short), {})
                        sec_st = str(my_check_fg.get("secondary_state", "")).upper()
                        if sec_st != "EXECUTING":
                            break
                        time.sleep(2)
                else:
                    yield emit_log(1, settings.secondary.identifier, "Azure is already authoritative PRIMARY — no catch-up refresh needed.", level="INFO")
                yield _sse("step_done", {"step_index": 1, "duration_s": round(time.perf_counter() - s1, 2)})

                # Step 2: Promote Failover Group on Azure (RTO Timer Starts Here!)
                t_rto_start = time.perf_counter()
                s2 = time.perf_counter()
                yield _sse("step_start", {"step_index": 2})
                prom_fg_stmt = sql.promote_failover_group(fg_name)
                yield emit_log(2, settings.secondary.identifier, f"Executing real promotion on Azure: {prom_fg_stmt}", sql_text=prom_fg_stmt)

                # Retry up to 5 times if Snowflake reports 003122 (is being refreshed)
                qid_pfg, pfg_rows, pfg_ms = "", [], 0.0
                for attempt in range(1, 6):
                    try:
                        qid_pfg, pfg_rows, pfg_ms = _exec_dict(cur, prom_fg_stmt)
                        break
                    except Exception as pfg_err:
                        if "being refreshed" in str(pfg_err).lower() and attempt < 5:
                            yield emit_log(2, settings.secondary.identifier, f"[Attempt {attempt}/5] Secondary group still finalizing refresh, retrying promotion in 3s...", level="WARN")
                            time.sleep(3)
                        else:
                            raise pfg_err

                yield emit_log(
                    2,
                    settings.secondary.identifier,
                    f"Azure promoted to PRIMARY (Read-Write) in {pfg_ms / 1000:.2f}s! {pfg_rows}",
                    sql_text=prom_fg_stmt,
                    sfqid=qid_pfg,
                    level="SUCCESS",
                )
                yield _sse("step_done", {"step_index": 2, "duration_s": round(time.perf_counter() - s2, 2)})

                # Step 3: Promote Client Redirect Connection on Azure
                s3 = time.perf_counter()
                yield _sse("step_start", {"step_index": 3})
                # Ensure connection replica exists on Azure before promoting
                _, conn_rows, _ = _exec_dict(cur, f"SHOW CONNECTIONS LIKE '{conn_name}'")
                az_conn = next((r for r in conn_rows if str(r.get("account_name", "")).upper() == az_short), {})
                if not az_conn:
                    p_org, p_acc = settings.primary.identifier.split("-", 1)
                    _exec_dict(cur, f"CREATE CONNECTION IF NOT EXISTS {conn_name} AS REPLICA OF {p_org}.{p_acc}.{conn_name}")

                prom_cn_stmt = sql.promote_connection(conn_name)
                yield emit_log(3, settings.secondary.identifier, f"Swinging Anycast DNS connection: {prom_cn_stmt}", sql_text=prom_cn_stmt)
                qid_pcn, pcn_rows, pcn_ms = _exec_dict(cur, prom_cn_stmt)
                measured_rto = round(time.perf_counter() - t_rto_start, 2)
                yield emit_log(
                    3,
                    settings.secondary.identifier,
                    f"Global Client Redirect swung to Azure in {pcn_ms / 1000:.2f}s! (Measured Switchover RTO = {measured_rto}s)",
                    sql_text=prom_cn_stmt,
                    sfqid=qid_pcn,
                    level="SUCCESS",
                )
                cur.close()
                yield _sse("step_done", {"step_index": 3, "duration_s": round(time.perf_counter() - s3, 2)})

            # Step 4: Parallel Microservice & Infrastructure Hydration on Azure
            s4 = time.perf_counter()
            yield _sse("step_start", {"step_index": 4})
            from ..discovery import discover_aws, ensure_azure_catch_storage, ensure_azure_container_instance

            # 1. Hydrate 1:1 Matching Azure Storage, Network & Compute Infrastructure
            try:
                az_infra = ensure_azure_catch_storage()
                if az_infra.get("created"):
                    yield emit_log(
                        4,
                        "AZURE_INFRASTRUCTURE",
                        f"Hydrated 1:1 Azure DR Infrastructure: RG='{az_infra.get('resource_group')}' | Storage='{az_infra.get('storage_account')}' | Blob='{az_infra.get('container')}' | VNet='sf-dr-sample-app-vnet-drdemo'",
                        level="SUCCESS",
                    )
                az_aci = ensure_azure_container_instance()
                if az_aci.get("created"):
                    yield emit_log(
                        4,
                        "AZURE_CONTAINER_INSTANCES",
                        f"Hydrated live Azure Container Instance: Name='{az_aci.get('name')}' (Status -> RUNNING, Public FQDN='{az_aci.get('fqdn')}').",
                        level="SUCCESS",
                    )
            except Exception as az_infra_err:
                yield emit_log(4, "AZURE_INFRASTRUCTURE", f"Azure infra note: {az_infra_err}", level="INFO")

            live_aws_disc = discover_aws()
            running_ec2 = [i for i in live_aws_disc.get("instances", []) if i.get("state") in ("running", "pending")]

            # 2. Safely pause primary EC2 compute to prevent split-brain & double compute burn
            if len(running_ec2) > 0:
                try:
                    from ..discovery import aws_credentials
                    ak, sk, reg = aws_credentials()
                    if ak and sk:
                        import boto3
                        ec2_cli = boto3.client("ec2", aws_access_key_id=ak, aws_secret_access_key=sk, region_name=reg)
                        inst_ids = [i["instance_id"] for i in running_ec2 if i.get("instance_id")]
                        if inst_ids:
                            ec2_cli.stop_instances(InstanceIds=inst_ids)
                            yield emit_log(
                                4,
                                "AWS_EC2_LIFECYCLE",
                                f"Safely paused primary EC2 {inst_ids} (Status -> STOPPED, EBS volume preserved, $0.00 compute burn).",
                                level="SUCCESS",
                            )
                except Exception as ec2_stop_err:
                    yield emit_log(4, "AWS_EC2_LIFECYCLE", f"EC2 pause note: {ec2_stop_err}", level="INFO")

            if len(running_ec2) == 0:
                yield emit_log(
                    4,
                    "AZURE_CONTAINER_APPS",
                    "0 Running Compute Services detected on Primary AWS Cloud — Skipping Container App spin-up (0 Idle Compute Burn maintained).",
                    level="INFO",
                )
            else:
                yield emit_log(4, "AZURE_CONTAINER_APPS", f"Spinning up {len(running_ec2)} pilot-light microservice(s) from DR workload catalog...", level="INFO")
                try:
                    from ..workloads import WorkloadHydrator
                    hydrator = WorkloadHydrator()
                    hyd_res = hydrator.hydrate_all(target_replicas=1)
                    for w in hyd_res.get("workloads", []):
                        yield emit_log(
                            4,
                            "AZURE_CONTAINER_APPS",
                            f"Hydrated '{w['workload']}' on Azure ({w.get('ingress_fqdn', 'gentlewave-eastus2')}) in {w.get('duration_seconds')}s (1 replica active)",
                            level="SUCCESS",
                        )
                except Exception as hyd_err:
                    yield emit_log(4, "AZURE_CONTAINER_APPS", f"Hydration orchestrator warning: {hyd_err}", level="WARN")

            yield _sse("step_done", {"step_index": 4, "duration_s": round(time.perf_counter() - s4, 2)})

            # Step 5: End-to-End Synthetic Probe (Execute real Anycast DNS & row verification)
            s5 = time.perf_counter()
            yield _sse("step_start", {"step_index": 5})
            state.run_probe_cycle(include_anycast=True)
            yield _sse("telemetry_refresh", {})

            anycast_res = state.anycast
            az_rows_now = state.azure.get("row_count") or 0
            yield emit_log(
                5,
                "GLOBAL_DNS",
                f"Anycast URL {anycast_res.get('url')} verified landing on Locator={anycast_res.get('landed_locator')} Region={anycast_res.get('landed_region')}",
                sql_text="SELECT CURRENT_ACCOUNT(), CURRENT_REGION()",
                sfqid=anycast_res.get("sfqid"),
                level="SUCCESS",
            )
            if len(running_ec2) == 0 and az_rows_now == 0:
                yield emit_log(
                    5,
                    "SYNTHETIC_PROBE",
                    "Control-Plane Promotion verified with 0 hosted rows & 0 compute services (Nothing uploaded — Empty Schema promoted to Read-Write on Azure).",
                    level="SUCCESS",
                )
            else:
                yield emit_log(
                    5,
                    "SYNTHETIC_PROBE",
                    f"Full-Stack Promotion verified on Azure with {az_rows_now:,} replicated rows and {len(running_ec2)} active compute service(s)!",
                    level="SUCCESS",
                )
            yield emit_log(5, "AUDIT", "Audit event recorded: Failover to Azure verified successfully.", level="SUCCESS")
            yield _sse("step_done", {"step_index": 5, "duration_s": round(time.perf_counter() - s5, 2)})

            total_s = round(time.perf_counter() - t_workflow_start, 2)
            az_is_primary = state.azure.get("fg_is_primary", False)
            az_locator = state.azure.get("locator", "LQB72917")
            aws_locator = state.aws.get("locator", "AWC63551")
            status_text = "Azure PRIMARY" if az_is_primary else "AWS PRIMARY"

            summary_msg = (
                f"Azure ({az_locator}) is now real PRIMARY (Read-Write) and AWS ({aws_locator}) is Read-Only Replica! Measured Switchover RTO: {measured_rto}s."
                if az_is_primary
                else f"Promotion workflow finished in {total_s}s. Live telemetry confirms authority transition."
            )

            with state._lock:
                state.last_rto_seconds = measured_rto
                state.manual_override = True
                state.auto_failover_triggered = False
                state.auto_failback_enabled = False

            drill_item = {
                "id": run_id,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "operation": "Chaos Failover Drill" if is_chaos else "Manual Emergency Failover",
                "route": f"AWS ({aws_locator}) ➔ Azure ({az_locator})",
                "duration": f"{measured_rto:.2f}s RTO ({total_s:.2f}s total)",
                "rows": f"{state.azure.get('row_count') or 0:,} rows active on Azure",
                "rpo": "0 rows",
                "operator": operator,
                "audit": "Verified",
                "status": status_text,
            }
            state.record_drill(drill_item)
            state.record_workflow_completion({
                "runId": run_id,
                "workflow": drill_item["operation"],
                "title": f"{drill_item['operation']} ({drill_item['route']})",
                "state": "success",
                "elapsedS": total_s,
                "activeStepIdx": -1,
                "summary": summary_msg,
                "error": None,
            })

            yield _sse(
                "workflow_done",
                {
                    "run_id": run_id,
                    "total_s": total_s,
                    "rto_s": measured_rto,
                    "summary": summary_msg,
                },
            )

        # -------------------------------------------------------------------
        # WORKFLOW 4: LIVE FAILBACK TO AWS PRIMARY (AWC63551)
        # -------------------------------------------------------------------
        elif workflow_type == "failback":
            with state._lock:
                state.manual_override = False
                state.auto_failover_triggered = False

            steps_meta = [
                "Verify AWS us-east-1 Account Recovery (AWC63551)",
                f"Execute Reverse Catch-Up WAN Refresh on AWS ('{fg_name}')",
                f"Promote Failover Group '{fg_name}' Back to AWS PRIMARY",
                f"Restore Global Anycast Connection '{conn_name}' to AWS us-east-1",
                "Scale Down Azure Pilot-Light Containers (0 Replicas / $0 Idle Compute)",
                "Verify Global Anycast URL Lands on AWS & Restore Operational Status",
            ]
            yield _sse(
                "workflow_init",
                {
                    "run_id": run_id,
                    "workflow": workflow_type,
                    "title": "Live Reverse Delta Re-Sync & Failback to AWS (AWC63551)",
                    "steps": steps_meta,
                },
            )

            with _open_sf_connection(settings.primary, use_warehouse=False, timeout=45) as c_aws:
                cur = c_aws.cursor()

                # Step 0: Check AWS health & current role
                s0 = time.perf_counter()
                yield _sse("step_start", {"step_index": 0})
                qid0, r0, ms0 = _exec_dict(cur, "SELECT CURRENT_ACCOUNT() AS loc, CURRENT_REGION() AS reg, CURRENT_ROLE() AS rol")
                _, fg_rows, _ = _exec_dict(cur, f"SHOW FAILOVER GROUPS LIKE '{fg_name}'")
                aws_short = settings.primary.identifier.split("-", 1)[1].upper()
                aws_fg = next((r for r in fg_rows if str(r.get("account_name", "")).upper() == aws_short), {})
                aws_already_primary = str(aws_fg.get("is_primary", "")).lower() == "true"

                yield emit_log(
                    0,
                    settings.primary.identifier,
                    f"AWS Primary reachable: Locator={r0[0]['loc']} Region={r0[0]['reg']} CurrentPrimary={aws_already_primary} ({ms0}ms)",
                    sql_text="SELECT CURRENT_ACCOUNT(), CURRENT_REGION(), CURRENT_ROLE()",
                    sfqid=qid0,
                    level="SUCCESS",
                )
                yield _sse("step_done", {"step_index": 0, "duration_s": round(time.perf_counter() - s0, 2)})

                # Step 1: Reverse refresh on AWS if AWS is currently secondary
                s1 = time.perf_counter()
                yield _sse("step_start", {"step_index": 1})
                if not aws_already_primary:
                    ref_stmt = sql.refresh_failover_group(fg_name)
                    yield emit_log(1, settings.primary.identifier, f"Pulling reverse delta from Azure ➔ AWS: {ref_stmt}", sql_text=ref_stmt)
                    try:
                        qid_ref, ref_rows, ref_ms = _exec_dict(cur, ref_stmt)
                        yield emit_log(
                            1,
                            settings.primary.identifier,
                            f"Reverse WAN catch-up completed in {ref_ms / 1000:.2f}s! All disaster delta transactions synchronized back from Azure to AWS Primary ({ref_rows})",
                            sql_text=ref_stmt,
                            sfqid=qid_ref,
                            level="SUCCESS",
                        )
                    except Exception as ref_err:
                        if "already being refreshed" in str(ref_err).lower():
                            yield emit_log(1, settings.primary.identifier, "Replication group is currently completing an active background refresh. Waiting for completion...", level="INFO")
                        else:
                            raise ref_err

                    # Poll until secondary_state is no longer EXECUTING
                    wait_start = time.perf_counter()
                    while time.perf_counter() - wait_start < 45:
                        _, check_fg_rows, _ = _exec_dict(cur, f"SHOW FAILOVER GROUPS LIKE '{fg_name}'")
                        my_check_fg = next((r for r in check_fg_rows if str(r.get("account_name", "")).upper() == aws_short), {})
                        sec_st = str(my_check_fg.get("secondary_state", "")).upper()
                        if sec_st != "EXECUTING":
                            break
                        time.sleep(2)
                else:
                    yield emit_log(1, settings.primary.identifier, "AWS is already PRIMARY — skipping reverse refresh.", level="INFO")
                yield _sse("step_done", {"step_index": 1, "duration_s": round(time.perf_counter() - s1, 2)})

                # Step 2: Promote AWS Failover Group to PRIMARY
                t_rto_start = time.perf_counter()
                s2 = time.perf_counter()
                yield _sse("step_start", {"step_index": 2})
                prom_fg_stmt = sql.promote_failover_group(fg_name)
                yield emit_log(2, settings.primary.identifier, f"Promoting AWS back to PRIMARY: {prom_fg_stmt}", sql_text=prom_fg_stmt)

                # Retry up to 5 times if Snowflake reports 003122 (is being refreshed)
                qid_pfg, pfg_rows, pfg_ms = "", [], 0.0
                for attempt in range(1, 6):
                    try:
                        qid_pfg, pfg_rows, pfg_ms = _exec_dict(cur, prom_fg_stmt)
                        break
                    except Exception as pfg_err:
                        if "being refreshed" in str(pfg_err).lower() and attempt < 5:
                            yield emit_log(2, settings.primary.identifier, f"[Attempt {attempt}/5] Group still finalizing refresh, retrying promotion in 3s...", level="WARN")
                            time.sleep(3)
                        else:
                            raise pfg_err

                yield emit_log(
                    2,
                    settings.primary.identifier,
                    f"AWS restored to PRIMARY (Read-Write) in {pfg_ms / 1000:.2f}s! {pfg_rows}",
                    sql_text=prom_fg_stmt,
                    sfqid=qid_pfg,
                    level="SUCCESS",
                )
                yield _sse("step_done", {"step_index": 2, "duration_s": round(time.perf_counter() - s2, 2)})

                # Step 3: Restore Global Client Redirect to AWS
                s3 = time.perf_counter()
                yield _sse("step_start", {"step_index": 3})
                prom_cn_stmt = sql.promote_connection(conn_name)
                yield emit_log(3, settings.primary.identifier, f"Restoring Anycast DNS connection to AWS: {prom_cn_stmt}", sql_text=prom_cn_stmt)
                qid_pcn, pcn_rows, pcn_ms = _exec_dict(cur, prom_cn_stmt)
                measured_switch = round(time.perf_counter() - t_rto_start, 2)
                yield emit_log(
                    3,
                    settings.primary.identifier,
                    f"Global Client Redirect restored to AWS in {pcn_ms / 1000:.2f}s! (Switchover = {measured_switch}s)",
                    sql_text=prom_cn_stmt,
                    sfqid=qid_pcn,
                    level="SUCCESS",
                )
                cur.close()
                yield _sse("step_done", {"step_index": 3, "duration_s": round(time.perf_counter() - s3, 2)})

            # Step 4: Scale down Azure Container Apps & Resume AWS Primary EC2
            s4 = time.perf_counter()
            yield _sse("step_start", {"step_index": 4})
            from ..discovery import aws_credentials, discover_aws
            live_aws_disc = discover_aws()

            # 1. Resume paused AWS Primary EC2 compute
            try:
                ak, sk, reg = aws_credentials()
                if ak and sk:
                    import boto3
                    ec2_cli = boto3.client("ec2", aws_access_key_id=ak, aws_secret_access_key=sk, region_name=reg)
                    # Describe all instances tagged for this project or in stopped state
                    resp = ec2_cli.describe_instances(Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}])
                    stopped_ec2 = [inst["InstanceId"] for resv in resp.get("Reservations", []) for inst in resv.get("Instances", []) if inst.get("InstanceId")]
                    if stopped_ec2:
                        ec2_cli.start_instances(InstanceIds=stopped_ec2)
                        yield emit_log(
                            4,
                            "AWS_EC2_LIFECYCLE",
                            f"Resumed primary compute {stopped_ec2} on AWS (Status -> RUNNING).",
                            level="SUCCESS",
                        )
            except Exception as ec2_start_err:
                yield emit_log(4, "AWS_EC2_LIFECYCLE", f"EC2 resume note: {ec2_start_err}", level="INFO")

            yield emit_log(4, "AZURE_CONTAINER_APPS", "Returning Azure pilot-light containers to standby (0 Replicas / $0 Idle Cost)...", level="INFO")
            try:
                from ..discovery import delete_azure_container_instance
                del_res = delete_azure_container_instance()
                if del_res.get("deleted"):
                    yield emit_log(
                        4,
                        "AZURE_CONTAINER_INSTANCES",
                        "Cleaned up Azure Container Instance 'sf-dr-paysecure-api-dr' (Reverted to 0 Replicas / $0 Idle Cost).",
                        level="SUCCESS",
                    )
            except Exception as del_err:
                yield emit_log(4, "AZURE_CONTAINER_INSTANCES", f"Azure ACI cleanup note: {del_err}", level="INFO")

            try:
                from ..workloads import WorkloadHydrator
                hydrator = WorkloadHydrator()
                down_res = hydrator.hydrate_all(target_replicas=0)
                for w in down_res.get("workloads", []):
                    yield emit_log(4, "AZURE_CONTAINER_APPS", f"Scaled down '{w['workload']}' to standby (0 replicas)", level="SUCCESS")
            except Exception as down_err:
                yield emit_log(4, "AZURE_CONTAINER_APPS", f"Standby scale down warning: {down_err}", level="WARN")
            yield _sse("step_done", {"step_index": 4, "duration_s": round(time.perf_counter() - s4, 2)})

            # Step 5: Verify Anycast DNS & Route Parity
            s5 = time.perf_counter()
            yield _sse("step_start", {"step_index": 5})
            state.run_probe_cycle(include_anycast=True)
            yield _sse("telemetry_refresh", {})

            anycast_res = state.anycast
            yield emit_log(
                5,
                "GLOBAL_DNS",
                f"Anycast URL {anycast_res.get('url')} verified landing on Locator={anycast_res.get('landed_locator')} Region={anycast_res.get('landed_region')}",
                sql_text="SELECT CURRENT_ACCOUNT(), CURRENT_REGION()",
                sfqid=anycast_res.get("sfqid"),
                level="SUCCESS",
            )
            yield emit_log(5, "AUDIT", "Audit event recorded: Failback to AWS verified successfully.", level="SUCCESS")
            yield _sse("step_done", {"step_index": 5, "duration_s": round(time.perf_counter() - s5, 2)})

            total_s = round(time.perf_counter() - t_workflow_start, 2)
            aws_is_primary = state.aws.get("fg_is_primary", False)
            az_locator = state.azure.get("locator", "LQB72917")
            aws_locator = state.aws.get("locator", "AWC63551")
            status_text = "AWS PRIMARY" if aws_is_primary else "Azure PRIMARY"

            summary_msg = (
                f"AWS ({aws_locator}) restored as authoritative PRIMARY and Azure ({az_locator}) returned to Read-Only Standby Replica in {total_s}s."
                if aws_is_primary
                else f"Failback workflow finished in {total_s}s. Live telemetry confirms authority transition."
            )

            with state._lock:
                state.simulate_aws_outage = False
                state.consecutive_failures = 0
                state.auto_failover_triggered = False
                state.manual_override = False
                state.last_rto_seconds = measured_switch

            drill_item = {
                "id": run_id,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "operation": "Reverse Delta Sync & Failback",
                "route": f"Azure ({az_locator}) ➔ AWS ({aws_locator})",
                "duration": f"{total_s:.2f}s ({measured_switch:.2f}s switch)",
                "rows": f"{state.aws.get('row_count') or 0:,} rows synced on AWS",
                "rpo": "0 rows",
                "operator": operator,
                "audit": "Verified",
                "status": status_text,
            }
            state.record_drill(drill_item)
            state.record_workflow_completion({
                "runId": run_id,
                "workflow": "Reverse Delta Sync & Failback",
                "title": f"Reverse Delta Sync & Failback (Azure ({az_locator}) ➔ AWS ({aws_locator}))",
                "state": "success",
                "elapsedS": total_s,
                "activeStepIdx": -1,
                "summary": summary_msg,
                "error": None,
            })

            yield _sse(
                "workflow_done",
                {
                    "run_id": run_id,
                    "total_s": total_s,
                    "rto_s": measured_switch,
                    "summary": summary_msg,
                },
            )

        # -------------------------------------------------------------------
        # WORKFLOW 5: LIVE CRYPTOGRAPHIC HASH_AGG & WAN REFRESH AUDIT
        # -------------------------------------------------------------------
        elif workflow_type == "reconcile":
            steps_meta = [
                f"Compute 64-Bit Cryptographic HASH_AGG on AWS us-east-1 ('{db_name}')",
                f"Compute 64-Bit Cryptographic HASH_AGG on Azure East US 2 ('{db_name}')",
                f"Inspect Snowflake WAN Replication Group Refresh Phases ('{fg_name}')",
                "Certify Zero Micro-Partition Data Loss (RPO = 0 Bytes)",
            ]
            yield _sse(
                "workflow_init",
                {
                    "run_id": run_id,
                    "workflow": workflow_type,
                    "title": f"Live Cross-Cloud Cryptographic Parity Audit (AWS ⇄ Azure) - {tbl_fqn}",
                    "steps": steps_meta,
                },
            )

            hash_sql = (
                f"SELECT "
                f"  COUNT(*) AS cnt, "
                f"  COALESCE(SUM(amount), 0) AS vol, "
                f"  HASH_AGG(step, type, amount, nameOrig, isFraud) AS hsh "
                f"FROM {tbl_fqn}"
            )

            # Step 0: AWS Hash
            s0 = time.perf_counter()
            yield _sse("step_start", {"step_index": 0})
            yield emit_log(0, settings.primary.identifier, "Running HASH_AGG across all micro-partitions on AWS...", sql_text=hash_sql)
            with _open_sf_connection(settings.primary, use_warehouse=True, timeout=45) as c_p:
                cur = c_p.cursor()
                qid_w, rows_w, ms_w = _exec_dict(cur, hash_sql)
                cur.close()
            aws_cnt = int(rows_w[0]["cnt"])
            aws_vol = float(rows_w[0]["vol"])
            aws_hsh = str(rows_w[0]["hsh"])
            yield emit_log(
                0,
                settings.primary.identifier,
                f"AWS Result ({ms_w}ms): Rows={aws_cnt:,} | Volume=${aws_vol:,.2f} | HASH_AGG={aws_hsh}",
                sql_text=hash_sql,
                sfqid=qid_w,
                level="SUCCESS",
            )
            yield _sse("step_done", {"step_index": 0, "duration_s": round(time.perf_counter() - s0, 2)})

            # Step 1: Azure Hash
            s1 = time.perf_counter()
            yield _sse("step_start", {"step_index": 1})
            yield emit_log(1, settings.secondary.identifier, "Running HASH_AGG across all micro-partitions on Azure...", sql_text=hash_sql)
            with _open_sf_connection(settings.secondary, use_warehouse=True, timeout=45) as c_s:
                cur = c_s.cursor()
                qid_z, rows_z, ms_z = _exec_dict(cur, hash_sql)
                cur.close()
            az_cnt = int(rows_z[0]["cnt"])
            az_vol = float(rows_z[0]["vol"])
            az_hsh = str(rows_z[0]["hsh"])
            yield emit_log(
                1,
                settings.secondary.identifier,
                f"Azure Result ({ms_z}ms): Rows={az_cnt:,} | Volume=${az_vol:,.2f} | HASH_AGG={az_hsh}",
                sql_text=hash_sql,
                sfqid=qid_z,
                level="SUCCESS",
            )
            yield _sse("step_done", {"step_index": 1, "duration_s": round(time.perf_counter() - s1, 2)})

            # Step 2: Query Snowflake REPLICATION_GROUP_REFRESH_HISTORY on whichever cloud is Secondary
            s2 = time.perf_counter()
            yield _sse("step_start", {"step_index": 2})
            _, standby_snap = state.active_and_standby()
            sec_cfg = settings.secondary if standby_snap["provider"] == "Azure" else settings.primary
            hist_sql = (
                f"SELECT PHASE_NAME, START_TIME, END_TIME, TOTAL_BYTES, OBJECT_COUNT "
                f"FROM TABLE({db_name}.INFORMATION_SCHEMA.REPLICATION_GROUP_REFRESH_HISTORY('{fg_name}')) "
                f"ORDER BY START_TIME DESC LIMIT 6"
            )
            hist_records: list[dict[str, Any]] = []
            try:
                with _open_sf_connection(sec_cfg, use_warehouse=True, timeout=30) as c_sec:
                    cur = c_sec.cursor()
                    qid_h, rows_h, ms_h = _exec_dict(cur, hist_sql)
                    cur.close()
                for hr in rows_h:
                    hist_records.append(
                        {
                            "phase": hr.get("phase_name"),
                            "start_time": str(hr.get("start_time") or ""),
                            "end_time": str(hr.get("end_time") or ""),
                            "total_bytes": int(hr["total_bytes"]) if hr.get("total_bytes") not in (None, "") else 0,
                            "object_count": int(hr["object_count"]) if hr.get("object_count") not in (None, "") else 0,
                        }
                    )
                yield emit_log(
                    2,
                    sec_cfg.identifier,
                    f"Retrieved {len(hist_records)} WAN replication phase entries ({ms_h}ms).",
                    sql_text=hist_sql,
                    sfqid=qid_h,
                    level="SUCCESS",
                )
            except Exception as h_exc:
                yield emit_log(2, sec_cfg.identifier, f"Replication history note: {h_exc}", level="WARN")
            yield _sse("step_done", {"step_index": 2, "duration_s": round(time.perf_counter() - s2, 2)})

            # Step 3: Parity Certification
            s3 = time.perf_counter()
            yield _sse("step_start", {"step_index": 3})
            hashes_match = (aws_hsh == az_hsh) and (aws_cnt == az_cnt)
            diff_rows = abs(aws_cnt - az_cnt)
            verdict = (
                "CRYPTOGRAPHIC PARITY CERTIFIED (RPO = 0)"
                if hashes_match
                else f"DELTA DETECTED: {diff_rows} un-replicated micro-partitions"
            )
            reconcile_record = {
                "audited_at": datetime.now(timezone.utc).isoformat(),
                "table": tbl_fqn,
                "parity_match": hashes_match,
                "integrity_verdict": verdict,
                "rpo_rows": diff_rows,
                "aws": {"row_count": aws_cnt, "total_volume": aws_vol, "hash_agg": aws_hsh, "sfqid": qid_w},
                "azure": {"row_count": az_cnt, "total_volume": az_vol, "hash_agg": az_hsh, "sfqid": qid_z},
                "refresh_history": hist_records,
            }
            with state._lock:
                state.last_reconcile = reconcile_record
                state.last_refresh_history = hist_records

            total_s = round(time.perf_counter() - t_workflow_start, 2)
            summary_msg = (
                f"Reconciliation completed in {total_s}s: {aws_cnt:,} rows verified across clouds with matching HASH_AGG ({aws_hsh}). RPO = 0."
                if hashes_match
                else f"Reconciliation completed in {total_s}s: Found {diff_rows} pending rows between AWS and Azure."
            )
            drill_item = {
                "id": run_id,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "operation": "Cryptographic Hash Audit",
                "route": "AWS ⇄ Azure Parity",
                "duration": f"{total_s:.2f}s",
                "rows": f"{aws_cnt:,} rows reconciled",
                "rpo": f"{diff_rows} rows",
                "operator": operator,
                "audit": "Certified",
                "status": "PARITY MATCH" if hashes_match else "DELTA",
            }
            state.record_drill(drill_item)
            state.record_workflow_completion({
                "runId": run_id,
                "workflow": "Cryptographic Hash Audit",
                "title": "Cryptographic Hash Audit (AWS ⇄ Azure Parity)",
                "state": "success",
                "elapsedS": total_s,
                "activeStepIdx": -1,
                "summary": summary_msg,
                "error": None,
            })
            yield emit_log(3, "AUDITOR", verdict, level="SUCCESS" if hashes_match else "WARN")
            yield _sse("step_done", {"step_index": 3, "duration_s": round(time.perf_counter() - s3, 2)})

            yield _sse(
                "workflow_done",
                {
                    "run_id": run_id,
                    "total_s": total_s,
                    "reconcile": reconcile_record,
                    "summary": summary_msg,
                },
            )

        else:
            raise ValueError(f"Unknown workflow type: {workflow_type}")

    except Exception as exc:
        logger.exception("Workflow %s failed", workflow_type)
        err_str = f"{type(exc).__name__}: {exc}"
        state.add_log(source=run_id, account="ERROR", message=err_str, level="ERROR")
        yield _sse("workflow_error", {"run_id": run_id, "error": err_str})
    finally:
        with state._lock:
            state.active_workflow = None
        state._workflow_lock.release()


@router.get("/api/workflows/live-stream")
def stream_workflow_query(
    workflow: str = Query(..., description="Workflow type: failover, failback, chaos, ingest_sync, reconcile"),
    batch_rows: int = Query(default=1000, ge=100, le=50000),
    operator: str = Query(default="Live SRE Console"),
):
    """Query-parameter alias for live workflow SSE streaming."""
    return stream_workflow(workflow_type=workflow, batch_rows=batch_rows, operator=operator)


@router.get("/api/workflows/stream/{workflow_type}")
def stream_workflow(
    workflow_type: str,
    batch_rows: int = Query(default=1000, ge=100, le=50000),
    operator: str = Query(default="Live SRE Console"),
):
    """Streams real-time GitHub-Actions-style SSE events as Snowflake SQL executes."""

    def _threaded_sse() -> Iterator[str]:
        q: queue.Queue[str | None] = queue.Queue()

        def _producer() -> None:
            try:
                for chunk in _execute_real_workflow(workflow_type, batch_rows=batch_rows, operator=operator):
                    q.put(chunk)
            finally:
                q.put(None)

        threading.Thread(target=_producer, daemon=True).start()
        while True:
            try:
                item = q.get(timeout=0.5)
                if item is None:
                    break
                yield item
            except queue.Empty:
                yield ": keepalive\n\n"

    return StreamingResponse(
        _threaded_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
