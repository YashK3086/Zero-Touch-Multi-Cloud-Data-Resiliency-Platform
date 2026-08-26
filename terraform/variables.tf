variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for primary storage & resources"
}

variable "aws_access_key_id" {
  type        = string
  default     = ""
  description = "AWS Access Key ID"
  sensitive   = true
}

variable "aws_secret_access_key" {
  type        = string
  default     = ""
  description = "AWS Secret Access Key"
  sensitive   = true
}

variable "azure_location" {
  type        = string
  default     = "East US"
  description = "Azure region for secondary storage & resources"
}

variable "azure_subscription_id" {
  type        = string
  default     = ""
  description = "Azure Subscription ID"
  sensitive   = true
}

variable "azure_tenant_id" {
  type        = string
  default     = ""
  description = "Azure Tenant ID"
  sensitive   = true
}

variable "azure_client_id" {
  type        = string
  default     = ""
  description = "Azure Client ID (Service Principal App ID)"
  sensitive   = true
}

variable "azure_client_secret" {
  type        = string
  default     = ""
  description = "Azure Client Secret"
  sensitive   = true
}

variable "environment" {
  type        = string
  default     = "drdemo"
  description = "Environment tag for cost tracking and resource naming"
}

variable "snowflake_primary_account" {
  type        = string
  default     = ""
  description = "Snowflake Primary Account identifier on AWS"
}

variable "snowflake_secondary_account" {
  type        = string
  default     = ""
  description = "Snowflake Secondary Account identifier on Azure"
}

variable "snowflake_user" {
  type        = string
  default     = ""
  description = "Snowflake User"
}

variable "snowflake_password" {
  type        = string
  default     = ""
  description = "Snowflake Password"
  sensitive   = true
}

variable "snowflake_role" {
  type        = string
  default     = "ACCOUNTADMIN"
  description = "Snowflake Role"
}
