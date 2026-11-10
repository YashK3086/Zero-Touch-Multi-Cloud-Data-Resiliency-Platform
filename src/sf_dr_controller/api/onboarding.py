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
    primary_cloud_provider: str = ""
    primary_cloud_region: str = ""
    primary_cloud_access_id: str = ""
    primary_cloud_secret_key: str = ""
    secondary_cloud_provider: str = ""
    secondary_cloud_region: str = ""
    secondary_cloud_access_id: str = ""
    secondary_cloud_secret_key: str = ""


@router.get("/status")
@router.get("/status/")
def get_onboarding_status() -> dict[str, Any]:
    """Returns whether multi-cloud accounts have been linked and configured."""
    settings = Settings()
    return {
        "is_configured": state.ui_connected and settings.is_configured,
        "primary_account": settings.snowflake_account_primary if state.ui_connected else "--",
        "secondary_account": settings.snowflake_account_secondary if state.ui_connected else "--",
        "user": settings.snowflake_user if state.ui_connected else "--",
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

        discovery: dict[str, Any] = {}
        try:
            from ..discovery import run_full_discovery

            discovery = run_full_discovery(p_cfg, s_cfg)
            state.last_discovery = discovery
        except Exception as d_err:
            logger.warning("Discovery probe note during verify: %s", d_err)

        return {
            "valid": True,
            "primary": p_res,
            "secondary": s_res,
            "discovery": discovery,
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
        # Apply non-placeholder cloud credentials to environment before provisioning
        from ..discovery import _valid_cred

        if req.primary_cloud_provider.strip() and req.primary_cloud_provider != "Auto-Detect":
            os.environ["PRIMARY_CLOUD_PROVIDER"] = req.primary_cloud_provider.strip()
        if req.primary_cloud_region.strip():
            os.environ["AWS_DEFAULT_REGION"] = req.primary_cloud_region.strip()
        if _valid_cred(req.primary_cloud_access_id):
            os.environ["PRIMARY_CLOUD_ACCESS_ID"] = req.primary_cloud_access_id.strip()
        if _valid_cred(req.primary_cloud_secret_key):
            os.environ["PRIMARY_CLOUD_SECRET_KEY"] = req.primary_cloud_secret_key.strip()
        if req.secondary_cloud_provider.strip() and req.secondary_cloud_provider != "Auto-Detect":
            os.environ["SECONDARY_CLOUD_PROVIDER"] = req.secondary_cloud_provider.strip()
        if req.secondary_cloud_region.strip():
            os.environ["AZURE_LOCATION"] = req.secondary_cloud_region.strip()
        if _valid_cred(req.secondary_cloud_access_id):
            os.environ["AZURE_SUBSCRIPTION_ID"] = req.secondary_cloud_access_id.strip()
        if _valid_cred(req.secondary_cloud_secret_key):
            os.environ["ARM_BEARER_TOKEN"] = req.secondary_cloud_secret_key.strip()

        result = provision_multi_cloud_dr(
            primary=p_cfg,
            secondary=s_cfg,
            database_name=req.database_name.strip(),
            warehouse_name=req.warehouse_name.strip(),
            failover_group_name=req.failover_group_name.strip(),
            redirect_connection_name=req.redirect_connection_name.strip(),
        )

        # Run live cloud discovery after provisioning so newly created S3 / Azure Blob are reflected
        try:
            from ..discovery import discover_aws, discover_azure

            state.last_discovery = {
                "aws": discover_aws(),
                "azure": discover_azure(),
            }
        except Exception as d_err:
            logger.warning("Discovery probe note after provision: %s", d_err)
        result["discovery"] = state.last_discovery

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
        if req.primary_cloud_provider.strip() and req.primary_cloud_provider != "Auto-Detect":
            env_lines.append(f'PRIMARY_CLOUD_PROVIDER="{req.primary_cloud_provider.strip()}"')
        if req.primary_cloud_region.strip():
            env_lines.append(f'AWS_DEFAULT_REGION="{req.primary_cloud_region.strip()}"')
        if _valid_cred(req.primary_cloud_access_id):
            env_lines.append(f'PRIMARY_CLOUD_ACCESS_ID="{req.primary_cloud_access_id.strip()}"')
        if _valid_cred(req.primary_cloud_secret_key):
            env_lines.append(f'PRIMARY_CLOUD_SECRET_KEY="{req.primary_cloud_secret_key.strip()}"')
        if req.secondary_cloud_provider.strip() and req.secondary_cloud_provider != "Auto-Detect":
            env_lines.append(f'SECONDARY_CLOUD_PROVIDER="{req.secondary_cloud_provider.strip()}"')
        if req.secondary_cloud_region.strip():
            env_lines.append(f'AZURE_LOCATION="{req.secondary_cloud_region.strip()}"')
        if _valid_cred(req.secondary_cloud_access_id):
            env_lines.append(f'AZURE_SUBSCRIPTION_ID="{req.secondary_cloud_access_id.strip()}"')
        if _valid_cred(req.secondary_cloud_secret_key):
            env_lines.append(f'ARM_BEARER_TOKEN="{req.secondary_cloud_secret_key.strip()}"')
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

        aws_running = [
            i for i in ((state.last_discovery.get("aws") or {}).get("instances") or []) if i.get("state") == "running"
        ]
        state.add_log(
            source="discovery",
            account="SYSTEM",
            message=f"🔍 Initial Cloud Scan Complete: {len(aws_running)} Running Compute Instance(s) discovered on Primary Cloud",
            level="INFO",
        )

        state.add_log(
            source="onboarding",
            account="SYSTEM",
            message=f"🎉 Zero-Touch Multi-Cloud DR Linked: {req.primary_account} <-> {req.secondary_account} (Protected DB={req.database_name})",
            level="SUCCESS",
        )
        state.ui_connected = True
        try:
            import json as _json

            from .state import REPORTS_DIR

            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            (REPORTS_DIR / "ui_connected.json").write_text(_json.dumps({"connected": True}), encoding="utf-8")
        except Exception:
            pass
        state.trigger_immediate_probe()
        return result
    except Exception as e:
        logger.exception("Onboarding provisioning failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

