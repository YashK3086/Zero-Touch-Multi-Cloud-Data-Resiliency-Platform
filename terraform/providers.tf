# ============================================================
# Provider Configuration (AWS Primary Cloud Infrastructure)
# ============================================================
# Cloud credentials are read from standard environment variables,
# loaded locally via `scripts/Load-Env.ps1`:
#   AWS -> AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

provider "aws" {
  region                      = var.aws_region
  skip_credentials_validation = false
  skip_requesting_account_id  = false

  default_tags {
    tags = local.common_tags
  }
}

