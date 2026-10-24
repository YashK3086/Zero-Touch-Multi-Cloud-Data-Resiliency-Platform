"""Probe whether the primary account can create a FAILOVER GROUP (requires Business Critical)."""
import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
r = conn.SnowflakeSqlRunner(30)

stmts = [
    "SELECT SYSTEM$GET_SNOWFLAKE_PLATFORM_INFO()",
    "CREATE FAILOVER GROUP IF NOT EXISTS SF_DR_FG_PROBE OBJECT_TYPES = DATABASES "
    "ALLOWED_DATABASES = SF_DR_DEMO_DB ALLOWED_ACCOUNTS = NNFCDXY.SF_AZURE_DR",
]
for st in stmts:
    try:
        print("[OK]", st[:60], "->", r.run(s.primary, [st]))
    except Exception as e:
        print("[ERR]", st[:60], "->", e)

try:
    r.run(s.primary, ["DROP FAILOVER GROUP IF EXISTS SF_DR_FG_PROBE"])
    print("probe cleaned up")
except Exception as e:
    print("cleanup:", e)
