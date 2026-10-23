# ============================================================
# Remote State Backend — AWS S3 (Free Tier) with native locking
# ============================================================
# Partial configuration: concrete values live in `backend.hcl` (gitignored).
# Bootstrap the bucket once via `terraform/bootstrap`, then run:
#   terraform init -backend-config=backend.hcl
terraform {
  backend "s3" {}
}
