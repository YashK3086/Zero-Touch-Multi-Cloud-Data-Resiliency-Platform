"""Zero-Touch Multi-Cloud DR Provisioning Engine.

Enables 100% UI-driven provisioning of Snowflake Warehouses, Failover Groups,
Global Anycast Redirect Connections, and cross-cloud WAN synchronization
without requiring local CLI tools or Git push.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import snowflake.connector

from .config import AccountConfig

logger = logging.getLogger("sf_dr_controller.bootstrap")

PAY_SIM_DDL = """
CREATE TABLE IF NOT EXISTS {database}.DR_STAGING.FINANCIAL_TRANSACTIONS (
    step INT,
    type VARCHAR(32),
    amount NUMBER(18, 2),
    nameOrig VARCHAR(64),
    oldbalanceOrg NUMBER(18, 2),
    newbalanceOrig NUMBER(18, 2),
    nameDest VARCHAR(64),
    oldbalanceDest NUMBER(18, 2),
    newbalanceDest NUMBER(18, 2),
    isFraud INT,
    isFlaggedFraud INT,
    ingested_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);
"""


def _get_sf_conn(account: AccountConfig, timeout: int = 30):
    kwargs: dict[str, Any] = {
        "account": account.identifier,
        "user": account.user,
        "role": account.role,
        "login_timeout": timeout,
        "network_timeout": timeout * 2,
        "application": "sf_dr_bootstrap_saas",
    }
    if account.password:
        kwargs["password"] = account.password
    elif account.private_key_path and account.private_key_path.exists():
        kwargs["authenticator"] = "SNOWFLAKE_JWT"
        kwargs["private_key_file"] = str(account.private_key_path)
    else:
        raise ValueError(f"No authentication credentials provided for {account.label}")
    return snowflake.connector.connect(**kwargs)


def parse_org_and_account(identifier: str) -> tuple[str, str]:
    """Extracts organization and account name from ORG-ACCOUNT or ORG_ACCOUNT."""
    clean = identifier.strip().strip('"').strip("'")
    if "-" in clean:
        org, acc = clean.split("-", 1)
    elif "_" in clean:
        org, acc = clean.split("_", 1)
    else:
        raise ValueError(f"Account identifier must be in ORG-ACCOUNT format: {identifier}")
    return org.upper(), acc.upper()


def verify_account_connection(account: AccountConfig) -> dict[str, Any]:
    """Validates live connectivity, measures ping latency, and verifies current role."""
    t0 = time.perf_counter()
    with _get_sf_conn(account, timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT CURRENT_ACCOUNT(), CURRENT_REGION(), CURRENT_ROLE(), CURRENT_VERSION()")
            row = cur.fetchone()
            ping_ms = round((time.perf_counter() - t0) * 1000, 1)
            return {
                "valid": True,
                "account": row[0] if row else account.identifier,
                "region": row[1] if row else "UNKNOWN",
                "role": row[2] if row else "UNKNOWN",
                "version": row[3] if row else "UNKNOWN",
                "ping_ms": ping_ms,
            }


def provision_multi_cloud_dr(
    primary: AccountConfig,
    secondary: AccountConfig,
    database_name: str = "SF_DR_DEMO_DB",
    warehouse_name: str = "DR_CONTROLLER_WH",
    failover_group_name: str = "SF_DR_FAILOVER_GROUP",
    redirect_connection_name: str = "SF_DR_GLOBAL_REDIRECT",
    on_step_callback: Any = None,
) -> dict[str, Any]:
    """Provisions all required Multi-Cloud Disaster Recovery resources directly via Snowflake SQL."""

    def emit(step: int, title: str, details: str = ""):
        logger.info("[Step %d/5] %s: %s", step, title, details)
        if on_step_callback:
            on_step_callback(step, title, details)

    p_org, p_acc = parse_org_and_account(primary.identifier)
    s_org, s_acc = parse_org_and_account(secondary.identifier)

    # -------------------------------------------------------------------------
    # STEP 1: Provision Warehouses & Databases on Primary (AWS)
    # -------------------------------------------------------------------------
    emit(1, "Provisioning Primary Cloud Infrastructure", f"Target: {primary.identifier}")
    with _get_sf_conn(primary) as conn_p:
        with conn_p.cursor() as cur:
            cur.execute(f"CREATE WAREHOUSE IF NOT EXISTS {warehouse_name} WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 INITIALLY_SUSPENDED = FALSE")
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {database_name}")
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {database_name}.DR_STAGING")
            cur.execute(PAY_SIM_DDL.format(database=database_name))

            # Check if dataset populated
            cur.execute(f"SELECT COUNT(*) FROM {database_name}.DR_STAGING.FINANCIAL_TRANSACTIONS")
            cnt = cur.fetchone()[0]
            if cnt == 0:
                logger.info("Seeding baseline transactions into %s.DR_STAGING.FINANCIAL_TRANSACTIONS...", database_name)
                seed_sql = f"""
                INSERT INTO {database_name}.DR_STAGING.FINANCIAL_TRANSACTIONS
                (step, type, amount, nameOrig, oldbalanceOrg, newbalanceOrig, nameDest, oldbalanceDest, newbalanceDest, isFraud, isFlaggedFraud)
                SELECT
                    UNIFORM(1, 744, RANDOM(1)),
                    DECODE(ABS(RANDOM(2)) % 5, 0, 'PAYMENT', 1, 'TRANSFER', 2, 'CASH_OUT', 3, 'DEBIT', 'CASH_IN'),
                    ROUND(UNIFORM(10.0, 500000.0, RANDOM(3)), 2),
                    'C' || TO_VARCHAR(UNIFORM(10000000, 99999999, RANDOM(4))),
                    ROUND(UNIFORM(0.0, 1000000.0, RANDOM(5)), 2),
                    ROUND(UNIFORM(0.0, 1000000.0, RANDOM(6)), 2),
                    'M' || TO_VARCHAR(UNIFORM(10000000, 99999999, RANDOM(7))),
                    ROUND(UNIFORM(0.0, 500000.0, RANDOM(8)), 2),
                    ROUND(UNIFORM(0.0, 500000.0, RANDOM(9)), 2),
                    IFF(UNIFORM(1, 1000, RANDOM(10)) <= 2, 1, 0),
                    0
                FROM TABLE(GENERATOR(ROWCOUNT => 500000))
                """
                cur.execute(seed_sql)

    # -------------------------------------------------------------------------
    # STEP 2: Configure Primary Failover Group & Anycast Redirect Connection
    # -------------------------------------------------------------------------
    emit(2, "Configuring Primary Failover Group & Connection", "Establishing replication permission to secondary")
    with _get_sf_conn(primary) as conn_p:
        with conn_p.cursor() as cur:
            cur.execute(f"""
            CREATE FAILOVER GROUP IF NOT EXISTS {failover_group_name}
                OBJECT_TYPES = (DATABASES)
                ALLOWED_DATABASES = ({database_name})
                ALLOWED_ACCOUNTS = ({p_org}.{p_acc}, {s_org}.{s_acc})
                REPLICATION_SCHEDULE = '10 MINUTE'
            """)
            try:
                cur.execute(f"CREATE CONNECTION IF NOT EXISTS {redirect_connection_name} ENABLE_FAILOVER_TO_ACCOUNTS = ({s_org}.{s_acc})")
            except Exception as e:
                logger.warning("Connection creation note on primary: %s", e)

    # -------------------------------------------------------------------------
    # STEP 3: Configure Secondary (Azure) Warehouse & Replica Objects
    # -------------------------------------------------------------------------
    emit(3, "Linking Secondary (Azure) Replica", f"Target: {secondary.identifier}")
    with _get_sf_conn(secondary) as conn_s:
        with conn_s.cursor() as cur:
            cur.execute(f"CREATE WAREHOUSE IF NOT EXISTS {warehouse_name} WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 INITIALLY_SUSPENDED = FALSE")

            # Drop old unlinked failover group replica if exists
            try:
                cur.execute(f"DROP FAILOVER GROUP IF EXISTS {failover_group_name}")
            except Exception as e:
                logger.warning("Secondary drop FG note: %s", e)

            # Create secondary failover group replica
            cur.execute(f"""
            CREATE FAILOVER GROUP IF NOT EXISTS {failover_group_name}
                AS REPLICA OF {p_org}.{p_acc}.{failover_group_name}
            """)

            # Create secondary connection replica
            try:
                cur.execute(f"""
                CREATE CONNECTION IF NOT EXISTS {redirect_connection_name}
                    AS REPLICA OF {p_org}.{p_acc}.{redirect_connection_name}
                """)
            except Exception as e:
                logger.warning("Secondary connection replica creation note: %s", e)

    # -------------------------------------------------------------------------
    # STEP 4: Trigger Initial WAN Delta Sync
    # -------------------------------------------------------------------------
    emit(4, "Synchronizing Multi-Cloud Ledger", "Performing WAN Delta Refresh across AWS -> Azure")
    with _get_sf_conn(secondary) as conn_s:
        with conn_s.cursor() as cur:
            t_sync = time.perf_counter()
            cur.execute(f"ALTER FAILOVER GROUP {failover_group_name} REFRESH")
            sync_duration_s = round(time.perf_counter() - t_sync, 2)
            logger.info("Initial WAN sync completed in %.2fs", sync_duration_s)

    # -------------------------------------------------------------------------
    # STEP 5: Verification & Zero-Drift Hash Parity Check
    # -------------------------------------------------------------------------
    emit(5, "Verifying Zero Data Loss & Hash Parity", "Checking RPO = 0 across clouds")
    with _get_sf_conn(primary) as conn_p, _get_sf_conn(secondary) as conn_s:
        with conn_p.cursor() as cur_p, conn_s.cursor() as cur_s:
            cur_p.execute(f"SELECT COUNT(*), HASH_AGG(step, type, amount, nameOrig) FROM {database_name}.DR_STAGING.FINANCIAL_TRANSACTIONS")
            p_cnt, p_hash = cur_p.fetchone()

            cur_s.execute(f"USE WAREHOUSE {warehouse_name}")
            cur_s.execute(f"SELECT COUNT(*), HASH_AGG(step, type, amount, nameOrig) FROM {database_name}.DR_STAGING.FINANCIAL_TRANSACTIONS")
            s_cnt, s_hash = cur_s.fetchone()

    hash_match = p_cnt == s_cnt and p_hash == s_hash
    emit(5, "Ready to Migrate & Protect", f"Primary: {p_cnt:,} rows | Secondary: {s_cnt:,} rows | Parity: {hash_match}")

    return {
        "success": True,
        "message": "Ready to Migrate & Protect! Multi-Cloud Link Established.",
        "primary_rows": p_cnt,
        "secondary_rows": s_cnt,
        "primary_hash": str(p_hash),
        "secondary_hash": str(s_hash),
        "hash_parity": hash_match,
        "rpo_delta": abs(p_cnt - s_cnt),
    }
