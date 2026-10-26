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
