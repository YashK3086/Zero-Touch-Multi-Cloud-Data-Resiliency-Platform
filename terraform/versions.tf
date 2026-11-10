# ============================================================
# Terraform & Provider Version Pins
# ============================================================
# - Terraform >= 1.10 is required for native S3 state locking (use_lockfile).
# - Snowflake Data Layer & DR Replication are provisioned 100% via the Zero-Touch UI Control Plane.
terraform {
  required_version = ">= 1.10.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
