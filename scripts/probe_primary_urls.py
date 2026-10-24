"""Compare reachability of SF_AWS_PRIMARY via org-name URL vs locator URL (key-pair auth)."""
import snowflake.connector

for acct in ["NNFCDXY-SF_AWS_PRIMARY", "nnfcdxy-sf-aws-primary", "awc63551"]:
    try:
        c = snowflake.connector.connect(
            account=acct,
            user="YASHSNOW20",
            authenticator="SNOWFLAKE_JWT",
            private_key_file="C:/CSPM_PROJECT/rsa_key.p8",
            role="ACCOUNTADMIN",
            login_timeout=20,
        )
        print("[OK]", acct, c.cursor().execute("SELECT CURRENT_ACCOUNT_NAME(), CURRENT_REGION()").fetchall())
        c.close()
    except Exception as e:
        print("[ERR]", acct, str(e)[:140])
