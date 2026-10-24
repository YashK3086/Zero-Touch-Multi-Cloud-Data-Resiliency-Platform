locals {
  # Naming helpers
  env_slug    = lower(replace(var.environment, "_", "-"))                  # e.g. drdemo   (S3, RG)
  env_compact = lower(replace(replace(var.environment, "-", ""), "_", "")) # e.g. drdemo   (Azure SA)

  # "ORG-ACCOUNT" identifier -> organization_name / account_name for the v2 provider
  sf_primary_parts = regex("^([^-]+)-(.+)$", var.snowflake_primary_account)
  sf_primary = {
    organization = upper(local.sf_primary_parts[0])
    account      = upper(local.sf_primary_parts[1])
  }

  sf_secondary_parts = regex("^([^-]+)-(.+)$", var.snowflake_secondary_account)
  sf_secondary = {
    organization = upper(local.sf_secondary_parts[0])
    account      = upper(local.sf_secondary_parts[1])
  }

  common_tags = {
    Project     = "Zero-Touch-Multi-Cloud-DR"
    Environment = var.environment
    ManagedBy   = "Terraform"
    CostCenter  = "Zero-Cost-Guardrail"
  }
}
