import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
r = conn.SnowflakeSqlRunner(30)

sql = """
SELECT QUERY_TEXT, USER_NAME, START_TIME, EXECUTION_STATUS
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE QUERY_TEXT ILIKE '%SF_AZURE_SECONDARY%'
ORDER BY START_TIME DESC
LIMIT 10
"""
try:
    res = r.run(s.primary, [sql])
    with open("scripts/account_history.txt", "w", encoding="utf-8") as f:
        for row in res[0]:
            f.write(f"Time: {row[2]} | User: {row[1]} | Status: {row[3]}\n")
            f.write(f"Query: {row[0]}\n")
            f.write("-" * 40 + "\n")
    print("Wrote to scripts/account_history.txt")
except Exception as e:
    print("Error:", e)
