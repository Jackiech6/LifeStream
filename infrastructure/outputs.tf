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
output "sqs_queue_url" {
  description = "SQS queue URL for video processing"
  value       = aws_sqs_queue.video_processing.id
}

output "sqs_dlq_url" {
  description = "SQS dead-letter queue URL"
  value       = aws_sqs_queue.video_processing_dlq.id
}

# Lambda Function
output "lambda_function_name" {
  description = "Lambda function name for video processing"
  value       = aws_lambda_function.video_processor.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.video_processor.arn
}
