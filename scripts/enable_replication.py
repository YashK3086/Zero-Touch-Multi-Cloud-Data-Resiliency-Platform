import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
runner = conn.SnowflakeSqlRunner(20)

print("--- ENABLING REPLICATION IN ORG ---")
commands = [
    "USE ROLE ORGADMIN",
    "SELECT SYSTEM$GLOBAL_ACCOUNT_SET_PARAMETER('NNFCDXY.OZ10928', 'ENABLE_ACCOUNT_DATABASE_REPLICATION', 'true')",
    "SELECT SYSTEM$GLOBAL_ACCOUNT_SET_PARAMETER('NNFCDXY.SF_AZURE_DR', 'ENABLE_ACCOUNT_DATABASE_REPLICATION', 'true')",
    "SHOW REPLICATION ACCOUNTS"
]
for cmd in commands:
    try:
        res = runner.run(s.primary, [cmd])
        print(f"[OK] {cmd} -> {res}")
    except Exception as e:
        print(f"[ERR] {cmd} -> {e}")
