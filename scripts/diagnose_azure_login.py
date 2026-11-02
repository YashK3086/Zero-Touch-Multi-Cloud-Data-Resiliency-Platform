from sf_dr_controller.config import Settings
from sf_dr_controller.connection import SnowflakeSqlRunner

settings = Settings()
runner = SnowflakeSqlRunner(timeout_seconds=20)

print("=" * 60)
print("INSPECTING USERS & AUTHENTICATION ON SECONDARY (AZURE)")
print("=" * 60)

try:
    # Query via RSA JWT connection which works 100%
    users = runner.run(settings.secondary, ["SHOW USERS", "SELECT CURRENT_USER(), CURRENT_ROLE()"])
    print("Connected successfully via RSA Key!")
    print("Current Session:", users[1])
    print("\nUsers on Azure Secondary:")
    for u in users[0]:
        name = u[0]
        login_name = u[1]
        has_pw = u[11] if len(u) > 11 else "N/A"
        print(f" - Name: {name} | Login Name: {login_name} | Has Password: {has_pw}")
        
    print("\nFetching exact description for YASHSNOW20...")
    desc = runner.run(settings.secondary, ["DESC USER YASHSNOW20"])
    for row in desc[0]:
        prop = row[0]
        val = row[1]
        if prop in ("NAME", "LOGIN_NAME", "TYPE", "HAS_PASSWORD", "MUST_CHANGE_PASSWORD", "DISABLED"):
            print(f"   {prop}: {val}")

except Exception as e:
    print("Secondary connection error:", e)

print("\n" + "=" * 60)
print("INSPECTING ACCOUNTS FROM ORGADMIN")
print("=" * 60)
try:
    accs = runner.run(settings.primary, ["USE ROLE ORGADMIN", "SHOW ACCOUNTS"])
    for a in accs[1]:
        print(f" Account: {a[1]} | Region: {a[3]} | Edition: {a[4]} | CreatedOn: {a[6]}")
except Exception as e:
    print("Orgadmin error:", e)

