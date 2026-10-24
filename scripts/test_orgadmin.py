import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
runner = conn.SnowflakeSqlRunner(20)

print("--- TESTING ORGADMIN ACCESS ---")
try:
    res = runner.run(s.primary, [
        "USE ROLE ORGADMIN",
        "SHOW REPLICATION ACCOUNTS"
    ])
    print("Replication accounts count:", len(res[1]))
    for r in res[1]:
        print("  Row:", r)
except Exception as e:
    print("Error:", e)
