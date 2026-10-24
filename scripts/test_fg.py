import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
runner = conn.SnowflakeSqlRunner(20)

print("--- TESTING REPLICATION & FAILOVER GROUP CAPABILITY ---")
try:
    res = runner.run(s.primary, [
        "USE ROLE ACCOUNTADMIN",
        "SHOW FAILOVER GROUPS"
    ])
    print("SHOW FAILOVER GROUPS: SUCCESS ->", res[1])
except Exception as e:
    print("FAILOVER GROUPS error:", e)
