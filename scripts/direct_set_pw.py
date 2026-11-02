from sf_dr_controller.config import Settings
from sf_dr_controller.connection import SnowflakeSqlRunner

settings = Settings()
runner = SnowflakeSqlRunner(timeout_seconds=20)

print("--- EXPLICITLY SETTING PASSWORD ON AZURE SECONDARY ---")
try:
    res = runner.run(settings.secondary, [
        "USE ROLE ACCOUNTADMIN",
        "ALTER USER YASHSNOW20 SET PASSWORD = 'SecurePassword123!' MUST_CHANGE_PASSWORD = FALSE"
    ])
    print("[SUCCESS] Password successfully set on Azure Secondary:", res)
except Exception as e:
    print("[ERROR] Setting password:", e)

try:
    desc = runner.run(settings.secondary, ["DESC USER YASHSNOW20"])
    for row in desc[0]:
        if row[0] in ("NAME", "LOGIN_NAME", "HAS_PASSWORD", "MUST_CHANGE_PASSWORD"):
            print(f"  {row[0]}: {row[1]}")
except Exception as e:
    print("Desc error:", e)

