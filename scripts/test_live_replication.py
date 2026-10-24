"""Test setting up Failover Group and executing live cross-cloud replication."""
import time
import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
r = conn.SnowflakeSqlRunner(60)

print("--- 1. Creating Failover Group on Primary (AWS) ---")
sec_id = s.secondary.identifier.replace("-", ".")
prim_id = s.primary.identifier.replace("-", ".")

primary_fg_sql = f"""
CREATE FAILOVER GROUP IF NOT EXISTS {s.snowflake_failover_group_name}
  OBJECT_TYPES = DATABASES
  ALLOWED_DATABASES = {s.snowflake_database}
  ALLOWED_ACCOUNTS = {sec_id}
  REPLICATION_SCHEDULE = '10 MINUTE'
"""
try:
    res = r.run(s.primary, [primary_fg_sql])
    print("[Primary OK] Create FG:", res)
except Exception as e:
    print("[Primary ERR] Create FG:", e)

print("\n--- 2. Creating Replica Failover Group on Secondary (Azure) ---")
secondary_fg_sql = f"""
CREATE FAILOVER GROUP IF NOT EXISTS {s.snowflake_failover_group_name}
  AS REPLICA OF {prim_id}.{s.snowflake_failover_group_name}
"""
try:
    res = r.run(s.secondary, [secondary_fg_sql])
    print("[Secondary OK] Create Replica FG:", res)
except Exception as e:
    print("[Secondary ERR] Create Replica FG:", e)

print("\n--- 3. Triggering initial refresh on Secondary ---")
try:
    res = r.run(s.secondary, [f"ALTER FAILOVER GROUP {s.snowflake_failover_group_name} REFRESH"])
    print("[Secondary OK] Initial refresh:", res)
except Exception as e:
    print("[Secondary ERR] Initial refresh:", e)

print("\n--- 4. Checking databases on Secondary ---")
try:
    dbs = r.run(s.secondary, ["SHOW DATABASES"])
    for row in dbs[0]:
        print("Secondary DB:", row[1], "| Origin:", row[4] if len(row) > 4 else "")
except Exception as e:
    print("[Secondary ERR] Show DBs:", e)
