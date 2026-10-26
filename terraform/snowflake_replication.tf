# ============================================================
# Snowflake — Cross-Cloud Replication & Failover Groups
# ============================================================

# Failover Group on Primary (AWS)
resource "snowflake_failover_group" "dr_primary_failover_group" {
  name              = "SF_DR_FAILOVER_GROUP"
  object_types      = ["DATABASES"]
  allowed_databases = [snowflake_database.dr_database.name]
  allowed_accounts = [
    "${local.sf_primary.organization}.${local.sf_primary.account}",
    "${local.sf_secondary.organization}.${local.sf_secondary.account}"
  ]

  replication_schedule {
    interval = 10
  }
}

# Failover Group Replica on Secondary (Azure)
resource "snowflake_failover_group" "dr_secondary_failover_group" {
  provider   = snowflake.secondary
  name       = "SF_DR_FAILOVER_GROUP"
  depends_on = [snowflake_failover_group.dr_primary_failover_group]

  from_replica {
    name                = snowflake_failover_group.dr_primary_failover_group.name
    organization_name   = local.sf_primary.organization
    source_account_name = local.sf_primary.account
  }
}

# ============================================================
# Snowflake — Global Client Redirect Connection
# ============================================================

# Primary Connection (AWS)
resource "snowflake_primary_connection" "dr_primary_connection" {
  name                        = "SF_DR_GLOBAL_REDIRECT"
  comment                     = "Global Client Redirect connection for multi-cloud DR"
  enable_failover_to_accounts = ["${local.sf_secondary.organization}.${local.sf_secondary.account}"]
}

# Secondary Connection Replica (Azure)
resource "snowflake_secondary_connection" "dr_secondary_connection" {
  provider      = snowflake.secondary
  name          = "SF_DR_GLOBAL_REDIRECT"
  as_replica_of = "${local.sf_primary.organization}.${local.sf_primary.account}.${snowflake_primary_connection.dr_primary_connection.name}"
  comment       = "Secondary replica connection for multi-cloud DR"
  depends_on    = [snowflake_primary_connection.dr_primary_connection]
}
