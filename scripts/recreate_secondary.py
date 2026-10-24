import sf_dr_controller.config as c
import sf_dr_controller.connection as conn

s = c.Settings()
runner = conn.SnowflakeSqlRunner(60)

pubkey = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAScF+bOz8207Q9S7WYdqv"
    "1UMSkMNoZFUF1Ohwy+K7N9mC19mg2MVmX9BUbXgL41qm4FT1uW0o2N7/6hkKN/hQ"
    "KqiGNSy7gpQ9A4jBxTqTv6BSpI0E17WZGuuPmU3/E/sqFXUSw2O1r5OGLDzR5SXh"
    "yCd214BjUZfAjn6zvcdYBnFfN04EO4Jwp808njd1H4g1WUvknp/DJqzMenkMQwP7"
    "Q9kGAXSrrU6+CsS1Nednu7GewQIh2Ka2dG0vdhTtSK/Csc/Pc0n5vUvgU6IcGeXd"
    "L9hbe5ceGU1TBc/rZydlWU3YWPYCxA9TmYH1Fn9T8ffWpm7db2QCI3D3J6ZNSsYW"
    "IDAQAB"
)

email = "yashvardhankhanna360@gmail.com"

print("Step 1: Dropping old secondary account SF_AZURE_SECONDARY...")
try:
    runner.run(s.primary, [
        "USE ROLE ORGADMIN",
        "DROP ACCOUNT SF_AZURE_SECONDARY GRACE_PERIOD_IN_DAYS = 0"
    ])
    print("Old account dropped.")
except Exception as e:
    print("Drop note/error:", e)

print("\nStep 2: Creating new account SF_AZURE_SECONDARY...")
create_sql = f"""
CREATE ACCOUNT SF_AZURE_SECONDARY
  ADMIN_NAME = YASHSNOW20
  ADMIN_PASSWORD = 'Atlas20@200605'
  ADMIN_RSA_PUBLIC_KEY = '{pubkey}'
  EMAIL = '{email}'
  EDITION = BUSINESS_CRITICAL
  REGION = 'azure_eastus2'
"""

try:
    res = runner.run(s.primary, [
        "USE ROLE ORGADMIN",
        create_sql
    ])
    print("CREATE ACCOUNT succeeded:", res)
except Exception as e:
    print("CREATE ACCOUNT with same name error:", e)
    print("\nTrying alternate name SF_AZURE_DR...")
    create_sql_alt = f"""
    CREATE ACCOUNT SF_AZURE_DR
      ADMIN_NAME = YASHSNOW20
      ADMIN_PASSWORD = 'Atlas20@200605'
      ADMIN_RSA_PUBLIC_KEY = '{pubkey}'
      EMAIL = '{email}'
      EDITION = BUSINESS_CRITICAL
      REGION = 'azure_eastus2'
    """
    res_alt = runner.run(s.primary, [
        "USE ROLE ORGADMIN",
        create_sql_alt
    ])
    print("CREATE ACCOUNT SF_AZURE_DR succeeded:", res_alt)
