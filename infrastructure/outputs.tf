output "s3_bucket_name" {
  description = "Name of the S3 bucket for video storage"
  value       = aws_s3_bucket.videos.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.videos.arn
}

output "sqs_queue_url" {
  description = "URL of the SQS queue for video processing"
  value       = aws_sqs_queue.video_processing.id
}

output "sqs_queue_arn" {
  description = "ARN of the SQS queue"
  value       = aws_sqs_queue.video_processing.arn
}

output "lambda_role_arn" {
  description = "ARN of the IAM role for Lambda processor"
  value       = aws_iam_role.lambda_processor.arn
}

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.main.endpoint
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.main.db_name
}

output "rds_username" {
  description = "RDS master username"
  value       = aws_db_instance.main.username
  sensitive   = true
}

output "billing_alarm_arn" {
  description = "ARN of the billing alarm (if enabled)"
  value       = var.enable_billing_alerts && var.notification_email != "" ? aws_cloudwatch_metric_alarm.billing[0].arn : null
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "aws_account_id" {
  description = "AWS account ID"
  value       = data.aws_caller_identity.current.account_id
}

# SQS Queue URLs
# API Deployment (Stage 3.3.6) - Lambda + API Gateway
output "lambda_api_function_name" {
  description = "Lambda API function name"
  value       = aws_lambda_function.api.function_name
}

output "lambda_api_function_arn" {
  description = "Lambda API function ARN"
  value       = aws_lambda_function.api.arn
}

output "api_gateway_rest_api_id" {
  description = "API Gateway REST API ID"
  value       = aws_api_gateway_rest_api.api.id
}

output "api_gateway_url" {
  description = "API Gateway invoke URL"
  value       = "https://${aws_api_gateway_rest_api.api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}"
}

output "api_health_check_url" {
  description = "API health check URL"
  value       = "https://${aws_api_gateway_rest_api.api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}/health"
}

output "api_docs_url" {
  description = "API documentation URL"
  value       = "https://${aws_api_gateway_rest_api.api.id}.execute-api.${var.aws_region}.amazonaws.com/${var.environment}/docs"
}

# ECR Repository
output "ecr_repository_url" {
  description = "ECR repository URL for Lambda processor image"
  value       = aws_ecr_repository.lambda_processor.repository_url
}

output "lambda_processor_function_name" {
  description = "Lambda processor function name"
  value       = aws_lambda_function.video_processor.function_name
}
