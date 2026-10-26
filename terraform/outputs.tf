output "aws_s3_bucket_name" {
  value       = aws_s3_bucket.sf_primary_stage.bucket
  description = "AWS Primary S3 Bucket Name (Snowflake External Stage)"
}

output "aws_iam_policy_arn" {
  value       = aws_iam_policy.snowflake_s3_stage_policy.arn
  description = "AWS IAM Policy ARN for Snowflake S3 External Stage access"
}

output "azure_resource_group_name" {
  value       = azurerm_resource_group.sf_dr_rg.name
  description = "Azure Resource Group holding secondary storage"
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
  description = "Snowflake DR Database (Business Critical - Primary)"
}

output "snowflake_schema_name" {
  value       = snowflake_schema.dr_schema.name
  description = "Snowflake DR Staging Schema"
}

output "snowflake_warehouse_name" {
  value       = snowflake_warehouse.dr_warehouse.name
  description = "Snowflake DR Controller Warehouse (X-Small, Auto-suspend 60s)"
}

output "snowflake_resource_monitor_name" {
  value       = snowflake_resource_monitor.dr_credit_guard.name
  description = "Snowflake resource monitor enforcing the monthly credit cap"
}

output "snowflake_failover_group_name" {
  value       = snowflake_failover_group.dr_primary_failover_group.name
  description = "Snowflake Active Failover Group"
}

output "snowflake_primary_connection_name" {
  value       = snowflake_primary_connection.dr_primary_connection.name
  description = "Snowflake Global Client Redirect Connection handle"
}

output "snowflake_pipe_name" {
  value       = snowflake_pipe.dr_financial_pipe.name
  description = "Production Snowpipe for S3 auto-ingestion"
}

output "snowflake_pipe_notification_channel" {
  value       = snowflake_pipe.dr_financial_pipe.notification_channel
  description = "Amazon SQS notification ARN for S3 event notifications"
}
