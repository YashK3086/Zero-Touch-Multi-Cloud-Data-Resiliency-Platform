# ============================================================
# Snowflake — Core Objects on Primary (AWS)        [SnowflakeAgent]
# ============================================================

# Hard credit guardrail: notify at 50/75/90%, suspend at 100%, kill at 110%.
resource "snowflake_resource_monitor" "dr_credit_guard" {
  name         = "DR_CREDIT_GUARD"
  credit_quota = var.snowflake_monthly_credit_quota

  notify_triggers           = [50, 75, 90]
  suspend_trigger           = 100
  suspend_immediate_trigger = 110
}

# X-Small warehouse, starts suspended, auto-suspends after 60s idle
resource "snowflake_warehouse" "dr_warehouse" {
  name                = "DR_CONTROLLER_WH"
  warehouse_size      = "XSMALL"
  auto_suspend        = 60
  auto_resume         = true
  initially_suspended = true
  resource_monitor    = snowflake_resource_monitor.dr_credit_guard.name
  comment             = "Health controller warehouse - auto-suspends after 60s idle"
}

resource "snowflake_database" "dr_database" {
  name                        = "SF_DR_DEMO_DB"
  comment                     = "Primary DR database on Snowflake Business Critical (AWS)"
  data_retention_time_in_days = 1 # Zero-cost guardrail
}

resource "snowflake_schema" "dr_schema" {
  database = snowflake_database.dr_database.name
  name     = "DR_STAGING"
  comment  = "Staging schema for external stage objects (AWS S3 + Azure Blob)"
}

# ============================================================
# Snowflake — Core Objects on Secondary (Azure)     [SnowflakeAgent]
# ============================================================

resource "snowflake_resource_monitor" "dr_credit_guard_secondary" {
  provider     = snowflake.secondary
  name         = "DR_CREDIT_GUARD"
  credit_quota = var.snowflake_monthly_credit_quota

  notify_triggers           = [50, 75, 90]
  suspend_trigger           = 100
  suspend_immediate_trigger = 110
}

resource "snowflake_warehouse" "dr_warehouse_secondary" {
  provider            = snowflake.secondary
  name                = "DR_CONTROLLER_WH"
  warehouse_size      = "XSMALL"
  auto_suspend        = 60
  auto_resume         = true
  initially_suspended = true
  resource_monitor    = snowflake_resource_monitor.dr_credit_guard_secondary.name
  comment             = "Secondary DR warehouse - auto-suspends after 60s idle"
}
