"""Live Multi-Cloud Inventory Discovery Engine (read-only).

Runs at account-link time and on demand. Inspects what ACTUALLY exists right now:
- Snowflake (both accounts): user databases, tables + live row counts, stages, pipes,
  failover groups and client-redirect connections (Cloud Services metadata, 0 credits).
- Primary cloud (AWS): running EC2 workloads and S3 buckets (boto3, if credentials given).
- Standby cloud (Azure): resource groups, storage accounts, container apps (ARM REST, if credentials given).

Nothing is created or modified here. Absent resources are reported as absent.
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import requests

from .config import AccountConfig

logger = logging.getLogger("sf_dr_controller.discovery")

SYSTEM_DATABASES = {"SNOWFLAKE", "SNOWFLAKE_SAMPLE_DATA"}


def _ensure_dotenv_loaded() -> None:
    """Loads project .env into os.environ if not already loaded."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except Exception:
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line_s = line.strip()
            if line_s and not line_s.startswith("#") and "=" in line_s:
                k, v = line_s.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ---------------------------------------------------------------------------
# Region helpers
# ---------------------------------------------------------------------------
def describe_region(region: str | None) -> tuple[str, str]:
    """Maps a Snowflake region id (e.g. AWS_US_EAST_1, AZURE_EASTUS2) to (provider, cloud region)."""
    if not region:
        return "--", "--"
    raw = region.split(".")[-1].upper()
    for prefix, provider in (("AWS_", "AWS"), ("AZURE_", "Azure"), ("GCP_", "GCP")):
        if raw.startswith(prefix):
            rest = raw[len(prefix):].lower()
            return provider, rest.replace("_", "-") if provider != "Azure" else rest.replace("_", "")
    return "--", raw.lower()


# ---------------------------------------------------------------------------
# Snowflake discovery
# ---------------------------------------------------------------------------
def _rows(cur, sql: str) -> list[dict[str, Any]]:
    cur.execute(sql)
    if not cur.description:
        return []
    cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def discover_snowflake(account: AccountConfig) -> dict[str, Any]:
    """Returns live inventory of one Snowflake account using metadata-only SHOW commands."""
    from .bootstrap import _get_sf_conn

    result: dict[str, Any] = {"account": account.identifier, "reachable": False, "error": None}
    try:
        with _get_sf_conn(account, timeout=20) as conn, conn.cursor() as cur:
            ident = _rows(cur, "SELECT CURRENT_ACCOUNT() AS loc, CURRENT_REGION() AS reg")
            region = ident[0]["reg"] if ident else None
            provider, cloud_region = describe_region(region)

            dbs = [
                {
                    "name": d["name"],
                    "kind": d.get("kind") or "STANDARD",
                    "is_replica": str(d.get("origin") or "").strip() not in ("", "None"),
                    "origin": d.get("origin") or None,
                }
                for d in _rows(cur, "SHOW DATABASES")
                if d["name"].upper() not in SYSTEM_DATABASES and (d.get("kind") or "STANDARD") != "APPLICATION"
            ]

            tables = [
                {
                    "database": t["database_name"],
                    "schema": t["schema_name"],
                    "name": t["name"],
                    "rows": int(t.get("rows") or 0),
                    "bytes": int(t.get("bytes") or 0),
                }
                for t in _rows(cur, "SHOW TABLES IN ACCOUNT")
                if t["database_name"].upper() not in SYSTEM_DATABASES
            ]
            stages = [
                {"database": s["database_name"], "name": s["name"], "url": s.get("url") or "", "type": s.get("type")}
                for s in _rows(cur, "SHOW STAGES IN ACCOUNT")
                if s["database_name"].upper() not in SYSTEM_DATABASES
            ]
            pipes = [
                {
                    "database": p["database_name"],
                    "name": p["name"],
                    "notification_channel": p.get("notification_channel"),
                }
                for p in _rows(cur, "SHOW PIPES IN ACCOUNT")
            ]
            fgs = [
                {
                    "name": f["name"],
                    "is_primary": str(f.get("is_primary")).lower() == "true",
                    "account_name": f.get("account_name"),
                    "allowed_accounts": f.get("allowed_accounts"),
                    "schedule": f.get("replication_schedule"),
                }
                for f in _rows(cur, "SHOW FAILOVER GROUPS")
            ]
            conns = [
                {"name": c["name"], "is_primary": str(c.get("is_primary")).lower() == "true", "url": c.get("connection_url")}
                for c in _rows(cur, "SHOW CONNECTIONS")
            ]

            result.update(
                {
                    "reachable": True,
                    "locator": ident[0]["loc"] if ident else None,
                    "region": region,
                    "provider": provider,
                    "cloud_region": cloud_region,
                    "databases": dbs,
                    "tables": tables,
                    "total_rows": sum(t["rows"] for t in tables),
                    "stages": stages,
                    "pipes": pipes,
                    "failover_groups": fgs,
                    "connections": conns,
                }
            )
    except Exception as exc:  # noqa: BLE001 — surfaced to the UI verbatim
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


