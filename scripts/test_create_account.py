import re
from pathlib import Path
import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
runner = conn.SnowflakeSqlRunner(60)

pubkey_text = Path("C:/CSPM_PROJECT/rsa_key.pub").read_text()
# extract base64 lines
lines = [l.strip() for l in pubkey_text.splitlines() if "KEY" not in l and l.strip()]
pubkey = "".join(lines)
print(f"Extracted pubkey (len {len(pubkey)}): {pubkey[:20]}...{pubkey[-20:]}")

email = "yashvardhankhanna360@gmail.com"

create_sql = f"""
CREATE ACCOUNT SF_AZURE_DR
  ADMIN_NAME = YASHSNOW20
  ADMIN_PASSWORD = 'Atlas20@200605'
  EMAIL = '{email}'
  EDITION = BUSINESS_CRITICAL
  REGION = 'azure_eastus2'
"""

print("Running CREATE ACCOUNT SF_AZURE_DR...")
try:
    res = runner.run(s.primary, [
        "USE ROLE ORGADMIN",
        create_sql
    ])
    print("SUCCESS creating SF_AZURE_DR:", res)
except Exception as e:
    print("Error:", e)
