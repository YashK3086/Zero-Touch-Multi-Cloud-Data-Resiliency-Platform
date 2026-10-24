"""Insert sample transactional data into the primary database."""
import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
r = conn.SnowflakeSqlRunner(30)

stmts = [
    "USE WAREHOUSE DR_CONTROLLER_WH",
    "CREATE TABLE IF NOT EXISTS SF_DR_DEMO_DB.DR_STAGING.TRANSACTIONS (id INT AUTOINCREMENT, account_id VARCHAR, amount NUMBER(10,2), status VARCHAR, created_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP())",
    "INSERT INTO SF_DR_DEMO_DB.DR_STAGING.TRANSACTIONS (account_id, amount, status) VALUES ('ACC-1001', 5420.50, 'SETTLED'), ('ACC-1002', 120.00, 'PENDING'), ('ACC-1003', 980.25, 'SETTLED')",
    "SELECT COUNT(*), CURRENT_ACCOUNT() FROM SF_DR_DEMO_DB.DR_STAGING.TRANSACTIONS"
]

res = r.run(s.primary, stmts)
print("Primary Insert Results:", res)
