import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
runner = conn.SnowflakeSqlRunner(20)

print("--- PRIMARY CURRENT ROLE & DETAILS ---")
res = runner.run(s.primary, [
    "SELECT CURRENT_ROLE(), CURRENT_USER()",
    "SHOW GRANTS TO USER YASHSNOW20"
])
print("Role & User:", res[0][0])
print("Grants:")
for g in res[1]:
    print("  ", g[1], "granted to", g[2], "role:", g[0])
