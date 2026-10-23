# ============================================================
# Terraform & Provider Version Pins
# ============================================================
# - Terraform >= 1.10 is required for native S3 state locking (use_lockfile).
# - Snowflake provider moved from Snowflake-Labs/* (0.x) to snowflakedb/* (v1+/v2+).
terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.22"
    }
  }
}
