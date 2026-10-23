"""Snowflake execution layer behind a small Protocol so logic is unit-testable."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Protocol

from .config import AccountConfig

logger = logging.getLogger(__name__)


class SqlRunner(Protocol):
    def run(
        self, account: AccountConfig, statements: Sequence[str], *, use_warehouse: bool = False
    ) -> list[list[tuple[Any, ...]]]:
        """Execute statements sequentially in ONE fresh session; return rows per statement."""
        ...


class SnowflakeSqlRunner:
    """Opens a brand-new session per call.

    A fresh login is deliberate: network policies and user disablement only
    affect *new* logins, so session reuse would mask real outages.
    """

    def __init__(self, timeout_seconds: int = 10) -> None:
        self.timeout = timeout_seconds

    def _connect(self, account: AccountConfig, use_warehouse: bool):
        import snowflake.connector  # lazy: unit tests never import the connector

        kwargs: dict[str, Any] = {
            "account": account.identifier,
            "user": account.user,
            "role": account.role,
            "login_timeout": self.timeout,
            "network_timeout": self.timeout,
            "socket_timeout": self.timeout,
            "application": "sf_dr_controller",
            "client_session_keep_alive": False,
        }
        if use_warehouse and account.warehouse:
            kwargs["warehouse"] = account.warehouse
        if account.private_key_path:
            kwargs["authenticator"] = "SNOWFLAKE_JWT"
            kwargs["private_key_file"] = str(account.private_key_path)
        elif account.password:
            kwargs["password"] = account.password
        else:
            raise ValueError(f"No credentials configured for {account.label} account")
        return snowflake.connector.connect(**kwargs)

    def run(
        self, account: AccountConfig, statements: Sequence[str], *, use_warehouse: bool = False
    ) -> list[list[tuple[Any, ...]]]:
        conn = self._connect(account, use_warehouse)
        try:
            results: list[list[tuple[Any, ...]]] = []
            with conn.cursor() as cur:
                for stmt in statements:
                    logger.debug("exec on %s: %s", account.label, stmt)
                    cur.execute(stmt, timeout=self.timeout * 6)
                    results.append(list(cur.fetchall()) if cur.description else [])
            return results
        finally:
            conn.close()