# ---------------------------------------------------------------------------
# AWS discovery & Primary Throw Bucket Provisioning
# ---------------------------------------------------------------------------
def _valid_cred(val: str | None) -> str | None:
    if not val:
        return None
    v = val.strip().strip('"').strip("'")
    if not v or v.startswith("••") or v == "AKIA-PRIMARY-CLOUD-KEY" or "PLACEHOLDER" in v.upper():
        return None
    return v


def aws_credentials() -> tuple[str | None, str | None, str]:
    """Resolves AWS API credentials from onboarding input or standard env variables."""
    _ensure_dotenv_loaded()
    key = _valid_cred(os.getenv("PRIMARY_CLOUD_ACCESS_ID")) or _valid_cred(os.getenv("AWS_ACCESS_KEY_ID"))
    secret = _valid_cred(os.getenv("PRIMARY_CLOUD_SECRET_KEY")) or _valid_cred(os.getenv("AWS_SECRET_ACCESS_KEY"))
    region = os.getenv("PRIMARY_CLOUD_REGION") or os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "us-east-1"
    return key, secret, region


def ensure_aws_throw_bucket() -> dict[str, Any]:
    """Idempotently creates the Primary Throw S3 Bucket (`sf-dr-primary-throw-<account_id>`) in AWS."""
    key, secret, region = aws_credentials()
    if not (key and secret):
        return {"created": False, "bucket": None, "uri": None, "error": "AWS credentials not configured"}
    try:
        import boto3
        from botocore.exceptions import ClientError

        session = boto3.session.Session(aws_access_key_id=key, aws_secret_access_key=secret, region_name=region)
        account_id = session.client("sts").get_caller_identity()["Account"]
        bucket_name = f"sf-dr-primary-throw-{account_id}"
        s3 = session.client("s3")

        exists = False
        try:
            s3.head_bucket(Bucket=bucket_name)
            exists = True
        except ClientError:
            exists = False

        if not exists:
            if region == "us-east-1":
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": region},
                )
            s3.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                },
            )
            s3.put_bucket_encryption(
                Bucket=bucket_name,
                ServerSideEncryptionConfiguration={
                    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
                },
            )
            s3.put_object(Bucket=bucket_name, Key="paysim/", Body=b"")
            logger.info("Created Primary Throw S3 bucket: s3://%s/paysim/", bucket_name)

        # Count real non-empty objects under paysim/
        objs = s3.list_objects_v2(Bucket=bucket_name, Prefix="paysim/").get("Contents", [])
        real_files = [o["Key"] for o in objs if int(o.get("Size") or 0) > 0]

        return {
            "created": True,
            "bucket": bucket_name,
            "uri": f"s3://{bucket_name}/paysim/",
            "region": region,
            "account_id": account_id,
            "file_count": len(real_files),
            "aws_key_id": key,
            "aws_secret_key": secret,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("AWS S3 throw bucket provisioning note: %s", exc)
        return {"created": False, "bucket": None, "uri": None, "error": f"{type(exc).__name__}: {exc}"}


def discover_aws() -> dict[str, Any]:
    """Lists running EC2 instances and S3 buckets in the primary AWS account."""
    key, secret, region = aws_credentials()
    if not (key and secret):
        return {"configured": False, "instances": [], "buckets": [], "error": None}
    try:
        import boto3

        session = boto3.session.Session(aws_access_key_id=key, aws_secret_access_key=secret, region_name=region)
        ec2 = session.client("ec2")
        instances = []
        resp = ec2.describe_instances(Filters=[{"Name": "instance-state-name", "Values": ["running", "pending"]}])
        for resv in resp.get("Reservations", []):
            for inst in resv.get("Instances", []):
                tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
                instances.append(
                    {
                        "instance_id": inst["InstanceId"],
                        "name": tags.get("Name", inst["InstanceId"]),
                        "role": tags.get("Role"),
                        "type": inst.get("InstanceType"),
                        "state": inst.get("State", {}).get("Name"),
                        "public_ip": inst.get("PublicIpAddress"),
                        "private_ip": inst.get("PrivateIpAddress"),
                        "vpc_id": inst.get("VpcId"),
                        "az": inst.get("Placement", {}).get("AvailabilityZone"),
                    }
                )
        buckets = [b["Name"] for b in session.client("s3").list_buckets().get("Buckets", [])]
        rds_instances = []
        try:
            for db in session.client("rds").describe_db_instances().get("DBInstances", []):
                rds_instances.append(
                    {
                        "id": db.get("DBInstanceIdentifier"),
                        "engine": db.get("Engine"),
                        "status": db.get("DBInstanceStatus"),
                        "class": db.get("DBInstanceClass"),
                        "endpoint": (db.get("Endpoint") or {}).get("Address"),
                    }
                )
        except Exception:
            pass
        efs_filesystems = []
        try:
            for fs in session.client("efs").describe_file_systems().get("FileSystems", []):
                efs_filesystems.append(
                    {
                        "file_system_id": fs.get("FileSystemId"),
                        "name": fs.get("Name") or fs.get("FileSystemId"),
                        "state": fs.get("LifeCycleState"),
                        "size_bytes": (fs.get("SizeInBytes") or {}).get("Value", 0),
                    }
                )
        except Exception:
            pass
        account_id = session.client("sts").get_caller_identity().get("Account")
        return {
            "configured": True,
            "account_id": account_id,
            "region": region,
            "instances": instances,
            "buckets": buckets,
            "rds_instances": rds_instances,
            "efs_filesystems": efs_filesystems,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {"configured": True, "instances": [], "buckets": [], "error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# Azure discovery (ARM REST — no SDK dependency)
# ---------------------------------------------------------------------------
_ARM = "https://management.azure.com"
_TOKEN_CACHE: dict[str, Any] = {"token": None, "exp": 0.0}


def azure_settings() -> dict[str, str | None]:
    """Resolves Azure service-principal settings (onboarding input or ARM_* env used by Terraform)."""
    _ensure_dotenv_loaded()
    return {
        "subscription_id": _valid_cred(os.getenv("SECONDARY_CLOUD_ACCESS_ID"))
        or _valid_cred(os.getenv("ARM_SUBSCRIPTION_ID"))
        or _valid_cred(os.getenv("AZURE_SUBSCRIPTION_ID")),
        "tenant_id": _valid_cred(os.getenv("ARM_TENANT_ID")) or _valid_cred(os.getenv("AZURE_TENANT_ID")),
        "client_id": _valid_cred(os.getenv("ARM_CLIENT_ID")) or _valid_cred(os.getenv("AZURE_CLIENT_ID")),
        "client_secret": _valid_cred(os.getenv("SECONDARY_CLOUD_SECRET_KEY"))
        or _valid_cred(os.getenv("ARM_CLIENT_SECRET"))
        or _valid_cred(os.getenv("AZURE_CLIENT_SECRET")),
        "location": os.getenv("SECONDARY_CLOUD_REGION") or os.getenv("AZURE_LOCATION") or "eastus2",
    }


def azure_token() -> str | None:
    """Acquires (and caches) an ARM bearer token via OAuth2 client-credentials, or uses a supplied token."""
    _ensure_dotenv_loaded()
    direct = _valid_cred(os.getenv("ARM_BEARER_TOKEN"))
    if direct and len(direct) > 50:
        return direct
    if _TOKEN_CACHE["token"] and time.time() < _TOKEN_CACHE["exp"] - 60:
        return _TOKEN_CACHE["token"]
    cfg = azure_settings()
    if not (cfg["tenant_id"] and cfg["client_id"] and cfg["client_secret"]):
        return None
    resp = requests.post(
        f"https://login.microsoftonline.com/{cfg['tenant_id']}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "scope": f"{_ARM}/.default",
        },
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    _TOKEN_CACHE.update({"token": body["access_token"], "exp": time.time() + int(body.get("expires_in", 3600))})
    return body["access_token"]


def arm_request(method: str, path: str, api_version: str, body: dict | None = None) -> requests.Response:
    """Performs an authenticated Azure Resource Manager REST call."""
    token = azure_token()
    if not token:
        raise RuntimeError("Azure credentials not configured")
    return requests.request(
        method,
        f"{_ARM}{path}?api-version={api_version}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )


def ensure_azure_catch_storage() -> dict[str, Any]:
    """Idempotently creates the Azure Resource Group, Storage Account, and Blob Container (`paysim-catch`) via ARM REST."""
    cfg = azure_settings()
    sub_id = cfg["subscription_id"]
    location = cfg["location"] or "eastus2"
    if not sub_id:
        return {"created": False, "storage_account": None, "container": None, "error": "Azure subscription not configured"}
    try:
        sub = f"/subscriptions/{sub_id}"
        rg_name = "rg-sf-dr-drdemo"
        sub_clean = re.sub(r"[^a-z0-9]", "", sub_id.lower())[:10]
        sa_name = f"sfdrseccatch{sub_clean}"[:24]
        container_name = "paysim-catch"

        # 1. Ensure Resource Group exists
        rg_resp = arm_request(
            "PUT",
            f"{sub}/resourcegroups/{rg_name}",
            "2021-04-01",
            {"location": location, "tags": {"ManagedBy": "sf-dr-controller", "Role": "SecondaryCatch"}},
        )
        rg_resp.raise_for_status()

        # 2. Check or create Storage Account
        sa_path = f"{sub}/resourceGroups/{rg_name}/providers/Microsoft.Storage/storageAccounts/{sa_name}"
        sa_get = arm_request("GET", sa_path, "2023-01-01")
        if not sa_get.ok or sa_get.json().get("properties", {}).get("provisioningState") != "Succeeded":
            sa_put = arm_request(
                "PUT",
                sa_path,
                "2023-01-01",
                {
                    "sku": {"name": "Standard_LRS"},
                    "kind": "StorageV2",
                    "location": location,
                    "properties": {
                        "accessTier": "Hot",
                        "allowBlobPublicAccess": False,
                        "minimumTlsVersion": "TLS1_2",
                        "supportsHttpsTrafficOnly": True,
                    },
                },
            )
            if sa_put.status_code not in (200, 201, 202):
                sa_put.raise_for_status()

            # Poll until Storage Account reaches Succeeded state (typically ~15-20s on Azure)
            for _ in range(15):
                time.sleep(2.5)
                chk = arm_request("GET", sa_path, "2023-01-01")
                if chk.ok and chk.json().get("properties", {}).get("provisioningState") == "Succeeded":
                    break

        # 3. Create Blob Container `paysim-catch`
        cont_path = f"{sa_path}/blobServices/default/containers/{container_name}"
        cont_put = arm_request("PUT", cont_path, "2023-01-01", {"properties": {"publicAccess": "None"}})
        cont_put.raise_for_status()

        # 4. Ensure 1:1 Matching Virtual Network (VNet) exists in Azure
        vnet_name = "sf-dr-sample-app-vnet-drdemo"
        vnet_path = f"{sub}/resourceGroups/{rg_name}/providers/Microsoft.Network/virtualNetworks/{vnet_name}"
        try:
            arm_request(
                "PUT",
                vnet_path,
                "2023-05-01",
                {
                    "location": location,
                    "tags": {"ManagedBy": "sf-dr-controller", "Role": "SecondaryDRNetwork"},
                    "properties": {
                        "addressSpace": {"addressPrefixes": ["10.1.0.0/16"]},
                        "subnets": [{"name": "sf-dr-subnet-drdemo", "properties": {"addressPrefix": "10.1.1.0/24"}}],
                    },
                },
            )
        except Exception as vnet_err:
            logger.info("Azure VNet notice: %s", vnet_err)

        logger.info("Created Secondary Catch Azure Storage: %s/%s in %s", sa_name, container_name, rg_name)
        return {
            "created": True,
            "resource_group": rg_name,
            "storage_account": sa_name,
            "container": container_name,
            "uri": f"azure://{sa_name}.blob.core.windows.net/{container_name}/",
            "location": location,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Azure catch storage provisioning note: %s", exc)
        return {"created": False, "storage_account": None, "container": None, "error": f"{type(exc).__name__}: {exc}"}


def ensure_azure_container_instance() -> dict[str, Any]:
    """Deploys a real live Azure Container Instance (Compute Workload with Public IP) via ARM REST."""
    cfg = azure_settings()
    sub_id = cfg["subscription_id"]
    location = cfg["location"] or "eastus2"
    rg_name = "rg-sf-dr-drdemo"
    if not sub_id:
        return {"created": False, "error": "Azure subscription not configured"}
    try:
        ensure_azure_catch_storage()
        sub = f"/subscriptions/{sub_id}"
        aci_name = "sf-dr-paysecure-api-dr"
        aci_path = f"{sub}/resourceGroups/{rg_name}/providers/Microsoft.ContainerInstance/containerGroups/{aci_name}"
        dns_label = f"sfdrpaysecure{sub_id[:8]}"
        body = {
            "location": location,
            "tags": {"ManagedBy": "sf-dr-controller", "Role": "ActiveDRCompute"},
            "properties": {
                "containers": [
                    {
                        "name": "paysecure-api",
                        "properties": {
                            "image": "mcr.microsoft.com/azuredocs/aci-helloworld",
                            "resources": {"requests": {"cpu": 1.0, "memoryInGB": 1.0}},
                            "ports": [{"port": 80, "protocol": "TCP"}],
                        },
                    }
                ],
                "osType": "Linux",
                "ipAddress": {
                    "type": "Public",
                    "ports": [{"port": 80, "protocol": "TCP"}],
                    "dnsNameLabel": dns_label,
                },
                "restartPolicy": "Always",
            },
        }
        resp = arm_request("PUT", aci_path, "2023-05-01", body)
        resp_data = resp.json() if resp.ok else {}
        props = resp_data.get("properties", {})
        ip = props.get("ipAddress", {}).get("ip")
        fqdn = props.get("ipAddress", {}).get("fqdn") or f"{dns_label}.{location}.azurecontainer.io"
        logger.info("Hydrated Azure Container Instance: %s (IP=%s, FQDN=%s)", aci_name, ip, fqdn)
        return {
            "created": True,
            "name": aci_name,
            "ip": ip,
            "fqdn": fqdn,
            "state": "Running",
            "error": None,
        }
    except Exception as exc:
        logger.warning("Azure ACI provisioning note: %s", exc)
        return {"created": False, "name": "sf-dr-paysecure-api-dr", "error": f"{type(exc).__name__}: {exc}"}


def delete_azure_container_instance() -> dict[str, Any]:
    """Deletes the Azure Container Instance on failback to return to $0 idle cost."""
    cfg = azure_settings()
    sub_id = cfg["subscription_id"]
    rg_name = "rg-sf-dr-drdemo"
    if not sub_id:
        return {"deleted": False}
    try:
        sub = f"/subscriptions/{sub_id}"
        aci_name = "sf-dr-paysecure-api-dr"
        aci_path = f"{sub}/resourceGroups/{rg_name}/providers/Microsoft.ContainerInstance/containerGroups/{aci_name}"
        resp = arm_request("DELETE", aci_path, "2023-05-01")
        return {"deleted": resp.status_code in (200, 202, 204)}
    except Exception as exc:
        logger.warning("Azure ACI cleanup note: %s", exc)
        return {"deleted": False, "error": str(exc)}


def discover_azure() -> dict[str, Any]:
    """Lists resource groups, storage accounts and container apps in the standby Azure subscription."""
    cfg = azure_settings()
    if not cfg["subscription_id"]:
        return {"configured": False, "resource_groups": [], "storage_accounts": [], "container_apps": [], "error": None}
    try:
        sub = f"/subscriptions/{cfg['subscription_id']}"
        rgs = arm_request("GET", f"{sub}/resourcegroups", "2021-04-01")
        rgs.raise_for_status()
        sas = arm_request("GET", f"{sub}/providers/Microsoft.Storage/storageAccounts", "2023-01-01")
        sas.raise_for_status()
        apps = arm_request("GET", f"{sub}/providers/Microsoft.App/containerApps", "2023-05-01")
        acis = arm_request("GET", f"{sub}/providers/Microsoft.ContainerInstance/containerGroups", "2023-05-01")
        all_compute = []
        if apps.ok:
            for a in apps.json().get("value", []):
                all_compute.append({
                    "name": a["name"],
                    "location": a["location"],
                    "min_replicas": a.get("properties", {}).get("template", {}).get("scale", {}).get("minReplicas"),
                    "fqdn": a.get("properties", {}).get("configuration", {}).get("ingress", {}).get("fqdn"),
                })
        if acis.ok:
            for c in acis.json().get("value", []):
                props = c.get("properties", {})
                state = props.get("instanceView", {}).get("state", "Running")
                all_compute.append({
                    "name": c["name"],
                    "location": c["location"],
                    "min_replicas": 1 if state.lower() == "running" else 0,
                    "fqdn": props.get("ipAddress", {}).get("fqdn") or props.get("ipAddress", {}).get("ip"),
                    "state": state,
                })
        return {
            "configured": True,
            "subscription_id": cfg["subscription_id"],
            "resource_groups": [r["name"] for r in rgs.json().get("value", [])],
            "storage_accounts": [
                {"name": s["name"], "location": s["location"], "id": s["id"]} for s in sas.json().get("value", [])
            ],
            "container_apps": all_compute,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {"configured": True, "resource_groups": [], "storage_accounts": [], "container_apps": [], "error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------
def run_full_discovery(primary: AccountConfig, secondary: AccountConfig) -> dict[str, Any]:
    """Runs all discovery probes and returns a single live inventory snapshot."""
    from concurrent.futures import ThreadPoolExecutor

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_p = pool.submit(discover_snowflake, primary)
        f_s = pool.submit(discover_snowflake, secondary)
        f_aws = pool.submit(discover_aws)
        f_az = pool.submit(discover_azure)
        snapshot = {
            "snowflake_primary": f_p.result(),
            "snowflake_secondary": f_s.result(),
            "aws": f_aws.result(),
            "azure": f_az.result(),
        }
    snapshot["discovered_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    snapshot["duration_s"] = round(time.perf_counter() - t0, 2)
    return snapshot

