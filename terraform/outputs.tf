output "aws_s3_bucket_name" {
  value       = aws_s3_bucket.sf_primary_stage.bucket
  description = "AWS Primary S3 Bucket Name (Snowflake External Stage)"
}

output "azure_storage_account_name" {
  value       = azurerm_storage_account.sf_secondary_storage.name
  description = "Azure Secondary Storage Account Name"
}

output "azure_container_name" {
  value       = azurerm_storage_container.sf_secondary_container.name
  description = "Azure Secondary Container Name"
}

output "snowflake_database_name" {
  value       = snowflake_database.dr_database.name
  description = "Snowflake DR Database (Business Critical — Primary)"
}

output "snowflake_warehouse_name" {
  value       = snowflake_warehouse.dr_warehouse.name
  description = "Snowflake DR Controller Warehouse (X-Small, Auto-suspend 60s)"
}

output "snowflake_schema_name" {
  value       = snowflake_schema.dr_schema.name
  description = "Snowflake DR Staging Schema"
}

output "aws_iam_policy_arn" {
  value       = aws_iam_policy.snowflake_s3_stage_policy.arn
  description = "AWS IAM Policy ARN for Snowflake S3 External Stage access"
}
