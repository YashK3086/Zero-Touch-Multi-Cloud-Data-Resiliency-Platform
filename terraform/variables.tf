# ------------------------------------------------------------
# General / Regions (non-secret -> terraform.tfvars)
# ------------------------------------------------------------
variable "environment" {
  type        = string
  default     = "drdemo"
  description = "Environment tag for cost tracking and resource naming"

  validation {
    condition     = can(regex("^[a-z0-9_-]{2,12}$", var.environment))
    error_message = "environment must be 2-12 chars of [a-z0-9_-] (Azure storage account name limit)."
  }
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for primary storage & resources"
}

variable "azure_location" {
  type        = string
  default     = "East US"
  description = "Azure region for secondary storage & resources"
}

# ------------------------------------------------------------
# Snowflake (account ids non-secret; credentials via TF_VAR_* env)
# ------------------------------------------------------------
variable "snowflake_primary_account" {
  type        = string
  description = "Primary Snowflake account identifier on AWS, format ORG-ACCOUNT"

  validation {
    condition     = can(regex("^[A-Za-z0-9]+-[A-Za-z0-9_]+$", var.snowflake_primary_account))
    error_message = "Use the ORGNAME-ACCOUNTNAME identifier format (e.g. NNFCDXY-OZ10928)."
  }
}

variable "snowflake_secondary_account" {
  type        = string
  default     = ""
  description = "Secondary Snowflake account identifier on Azure, format ORG-ACCOUNT (used from Phase 2)"
}

variable "snowflake_user" {
  type        = string
  description = "Snowflake login name used by Terraform"
}

variable "snowflake_password" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Snowflake password (ignored when snowflake_private_key_path is set)"
}

variable "snowflake_private_key_path" {
  type        = string
  default     = ""
  description = "Path to an unencrypted PKCS#8 private key for key-pair (JWT) auth. Preferred over password."
}

variable "snowflake_role" {
  type        = string
  default     = "ACCOUNTADMIN"
  description = "Snowflake role used by Terraform"
}

variable "snowflake_monthly_credit_quota" {
  type        = number
  default     = 10
  description = "Monthly credit cap for the DR_CREDIT_GUARD resource monitor (warehouses suspend at 100%)"
}
