from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from sf_dr_controller.config import AccountConfig, Settings


class FakeRunner:
    """Scriptable SqlRunner: per-account health toggles + statement log."""

    def __init__(self) -> None:
        self.healthy = {"primary": True, "secondary": True}
        self.fail_statements: set[str] = set()
        self.calls: list[tuple[str, str]] = []

    def run(
        self, account: AccountConfig, statements: Sequence[str], *, use_warehouse: bool = False
    ) -> list[list[tuple[Any, ...]]]:
        if not self.healthy[account.label]:
            raise ConnectionError(f"{account.label} unreachable")
        out = []
        for stmt in statements:
            self.calls.append((account.label, stmt))
            if stmt in self.fail_statements:
                raise RuntimeError(f"boom: {stmt}")
            if stmt == "SELECT 1":
                out.append([(1,)])
            elif "REPLICATION_GROUP_REFRESH_HISTORY" in stmt:
                out.append([(42,)])
            else:
                out.append([])
        return out


@pytest.fixture
def runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        snowflake_account_primary="ORG-AWS_PRIMARY",
        snowflake_account_secondary="ORG-AZURE_SECONDARY",
        snowflake_user="TEST_USER",
        snowflake_password="not-a-real-secret",
        dr_failure_threshold=3,
        dr_probe_interval_seconds=0.01,
    )
