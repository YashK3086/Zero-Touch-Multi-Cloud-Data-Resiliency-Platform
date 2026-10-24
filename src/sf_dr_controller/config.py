"""Runtime configuration loaded from environment variables / `.env`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .sql import validate_identifier


@dataclass(frozen=True)
class AccountConfig:
    """Connection parameters for one Snowflake account."""

    label: str  # "primary" | "secondary"
    identifier: str  # ORG-ACCOUNT
    user: str
    role: str
    password: str | None = None
    private_key_path: Path | None = None
    warehouse: str | None = None

    def __repr__(self) -> str:  # never leak secrets into logs
        return f"AccountConfig(label={self.label!r}, identifier={self.identifier!r}, user={self.user!r})"


class Settings(BaseSettings):
    """All controller settings. Env var names are the upper-cased field names."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Snowflake accounts -------------------------------------------------
    snowflake_account_primary: str
    snowflake_account_secondary: str
    snowflake_user: str
    snowflake_password: SecretStr | None = None
    snowflake_private_key_path: Path | None = None
    snowflake_role: str = "ACCOUNTADMIN"
    snowflake_warehouse: str = "DR_CONTROLLER_WH"
    snowflake_database: str = "SF_DR_DEMO_DB"

    # Secondary account may use a different admin login (created via CREATE ACCOUNT)
    snowflake_secondary_user: str | None = None
    snowflake_secondary_password: SecretStr | None = None

    # --- DR objects ---------------------------------------------------------
    snowflake_failover_group_name: str = "SF_DR_FAILOVER_GROUP"
    snowflake_redirect_connection_name: str = "SF_DR_GLOBAL_REDIRECT"

    # --- Controller tunables ------------------------------------------------
    dr_probe_interval_seconds: float = Field(default=10.0, gt=0)
    dr_probe_timeout_seconds: int = Field(default=10, ge=1, le=120)
    dr_failure_threshold: int = Field(default=3, ge=1)
    dr_max_replication_lag_seconds: int = Field(default=300, ge=0)
    dr_auto_failover: bool = True
    dr_dry_run: bool = False
    dr_webhook_url: str | None = None

    @field_validator(
        "snowflake_failover_group_name",
        "snowflake_redirect_connection_name",
        "snowflake_warehouse",
        "snowflake_database",
    )
    @classmethod
    def _safe_identifier(cls, v: str) -> str:
        return validate_identifier(v)

    @field_validator("snowflake_account_primary", "snowflake_account_secondary")
    @classmethod
    def _account_format(cls, v: str) -> str:
        if "-" not in v or v.startswith("<"):
            raise ValueError("Snowflake account must use ORGNAME-ACCOUNTNAME format")
        return v

    # --- Derived ------------------------------------------------------------
    def _secret(self, s: SecretStr | None) -> str | None:
        return s.get_secret_value() if s else None

    @property
    def primary(self) -> AccountConfig:
        return AccountConfig(
            label="primary",
            identifier=self.snowflake_account_primary,
            user=self.snowflake_user,
            role=self.snowflake_role,
            password=self._secret(self.snowflake_password),
            private_key_path=self.snowflake_private_key_path,
            warehouse=self.snowflake_warehouse,
        )

    @property
    def secondary(self) -> AccountConfig:
        return AccountConfig(
            label="secondary",
            identifier=self.snowflake_account_secondary,
            user=self.snowflake_secondary_user or self.snowflake_user,
            role=self.snowflake_role,
            password=self._secret(self.snowflake_secondary_password or self.snowflake_password),
            private_key_path=self.snowflake_private_key_path,
            warehouse=self.snowflake_warehouse,
        )
