import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
runner = conn.SnowflakeSqlRunner(20)

print("--- RESETTING PASSWORD FOR SECONDARY (AZURE) ---")
sql_commands = [
    "ALTER USER YASHSNOW20 UNSET TYPE",
    "ALTER USER YASHSNOW20 SET PASSWORD = 'Atlas20@200605' MUST_CHANGE_PASSWORD = FALSE",
]

for cmd in sql_commands:
    try:
        res = runner.run(s.secondary, [cmd])
        print(f"[OK] Secondary: {cmd} -> {res}")
    except Exception as e:
        print(f"[ERR] Secondary: {cmd} -> {e}")

print("\nVerifying user status on Secondary...")
try:
    desc = runner.run(s.secondary, ["DESC USER YASHSNOW20"])
    for row in desc[0]:
        if row[0] in ("TYPE", "HAS_PASSWORD", "PASSWORD_LAST_SET_TIME", "MUST_CHANGE_PASSWORD"):
            print(f"  {row[0]}: {row[1]}")
except Exception as e:
    print("Desc error:", e)

