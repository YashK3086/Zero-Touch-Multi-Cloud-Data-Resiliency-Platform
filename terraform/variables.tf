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
  description = "AWS region for primary storage & sample app resources"
}

variable "azure_location" {
  type        = string
  default     = "East US"
  description = "Azure region for secondary storage & pilot-light standby resources"
}
