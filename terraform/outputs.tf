output "sample_app_public_ip" {
  value       = aws_instance.sample_app_instance.public_ip
  description = "Live Customer Sample App Public IPv4"
}

output "sample_app_url" {
  value       = "http://${aws_instance.sample_app_instance.public_ip}:8080"
  description = "Live Sample App Health & Payment Endpoint"
}

output "sample_app_instance_id" {
  value       = aws_instance.sample_app_instance.id
  description = "Primary EC2 Instance ID"
}

output "sample_app_vpc_id" {
  value       = aws_vpc.sample_app_vpc.id
  description = "Primary Sample App VPC ID"
}

output "aws_s3_bucket_name" {
  value       = aws_s3_bucket.sample_app_data_bucket.id
  description = "Primary Sample App S3 Data Bucket"
}
