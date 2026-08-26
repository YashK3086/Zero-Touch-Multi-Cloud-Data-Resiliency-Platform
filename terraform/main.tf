terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    snowflake = {
      source  = "Snowflake-Labs/snowflake"
      version = "~> 0.87.0"
    }
  }
}

provider "aws" {
  region     = var.aws_region
  access_key = var.aws_access_key_id != "" ? var.aws_access_key_id : null
  secret_key = var.aws_secret_access_key != "" ? var.aws_secret_access_key : null

  default_tags {
    tags = {
      Project    = "Zero-Touch-Multi-Cloud-DR"
      ManagedBy  = "Terraform"
      CostCenter = "Zero-Cost-Guardrail"
    }
  }
}

provider "azurerm" {
  features {}
  skip_provider_registration = true

  subscription_id = var.azure_subscription_id != "" ? var.azure_subscription_id : null
  tenant_id       = var.azure_tenant_id != "" ? var.azure_tenant_id : null
  client_id       = var.azure_client_id != "" ? var.azure_client_id : null
  client_secret   = var.azure_client_secret != "" ? var.azure_client_secret : null
}

provider "snowflake" {
  account  = var.snowflake_primary_account != "" ? var.snowflake_primary_account : null
  user     = var.snowflake_user != "" ? var.snowflake_user : null
  password = var.snowflake_password != "" ? var.snowflake_password : null
  role     = var.snowflake_role != "" ? var.snowflake_role : null
}

# AWS S3 Primary Storage Bucket (Free Tier compliant)
resource "aws_s3_bucket" "sf_primary_stage" {
  bucket        = "sf-dr-primary-stage-${lower(replace(var.environment, "_", "-"))}"
  force_destroy = true
}

resource "aws_s3_bucket_lifecycle_configuration" "sf_primary_stage_lifecycle" {
  bucket = aws_s3_bucket.sf_primary_stage.id

  rule {
    id     = "auto-delete-old-objects"
    status = "Enabled"

    filter {}

    expiration {
      days = 1
    }
  }
}

# Azure Blob Storage Secondary Storage (Free Account compliant)
resource "azurerm_resource_group" "sf_dr_rg" {
  name     = "rg-sf-dr-${lower(replace(var.environment, "_", "-"))}"
  location = var.azure_location
}

resource "azurerm_storage_account" "sf_secondary_storage" {
  name                     = "sfdrsecstage${lower(replace(replace(var.environment, "-", ""), "_", ""))}"
  resource_group_name      = azurerm_resource_group.sf_dr_rg.name
  location                 = azurerm_resource_group.sf_dr_rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "sf_secondary_container" {
  name                  = "sf-dr-secondary-stage"
  storage_account_name  = azurerm_storage_account.sf_secondary_storage.name
  container_access_type = "private"
}

# ============================================================
# SNOWFLAKE — Advanced Managed Data Platform (Business Critical)
# ============================================================

# Snowflake DR Database (Primary — AWS)
resource "snowflake_database" "dr_database" {
  name                        = "SF_DR_DEMO_DB"
  comment                     = "Primary DR database on Snowflake Business Critical (AWS)"
  data_retention_time_in_days = 1 # Zero-cost guardrail
}

# Snowflake X-Small Warehouse (Auto-suspend 60s — Free Tier safe)
resource "snowflake_warehouse" "dr_warehouse" {
  name           = "DR_CONTROLLER_WH"
  warehouse_size = "X-SMALL"
  auto_suspend   = 60
  auto_resume    = true
  comment        = "Health controller warehouse — auto-suspends after 60s idle"
}

# Snowflake Schema inside DR Database
resource "snowflake_schema" "dr_schema" {
  database = snowflake_database.dr_database.name
  name     = "DR_STAGING"
  comment  = "Staging schema for external stage objects (AWS S3 + Azure Blob)"
}

# ============================================================
# AWS IAM — S3 Access Policy for Snowflake External Stage
# ============================================================

# IAM policy allowing Snowflake to read/write S3 stage bucket
resource "aws_iam_policy" "snowflake_s3_stage_policy" {
  name        = "snowflake-s3-stage-access-${var.environment}"
  description = "Grants Snowflake external stage read/write access to primary S3 bucket"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.sf_primary_stage.arn,
          "${aws_s3_bucket.sf_primary_stage.arn}/*"
        ]
      }
    ]
  })
}
