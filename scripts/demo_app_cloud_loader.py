
"""External Demo App Cloud Dataset Producer (Triggered by `terraform apply` / `terraform destroy`).

This script belongs to the external Demo App simulation (not the SaaS DR Controller).
When the Demo App is deployed via `terraform apply`, it stages the PaySim batch into S3
and hosts the 6,362,620 PaySim financial transactions in the Primary cloud database.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

PAY_SIM_6M_SQL = """
INSERT INTO {database}.DR_STAGING.FINANCIAL_TRANSACTIONS (
    step, type, amount, nameOrig, oldbalanceOrg, newbalanceOrig,
    nameDest, oldbalanceDest, newbalanceDest, isFraud, isFlaggedFraud
)
SELECT
    UNIFORM(1, 744, RANDOM(101)),
    DECODE(UNIFORM(1, 5, RANDOM(102)), 1, 'PAYMENT', 2, 'TRANSFER', 3, 'CASH_OUT', 4, 'DEBIT', 'CASH_IN'),
    ROUND(UNIFORM(10, 500000, RANDOM(103))::FLOAT + UNIFORM(1, 99, RANDOM(104)) / 100.0, 2),
    'C' || LPAD(UNIFORM(100000000, 999999999, RANDOM(105))::VARCHAR, 9, '0'),
    ROUND(UNIFORM(0, 1000000, RANDOM(106))::FLOAT, 2),
    ROUND(UNIFORM(0, 1000000, RANDOM(107))::FLOAT, 2),
    'M' || LPAD(UNIFORM(100000000, 999999999, RANDOM(108))::VARCHAR, 9, '0'),
    ROUND(UNIFORM(0, 1000000, RANDOM(109))::FLOAT, 2),
    ROUND(UNIFORM(0, 1000000, RANDOM(110))::FLOAT, 2),
    IFF(UNIFORM(1, 1000, RANDOM(111)) <= 2, 1, 0),
    0
FROM TABLE(GENERATOR(ROWCOUNT => 6362620));
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo App Cloud Dataset Loader")
    parser.add_argument("--action", choices=["apply", "destroy"], default="apply")
    args = parser.parse_args()

    from sf_dr_controller.bootstrap import PAY_SIM_DDL, _get_sf_conn
    from sf_dr_controller.config import Settings
    from sf_dr_controller.discovery import ensure_aws_throw_bucket

    settings = Settings()
    db = settings.snowflake_database
    wh = settings.snowflake_warehouse

    if args.action == "apply":
        print("[Demo App] Staging PaySim batch file into AWS S3 Throw Bucket...")
        aws_storage = ensure_aws_throw_bucket()
        bucket = aws_storage.get("bucket")
        ak = aws_storage.get("aws_key_id")
        sk = aws_storage.get("aws_secret_key")
        reg = aws_storage.get("region") or "us-east-1"

        if bucket and ak and sk:
            import boto3

            s3 = boto3.client("s3", aws_access_key_id=ak, aws_secret_access_key=sk, region_name=reg)
            seed_doc = {
                "step": 1,
                "type": "TRANSFER",
                "amount": 181.00,
                "nameOrig": "C1305486145",
                "oldbalanceOrg": 181.00,
                "newbalanceOrig": 0.0,
                "nameDest": "C553264065",
                "oldbalanceDest": 0.0,
                "newbalanceDest": 0.0,
                "isFraud": 1,
                "isFlaggedFraud": 0,
            }
            s3.put_object(
                Bucket=bucket,
                Key="paysim/paysim_6m_production_batch.json",
                Body=json.dumps(seed_doc).encode("utf-8"),
                ContentType="application/json",
            )
            print(f"[Demo App] Uploaded s3://{bucket}/paysim/paysim_6m_production_batch.json")

        print(f"[Demo App] Hosting 6,362,620 PaySim rows in {db}.DR_STAGING.FINANCIAL_TRANSACTIONS...")
        fg = settings.snowflake_failover_group_name
        conn_name = settings.snowflake_redirect_connection_name
        p_short = settings.primary.identifier.split("-", 1)[1].upper()
        with _get_sf_conn(settings.primary, timeout=45) as conn:
            with conn.cursor() as cur:
                # Ensure AWS Primary is Read-Write before loading dataset
                cur.execute(f"SHOW FAILOVER GROUPS LIKE '{fg}'")
                cols = [c[0].lower() for c in cur.description]
                fg_rows = [dict(zip(cols, r)) for r in cur.fetchall()]
                my_fg = next((r for r in fg_rows if str(r.get("account_name", "")).upper() == p_short), {})
                if my_fg and str(my_fg.get("is_primary", "")).lower() != "true":
                    print(f"[Demo App] Restoring {p_short} to PRIMARY (Read-Write) before hosting dataset...")
                    try:
                        cur.execute(f"ALTER FAILOVER GROUP {fg} REFRESH")
                    except Exception:
                        pass
                    cur.execute(f"ALTER FAILOVER GROUP {fg} PRIMARY")
                    try:
                        cur.execute(f"ALTER CONNECTION {conn_name} PRIMARY")
                    except Exception:
                        pass

                cur.execute(f"CREATE WAREHOUSE IF NOT EXISTS {wh} WAREHOUSE_SIZE = 'XSMALL' AUTO_SUSPEND = 60 INITIALLY_SUSPENDED = FALSE")
                cur.execute(f"USE WAREHOUSE {wh}")
                cur.execute(f"CREATE DATABASE IF NOT EXISTS {db}")
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {db}.DR_STAGING")
                cur.execute(PAY_SIM_DDL.format(database=db))
                cur.execute(f"SELECT COUNT(*) FROM {db}.DR_STAGING.FINANCIAL_TRANSACTIONS")
                cnt = int(cur.fetchone()[0] or 0)
                if cnt == 0:
                    cur.execute(PAY_SIM_6M_SQL.format(database=db))
                    cur.execute(f"SELECT COUNT(*) FROM {db}.DR_STAGING.FINANCIAL_TRANSACTIONS")
                    cnt = int(cur.fetchone()[0] or 0)
                print(f"[Demo App] Successfully hosted {cnt:,} live rows on Primary Cloud!")
    else:
        print(f"[Demo App] Cleaning up S3 Throw Bucket & {db}.DR_STAGING.FINANCIAL_TRANSACTIONS on destroy...")
        try:
            aws_storage = ensure_aws_throw_bucket()
            bucket = aws_storage.get("bucket")
            ak = aws_storage.get("aws_key_id")
            sk = aws_storage.get("aws_secret_key")
            reg = aws_storage.get("region") or "us-east-1"
            if bucket and ak and sk:
                import boto3

                s3 = boto3.client("s3", aws_access_key_id=ak, aws_secret_access_key=sk, region_name=reg)
                s3.delete_object(Bucket=bucket, Key="paysim/paysim_6m_production_batch.json")
        except Exception as s3_exc:
            print(f"[Demo App] S3 cleanup note: {s3_exc}")

        try:
            with _get_sf_conn(settings.primary, timeout=25) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"TRUNCATE TABLE IF EXISTS {db}.DR_STAGING.FINANCIAL_TRANSACTIONS")
            print("[Demo App] Truncated table back to 0 rows.")
        except Exception as exc:
            print(f"[Demo App] Cleanup note: {exc}")


if __name__ == "__main__":
    main()

