# Additional CloudWatch monitoring for Lambda and SQS

# API Lambda throttles
resource "aws_cloudwatch_metric_alarm" "lambda_api_throttles" {
  alarm_name          = "${var.project_name}-lambda-api-throttles-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "API Lambda is being throttled"
  alarm_actions       = var.notification_email != "" && var.enable_billing_alerts ? [aws_sns_topic.billing_alerts[0].arn] : []

  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
}

# Processor Lambda errors
resource "aws_cloudwatch_metric_alarm" "lambda_processor_errors" {
  alarm_name          = "${var.project_name}-lambda-processor-errors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Processor Lambda errors detected"
  alarm_actions       = var.notification_email != "" && var.enable_billing_alerts ? [aws_sns_topic.billing_alerts[0].arn] : []

  dimensions = {
    FunctionName = aws_lambda_function.video_processor.function_name
  }
}

# Processor Lambda throttles
resource "aws_cloudwatch_metric_alarm" "lambda_processor_throttles" {
  alarm_name          = "${var.project_name}-lambda-processor-throttles-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Processor Lambda is being throttled"
  alarm_actions       = var.notification_email != "" && var.enable_billing_alerts ? [aws_sns_topic.billing_alerts[0].arn] : []

  dimensions = {
    FunctionName = aws_lambda_function.video_processor.function_name
  }
}

# Processor Lambda duration (p95 near timeout)
resource "aws_cloudwatch_metric_alarm" "lambda_processor_duration_p95" {
  alarm_name          = "${var.project_name}-lambda-processor-duration-p95-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p95"
  threshold           = var.lambda_timeout * 900  # 90% of timeout in ms
  alarm_description   = "Processor Lambda p95 duration is close to timeout"
  alarm_actions       = var.notification_email != "" && var.enable_billing_alerts ? [aws_sns_topic.billing_alerts[0].arn] : []

  dimensions = {
    FunctionName = aws_lambda_function.video_processor.function_name
  }
}

# SQS backlog (main queue)
resource "aws_cloudwatch_metric_alarm" "sqs_backlog" {
  alarm_name          = "${var.project_name}-sqs-backlog-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Average"
  threshold           = 0
  alarm_description   = "Messages are accumulating in the main SQS queue"
  alarm_actions       = var.notification_email != "" && var.enable_billing_alerts ? [aws_sns_topic.billing_alerts[0].arn] : []

  dimensions = {
    QueueName = aws_sqs_queue.video_processing.name
  }
}

# SQS DLQ messages
resource "aws_cloudwatch_metric_alarm" "sqs_dlq_messages" {
  alarm_name          = "${var.project_name}-sqs-dlq-messages-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Average"
  threshold           = 0
  alarm_description   = "Messages are landing in the DLQ"
  alarm_actions       = var.notification_email != "" && var.enable_billing_alerts ? [aws_sns_topic.billing_alerts[0].arn] : []

  dimensions = {
    QueueName = aws_sqs_queue.video_processing_dlq.name
  }
}

