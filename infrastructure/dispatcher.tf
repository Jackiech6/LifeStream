# Dispatcher Lambda: SQS -> idempotency check -> ECS RunTask. Deletes message only after task started.

data "archive_file" "dispatcher" {
  type        = "zip"
  source_file = "${path.module}/dispatcher/main.py"
  output_path = "${path.module}/dispatcher.zip"
}

resource "aws_iam_role" "dispatcher" {
  name = "${var.project_name}-dispatcher-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
      }
    ]
  })

  tags = { Name = "${var.project_name}-dispatcher-${var.environment}" }
}

resource "aws_iam_role_policy" "dispatcher" {
  name   = "${var.project_name}-dispatcher-policy-${var.environment}"
  role   = aws_iam_role.dispatcher.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:HeadObject"]
        Resource = ["${aws_s3_bucket.videos.arn}", "${aws_s3_bucket.videos.arn}/*"]
      },
      {
        Effect = "Allow"
        Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = [aws_sqs_queue.video_processing.arn, aws_sqs_queue.video_processing_dlq.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Scan"]
        Resource = [aws_dynamodb_table.idempotency.arn, aws_dynamodb_table.jobs.arn]
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask",
          "ecs:DescribeTasks",
          "ecs:DescribeTaskDefinition",
          "ecs:ListTasks"
        ]
        Resource = ["*"]
      },
      {
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = [aws_iam_role.ecs_task_execution.arn, aws_iam_role.ecs_task.arn]
      }
    ]
  })
}

resource "aws_lambda_function" "dispatcher" {
  function_name               = "${var.project_name}-dispatcher-${var.environment}"
  role                        = aws_iam_role.dispatcher.arn
  handler                     = "main.lambda_handler"
  runtime                     = "python3.11"
  filename                    = data.archive_file.dispatcher.output_path
  source_code_hash            = data.archive_file.dispatcher.output_base64sha256
  timeout                     = 60
  memory_size                 = 128
  # reserved_concurrent_executions: omit = no cap. Use 5–10 when account has sufficient quota.
  depends_on                  = [aws_cloudwatch_log_group.dispatcher]

  environment {
    variables = {
      ECS_CLUSTER            = aws_ecs_cluster.processor.name
      ECS_TASK_DEFINITION    = aws_ecs_task_definition.processor.family
      ECS_SUBNETS            = jsonencode(data.aws_subnets.default.ids)
      ECS_SECURITY_GROUPS    = jsonencode([aws_security_group.ecs_processor.id])
      S3_BUCKET              = aws_s3_bucket.videos.id
      IDEMPOTENCY_TABLE_NAME = aws_dynamodb_table.idempotency.name
      JOBS_TABLE_NAME        = aws_dynamodb_table.jobs.name
      SQS_QUEUE_URL          = aws_sqs_queue.video_processing.id
    }
  }

  tags = { Name = "${var.project_name}-dispatcher-${var.environment}" }
}

resource "aws_cloudwatch_log_group" "dispatcher" {
  name              = "/aws/lambda/${var.project_name}-dispatcher-${var.environment}"
  retention_in_days = 7
  tags = { Name = "${var.project_name}-dispatcher-logs-${var.environment}" }
}

resource "aws_lambda_event_source_mapping" "sqs_to_dispatcher" {
  event_source_arn = aws_sqs_queue.video_processing.arn
  function_name    = aws_lambda_function.dispatcher.arn
  batch_size       = 1
  enabled          = true
}
