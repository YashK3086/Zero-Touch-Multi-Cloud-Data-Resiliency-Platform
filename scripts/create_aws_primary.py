"""Create the Business Critical AWS primary account with the RSA key pre-attached."""
from pathlib import Path

import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
r = conn.SnowflakeSqlRunner(60)

body = "".join(
    l.strip() for l in Path("C:/CSPM_PROJECT/rsa_key.pub").read_text().splitlines()
    if "KEY" not in l and l.strip()
)

create_sql = f"""
CREATE ACCOUNT SF_AWS_PRIMARY
  ADMIN_NAME = YASHSNOW20
  ADMIN_RSA_PUBLIC_KEY = '{body}'
  ADMIN_USER_TYPE = SERVICE
  EMAIL = 'yashvardhankhanna360@gmail.com'
  EDITION = BUSINESS_CRITICAL
  REGION = 'AWS_US_EAST_1'
"""

for st in [
    "USE ROLE ORGADMIN",
    create_sql,
    "SELECT SYSTEM$GLOBAL_ACCOUNT_SET_PARAMETER('NNFCDXY.SF_AWS_PRIMARY', 'ENABLE_ACCOUNT_DATABASE_REPLICATION', 'true')",
]:
    try:
        print("[OK]", st.strip()[:50], "->", r.run(s.primary, [st]))
    except Exception as e:
        print("[ERR]", st.strip()[:50], "->", e)
