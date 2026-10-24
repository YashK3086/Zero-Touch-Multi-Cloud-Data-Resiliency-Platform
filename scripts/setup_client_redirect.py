"""Set up Client Redirect connection across AWS and Azure accounts."""
import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
r = conn.SnowflakeSqlRunner(60)

sec_id = s.secondary.identifier.replace("-", ".")
prim_id = s.primary.identifier.replace("-", ".")

print("--- 1. Creating Primary Connection SF_DR_GLOBAL_REDIRECT on AWS ---")
prim_conn_sql = f"""
CREATE CONNECTION IF NOT EXISTS {s.snowflake_redirect_connection_name}
  ENABLE FAILOVER TO ACCOUNTS {sec_id}
  COMMENT = 'Global multi-cloud client redirect connection'
"""
try:
    res = r.run(s.primary, [prim_conn_sql])
    print("[Primary OK] Create Connection:", res)
except Exception as e:
    print("[Primary ERR] Create Connection:", e)

print("\n--- 2. Creating Secondary Replica Connection on Azure ---")
sec_conn_sql = f"""
CREATE CONNECTION IF NOT EXISTS {s.snowflake_redirect_connection_name}
  AS REPLICA OF {prim_id}.{s.snowflake_redirect_connection_name}
  COMMENT = 'Secondary replica for global client redirect'
"""
try:
    res = r.run(s.secondary, [sec_conn_sql])
    print("[Secondary OK] Create Replica Connection:", res)
except Exception as e:
    print("[Secondary ERR] Create Replica Connection:", e)

print("\n--- 3. Showing Connections on Primary and Secondary ---")
try:
    print("Primary connections:", r.run(s.primary, ["SHOW CONNECTIONS"]))
    print("Secondary connections:", r.run(s.secondary, ["SHOW CONNECTIONS"]))
except Exception as e:
    print("Show connections error:", e)
