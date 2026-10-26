from pathlib import Path
import snowflake.connector

pubkey_text = Path("C:/CSPM_PROJECT/rsa_key.pub").read_text()
lines = [l.strip() for l in pubkey_text.splitlines() if "KEY" not in l and l.strip()]
pubkey = "".join(lines)

print("Step 1: Connecting to new secondary account SF_AZURE_DR with password")
conn = snowflake.connector.connect(
    user="YASHSNOW20",
    password="Atlas20@200605",
    account="NNFCDXY-SF_AZURE_DR",
    role="ACCOUNTADMIN"
)

cur = conn.cursor()
print("Connected! Setting RSA public key for YASHSNOW20...")
cur.execute(f"ALTER USER YASHSNOW20 SET RSA_PUBLIC_KEY='{pubkey}'")
print("RSA_PUBLIC_KEY set successfully on SF_AZURE_DR!")

cur.execute("SELECT CURRENT_USER(), CURRENT_ACCOUNT(), CURRENT_ROLE()")
print("Current session:", cur.fetchall())

conn.close()
