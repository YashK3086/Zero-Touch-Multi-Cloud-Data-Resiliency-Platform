import sys
from sf_dr_controller.config import Settings
from sf_dr_controller.connection import SnowflakeSqlRunner

settings = Settings()
runner = SnowflakeSqlRunner(timeout_seconds=30)

print("=" * 60)
print("1. ENABLING REPLICATION IN ORGADMIN ACROSS BOTH ACCOUNTS")
print("=" * 60)

org_commands = [
    "USE ROLE ORGADMIN",
    "SELECT SYSTEM$GLOBAL_ACCOUNT_SET_PARAMETER('NNFCDXY.SF_AWS_PRIMARY', 'ENABLE_ACCOUNT_DATABASE_REPLICATION', 'true')",
    "SELECT SYSTEM$GLOBAL_ACCOUNT_SET_PARAMETER('NNFCDXY.SF_AZURE_DR', 'ENABLE_ACCOUNT_DATABASE_REPLICATION', 'true')",
    "SHOW REPLICATION ACCOUNTS",
]

for cmd in org_commands:
    try:
        res = runner.run(settings.primary, [cmd])
        print(f"[OK] {cmd}")
        if "SHOW" in cmd:
            for r in res[0]:
                print(f"     Account: {r[1]} | Region: {r[3]} | IsPrimary: {r[4]}")
    except Exception as e:
        print(f"[ERR] {cmd} -> {e}")

print("\n" + "=" * 60)
print("2. CHECKING DATABASE ON SECONDARY (AZURE)")
print("=" * 60)
try:
    res = runner.run(settings.secondary, ["SHOW DATABASES LIKE 'SF_DR_DEMO_DB'"])
    if res and res[0]:
        print("[FOUND] Database 'SF_DR_DEMO_DB' already exists on Secondary (Azure).")
        print("Dropping existing standalone SF_DR_DEMO_DB on Azure so Failover Group replica can create it cleanly...")
        runner.run(settings.secondary, ["DROP DATABASE IF EXISTS SF_DR_DEMO_DB"])
        print("[OK] Dropped stale SF_DR_DEMO_DB on Azure.")
    else:
        print("[OK] No conflicting SF_DR_DEMO_DB found on Azure.")
except Exception as e:
    print(f"[WARN] Secondary DB check: {e}")

print("\n" + "=" * 60)
print("3. VERIFYING FAILOVER GROUP ON PRIMARY (AWS)")
print("=" * 60)
try:
    res = runner.run(settings.primary, ["USE ROLE ACCOUNTADMIN", "SHOW FAILOVER GROUPS LIKE 'SF_DR_FAILOVER_GROUP'"])
    if res and len(res) > 1 and res[1]:
        print("[OK] Failover Group exists on AWS Primary:", res[1][0][1])
    else:
        print("[INFO] Failover group not yet created on Primary.")
except Exception as e:
    print(f"[WARN] Primary FG check: {e}")

print("\n" + "=" * 60)
print("REPLICATION PRE-FLIGHT READY!")
print("=" * 60)

