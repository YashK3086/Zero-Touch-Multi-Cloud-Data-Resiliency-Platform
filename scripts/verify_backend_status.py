"""Direct Backend Disaster Recovery Inspector.

Queries both Snowflake cloud accounts and the global Anycast redirect connection
to show exactly which cloud is PRIMARY, which is REPLICA, and where traffic lands.
"""

from __future__ import annotations

import sys
import snowflake.connector
from sf_dr_controller.config import Settings

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _connect_account(account_cfg, use_warehouse: bool = False):
    kwargs = {
        "account": account_cfg.identifier,
        "user": account_cfg.user,
        "role": account_cfg.role,
        "login_timeout": 20,
        "network_timeout": 30,
    }
    if use_warehouse and account_cfg.warehouse:
        kwargs["warehouse"] = account_cfg.warehouse
    if account_cfg.private_key_path:
        kwargs["authenticator"] = "SNOWFLAKE_JWT"
        kwargs["private_key_file"] = str(account_cfg.private_key_path)
    elif account_cfg.password:
        kwargs["password"] = account_cfg.password
    return snowflake.connector.connect(**kwargs)


def _query_dicts(cur, sql_text: str) -> tuple[str | None, list[dict]]:
    cur.execute(sql_text)
    sfqid = getattr(cur, "sfqid", None)
    if not cur.description:
        return sfqid, []
    cols = [c[0].lower() for c in cur.description]
    return sfqid, [dict(zip(cols, row)) for row in cur.fetchall()]


def inspect_backend() -> None:
    settings = Settings()

    print("=" * 84)
    print(" >>> LIVE SNOWFLAKE MULTI-CLOUD BACKEND INSPECTOR <<<")
    print("=" * 84)

    # 1. Anycast Global Redirect URL Probe
    print("\n[1] ANYCAST GLOBAL REDIRECT URL PROBE:")
    global_url = f"{settings.snowflake_account_primary.split('-')[0].lower()}-{settings.snowflake_redirect_connection_name.lower()}.snowflakecomputing.com"
    try:
        conn = snowflake.connector.connect(
            host=global_url,
            account=settings.snowflake_account_primary,
            user=settings.snowflake_user,
            authenticator="SNOWFLAKE_JWT" if settings.snowflake_private_key_path else "snowflake",
            private_key_file=str(settings.snowflake_private_key_path) if settings.snowflake_private_key_path else None,
            password=settings.snowflake_password.get_secret_value() if (not settings.snowflake_private_key_path and settings.snowflake_password) else None,
            role="ACCOUNTADMIN",
            login_timeout=15,
        )
        cur = conn.cursor()
        cur.execute("SELECT CURRENT_ACCOUNT(), CURRENT_REGION(), CURRENT_ROLE()")
        sfqid = getattr(cur, "sfqid", "")
        act, reg, rol = cur.fetchone()
        conn.close()

        cloud_name = "AWS US-East-1 (SF_AWS_PRIMARY)" if "AWS" in reg else "AZURE EastUS-2 (SF_AZURE_DR)"
        print(f"  * Global URL     : {global_url}")
        print(f"  * Landed On      : Locator [{act}] | Region [{reg}] | Role [{rol}]")
        print(f"  * Query ID       : {sfqid}")
        print(f"  * Active Target  : ==> [ {cloud_name} ] <==")
    except Exception as e:
        print(f"  * Global URL probe error: {e}")

    # 2 & 3. Probe each cloud account directly
    for idx, (title, acct_cfg) in enumerate(
        [
            ("AWS ACCOUNT", settings.primary),
            ("AZURE ACCOUNT", settings.secondary),
        ],
        start=2,
    ):
        acct_short = acct_cfg.identifier.split("-", 1)[1].upper()
        print(f"\n[{idx}] {title} ({acct_cfg.identifier}):")
        try:
            conn = _connect_account(acct_cfg, use_warehouse=False)
            cur = conn.cursor()

            _, fg_rows = _query_dicts(cur, f"SHOW FAILOVER GROUPS LIKE '{settings.snowflake_failover_group_name}'")
            my_fg = next((r for r in fg_rows if str(r.get("account_name", "")).upper() == acct_short), {})
            fg_primary = str(my_fg.get("is_primary", "")).lower() == "true"

            _, cn_rows = _query_dicts(cur, f"SHOW CONNECTIONS LIKE '{settings.snowflake_redirect_connection_name}'")
            my_cn = next((r for r in cn_rows if str(r.get("account_name", "")).upper() == acct_short), {})
            cn_primary = str(my_cn.get("is_primary", "")).lower() == "true"

            _, rm_rows = _query_dicts(cur, "SHOW RESOURCE MONITORS LIKE 'DR_CREDIT_GUARD'")
            rm = rm_rows[0] if rm_rows else {}

            cnt_qid, cnt_rows = _query_dicts(
                cur, "SELECT COUNT(*) AS cnt FROM SF_DR_DEMO_DB.DR_STAGING.FINANCIAL_TRANSACTIONS"
            )
            cnt = int(cnt_rows[0]["cnt"]) if cnt_rows else 0
            conn.close()

            print(
                f"  * Locator / Region    : {my_fg.get('account_locator', 'N/A')} ({my_fg.get('snowflake_region', 'N/A')})"
            )
            print(
                f"  * Failover Group Role : {'[PRIMARY - Authoritative Read-Write]' if fg_primary else '[SECONDARY - Read-Only Replica]'}"
            )
            print(
                f"  * Client Redirect DNS : {'[ACTIVE LEADER - Receiving Global Traffic]' if cn_primary else '[STANDBY TARGET]'}"
            )
            print(f"  * PaySim Table Rows   : {cnt:,} rows (sfqid={cnt_qid})")
            print(
                f"  * Credit Guard Burn   : {rm.get('used_credits', '0.00')} / {rm.get('credit_quota', '10.00')} credits"
            )
        except Exception as e:
            print(f"  * {title} query error: {e}")

    print("\n" + "=" * 84)


if __name__ == "__main__":
    inspect_backend()
