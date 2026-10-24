import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
runner = conn.SnowflakeSqlRunner(20)

print("--- ORG & ACCOUNT METADATA ---")
meta = runner.run(s.primary, [
    "SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME(), CURRENT_REGION(), CURRENT_VERSION()"
])
print("Primary info:", meta[0][0])

print("\n--- SHOW ACCOUNTS IN ORG ---")
try:
    accounts = runner.run(s.primary, ["SHOW ACCOUNTS"])
    for a in accounts[0]:
        print(f"Account: {a[0]} | Org: {a[1]} | Region: {a[3]} | Edition: {a[4]} | IsPrimary/Status: {a}")
except Exception as e:
    print("SHOW ACCOUNTS error:", e)
