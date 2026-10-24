import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
runner = conn.SnowflakeSqlRunner(20)

print("--- ORG REPLICATION STATUS ---")
try:
    res = runner.run(s.primary, [
        "USE ROLE ORGADMIN",
        "SHOW REPLICATION ACCOUNTS"
    ])
    for r in res[1]:
        print(f"Replication Account: {r[0]} | Org: {r[1]} | Region: {r[2]} | Edition: {r[3]} | Failover Allowed: {r[4]}")
except Exception as e:
    print("Error:", e)
