"""SQL helpers. DDL like ALTER FAILOVER GROUP cannot use bind parameters for
object names, so every identifier is strictly validated before interpolation."""

from __future__ import annotations

import re

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]{0,254}$")


def validate_identifier(name: str) -> str:
    """Return `name` if it is a safe unquoted Snowflake identifier, else raise ValueError."""
    if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name):
        raise ValueError(f"Unsafe or invalid Snowflake identifier: {name!r}")
    return name


HEALTH_PROBE = "SELECT 1"  # Served by cloud services layer: no warehouse, no credits


def promote_failover_group(group: str) -> str:
    return f"ALTER FAILOVER GROUP {validate_identifier(group)} PRIMARY"


def refresh_failover_group(group: str) -> str:
    return f"ALTER FAILOVER GROUP {validate_identifier(group)} REFRESH"


def promote_connection(connection: str) -> str:
    return f"ALTER CONNECTION {validate_identifier(connection)} PRIMARY"


def replication_lag(database: str, group: str) -> str:
    """Seconds since the start of the last COMPLETED refresh (data is consistent as of refresh start).

    Requires a warehouse, so it is only run on demand (never in the tight probe loop).
    """
    db = validate_identifier(database)
    grp = validate_identifier(group)
    return (
        "SELECT DATEDIFF('second', START_TIME, CURRENT_TIMESTAMP()) AS LAG_SECONDS "
        f"FROM TABLE({db}.INFORMATION_SCHEMA.REPLICATION_GROUP_REFRESH_HISTORY('{grp}')) "
        "WHERE PHASE_NAME = 'COMPLETED' ORDER BY START_TIME DESC LIMIT 1"
    )


def show_connection(connection: str) -> str:
    """Query current primary/replica status and client redirection URL."""
    return f"SHOW CONNECTIONS LIKE '{validate_identifier(connection)}'"


def show_failover_group(group: str) -> str:
    """Query current primary account and allowed accounts for failover group."""
    return f"SHOW FAILOVER GROUPS LIKE '{validate_identifier(group)}'"


# =========================================================================
# Workload Cataloging & Blueprint Synchronization DDL (Phase 2)
# =========================================================================

def create_workload_catalog_table(database: str, schema: str = "DR_STAGING") -> str:
    """DDL for storing container workload blueprints & replication metadata."""
    db = validate_identifier(database)
    sch = validate_identifier(schema)
    return f"""
    CREATE TABLE IF NOT EXISTS {db}.{sch}.DR_WORKLOAD_CATALOG (
        workload_name VARCHAR(128) NOT NULL,
        version VARCHAR(64) DEFAULT '1.0.0',
        manifest_variant VARIANT NOT NULL,
        active_cloud VARCHAR(32) DEFAULT 'AWS',
        synced_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(),
        PRIMARY KEY (workload_name)
    )
    """


def create_workload_pipe(database: str, stage_name: str, schema: str = "DR_STAGING") -> str:
    """Defines Snowpipe auto-ingestion for workload blueprints placed in external stages."""
    db = validate_identifier(database)
    sch = validate_identifier(schema)
    stg = validate_identifier(stage_name)
    return f"""
    CREATE OR REPLACE PIPE {db}.{sch}.SF_WORKLOAD_PIPE
    AUTO_INGEST = TRUE
    AS
    COPY INTO {db}.{sch}.DR_WORKLOAD_CATALOG (workload_name, version, manifest_variant)
    FROM (
        SELECT
            $1:name::VARCHAR,
            $1:version::VARCHAR,
            $1
        FROM @{db}.{sch}.{stg}/workloads/
    )
    FILE_FORMAT = (TYPE = 'JSON')
    """

