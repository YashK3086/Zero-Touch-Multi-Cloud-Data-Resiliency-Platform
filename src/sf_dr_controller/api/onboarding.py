"""SaaS 100% UI-Driven Onboarding & Provisioning API Endpoints.

Enables Zero-Touch credential verification, account linking, automated
warehouse creation, failover group replication, and environment updates.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..bootstrap import provision_multi_cloud_dr, verify_account_connection
from ..config import AccountConfig, Settings
from .state import state

logger = logging.getLogger("sf_dr_controller.api.onboarding")

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


class VerifyOnboardingRequest(BaseModel):
    primary_account: str
    primary_user: str
    primary_password: str
    secondary_account: str
    secondary_user: str
    secondary_password: str
    primary_role: str = "ACCOUNTADMIN"
    secondary_role: str = "ACCOUNTADMIN"


class ProvisionOnboardingRequest(BaseModel):
    primary_account: str
    primary_user: str
    primary_password: str
    secondary_account: str
    secondary_user: str
    secondary_password: str
    database_name: str = "SF_DR_DEMO_DB"
    warehouse_name: str = "DR_CONTROLLER_WH"
    failover_group_name: str = "SF_DR_FAILOVER_GROUP"
    redirect_connection_name: str = "SF_DR_GLOBAL_REDIRECT"
    primary_role: str = "ACCOUNTADMIN"
    secondary_role: str = "ACCOUNTADMIN"


@router.get("/status")
@router.get("/status/")
def get_onboarding_status() -> dict[str, Any]:
    """Returns whether multi-cloud accounts have been linked and configured."""
    settings = Settings()
    return {
        "is_configured": settings.is_configured,
        "primary_account": settings.snowflake_account_primary,
        "secondary_account": settings.snowflake_account_secondary,
        "user": settings.snowflake_user,
        "database": settings.snowflake_database,
        "warehouse": settings.snowflake_warehouse,
        "failover_group": settings.snowflake_failover_group_name,
        "connection": settings.snowflake_redirect_connection_name,
    }


@router.post("/verify")
@router.post("/verify/")
def verify_onboarding_credentials(req: VerifyOnboardingRequest) -> dict[str, Any]:
    """Tests live connectivity to primary and secondary accounts before provisioning."""
    try:
        p_cfg = AccountConfig(
            label="primary",
            identifier=req.primary_account.strip(),
            user=req.primary_user.strip(),
            role=req.primary_role.strip(),
            password=req.primary_password.strip(),
        )
        s_cfg = AccountConfig(
            label="secondary",
            identifier=req.secondary_account.strip(),
            user=req.secondary_user.strip(),
            role=req.secondary_role.strip(),
            password=req.secondary_password.strip(),
        )
        p_res = verify_account_connection(p_cfg)
        s_res = verify_account_connection(s_cfg)
        return {
            "valid": True,
            "primary": p_res,
            "secondary": s_res,
        }
    except Exception as e:
        logger.exception("Onboarding credential validation failed")
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/provision")
@router.post("/provision/")
def provision_onboarding_pipeline(req: ProvisionOnboardingRequest) -> dict[str, Any]:
    """Zero-Touch 1-Click Multi-Cloud Provisioning: Warehouses, Failover Groups, Connections & WAN Sync."""
    try:
        p_cfg = AccountConfig(
            label="primary",
            identifier=req.primary_account.strip(),
            user=req.primary_user.strip(),
            role=req.primary_role.strip(),
            password=req.primary_password.strip(),
        )
        s_cfg = AccountConfig(
            label="secondary",
            identifier=req.secondary_account.strip(),
            user=req.secondary_user.strip(),
            role=req.secondary_role.strip(),
            password=req.secondary_password.strip(),
        )
        result = provision_multi_cloud_dr(
            primary=p_cfg,
            secondary=s_cfg,
            database_name=req.database_name.strip(),
            warehouse_name=req.warehouse_name.strip(),
            failover_group_name=req.failover_group_name.strip(),
            redirect_connection_name=req.redirect_connection_name.strip(),
        )

        # Update environment variables and persist to .env
        env_lines = [
            f'SNOWFLAKE_ACCOUNT_PRIMARY="{req.primary_account.strip()}"',
            f'SNOWFLAKE_ACCOUNT_SECONDARY="{req.secondary_account.strip()}"',
            f'SNOWFLAKE_USER="{req.primary_user.strip()}"',
            f'SNOWFLAKE_PASSWORD="{req.primary_password.strip()}"',
            f'SNOWFLAKE_SECONDARY_USER="{req.secondary_user.strip()}"',
            f'SNOWFLAKE_SECONDARY_PASSWORD="{req.secondary_password.strip()}"',
            f'SNOWFLAKE_ROLE="{req.primary_role.strip()}"',
            f'SNOWFLAKE_WAREHOUSE="{req.warehouse_name.strip()}"',
            f'SNOWFLAKE_DATABASE="{req.database_name.strip()}"',
            f'SNOWFLAKE_FAILOVER_GROUP_NAME="{req.failover_group_name.strip()}"',
            f'SNOWFLAKE_REDIRECT_CONNECTION_NAME="{req.redirect_connection_name.strip()}"',
        ]
        for k_val in env_lines:
            k, v = k_val.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

        # Persist to .env
        env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
        existing: dict[str, str] = {}
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    existing[k.strip()] = v.strip()
        for k_val in env_lines:
            k, v = k_val.split("=", 1)
            existing[k.strip()] = v.strip()

        env_path.write_text("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n", encoding="utf-8")

        state.add_log(
            source="onboarding",
            account="SYSTEM",
            message=f"🎉 Zero-Touch Multi-Cloud DR Linked: {req.primary_account} <-> {req.secondary_account} (Protected DB={req.database_name})",
            level="SUCCESS",
        )
        state.run_probe_cycle(include_anycast=True)
        return result
    except Exception as e:
        logger.exception("Onboarding provisioning failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
