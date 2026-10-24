"""Clean up failover groups and client redirect connections before terraform destroy."""
import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
r = conn.SnowflakeSqlRunner(30)

print("--- 1. Dropping secondary DR objects (Azure) ---")
sec_stmts = [
    "DROP FAILOVER GROUP IF EXISTS SF_DR_FAILOVER_GROUP",
    "DROP CONNECTION IF EXISTS SF_DR_GLOBAL_REDIRECT",
    "DROP DATABASE IF EXISTS SF_DR_DEMO_DB",
    "DROP WAREHOUSE IF EXISTS DR_CONTROLLER_WH",
    "DROP RESOURCE MONITOR IF EXISTS DR_CREDIT_GUARD"
]
for st in sec_stmts:
    try:
        res = r.run(s.secondary, [st])
        print(f"[Secondary OK] {st} -> {res}")
    except Exception as e:
        print(f"[Secondary ERR] {st} -> {e}")

print("\n--- 2. Dropping primary DR objects (AWS) ---")
prim_stmts = [
    "DROP FAILOVER GROUP IF EXISTS SF_DR_FAILOVER_GROUP",
    "DROP CONNECTION IF EXISTS SF_DR_GLOBAL_REDIRECT"
]
for st in prim_stmts:
    try:
        res = r.run(s.primary, [st])
        print(f"[Primary OK] {st} -> {res}")
    except Exception as e:
        print(f"[Primary ERR] {st} -> {e}")

print("\nPre-destroy cleanup complete.")
