# ============================================================
# Provider Configuration
# ============================================================
# Cloud credentials are NOT passed as Terraform variables. They are read from
# standard environment variables, loaded locally via `scripts/Load-Env.ps1`
# and injected by GitHub Actions secrets / OIDC in CI:
#   AWS   -> AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (or OIDC role)
#   Azure -> ARM_SUBSCRIPTION_ID, ARM_TENANT_ID, ARM_CLIENT_ID, ARM_CLIENT_SECRET
#   Snowflake -> TF_VAR_snowflake_* (sensitive variables below)

provider "aws" {
  region                      = var.aws_region
  skip_credentials_validation = true
  skip_requesting_account_id  = true

  default_tags {
    tags = local.common_tags
  }
}

provider "azurerm" {
  features {
    resource_group {
      # Demo environment: allow clean `terraform destroy` to save credits.
      prevent_deletion_if_contains_resources = false
    }
  }

  # Service principal has Contributor only; providers were registered manually.
  resource_provider_registrations = "none"
}

# Primary Snowflake account (AWS)
provider "snowflake" {
  organization_name = local.sf_primary.organization
  account_name      = local.sf_primary.account
  user              = var.snowflake_user
  role              = var.snowflake_role

  preview_features_enabled = [
    "snowflake_failover_group_resource",
    "snowflake_stage_resource",
    "snowflake_pipe_resource",
    "snowflake_table_resource"
  ]

  # Key-pair (JWT) auth is used when snowflake_private_key_path is provided.
  authenticator = var.snowflake_private_key_path != "" ? "SNOWFLAKE_JWT" : null
  private_key   = var.snowflake_private_key_path != "" ? file(var.snowflake_private_key_path) : null
}

# Secondary Snowflake account (Azure)
provider "snowflake" {
  alias             = "secondary"
  organization_name = local.sf_secondary.organization
  account_name      = local.sf_secondary.account
  user              = var.snowflake_user
  role              = var.snowflake_role

  preview_features_enabled = [
    "snowflake_failover_group_resource",
    "snowflake_table_resource"
  ]

  authenticator = var.snowflake_private_key_path != "" ? "SNOWFLAKE_JWT" : null
  private_key   = var.snowflake_private_key_path != "" ? file(var.snowflake_private_key_path) : null
}
