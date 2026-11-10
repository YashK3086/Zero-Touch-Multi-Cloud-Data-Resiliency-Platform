locals {
  # Naming helpers
  env_slug    = lower(replace(var.environment, "_", "-"))
  env_compact = lower(replace(replace(var.environment, "-", ""), "_", ""))

  common_tags = {
    Project     = "PaySecure-Customer-Sample-App"
    Environment = var.environment
    ManagedBy   = "Terraform"
    CostCenter  = "Zero-Cost-Guardrail"
  }
}
