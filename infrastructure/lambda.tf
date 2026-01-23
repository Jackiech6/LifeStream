# Lambda Function for Video Processing (Container Image)
# Uses ECR container image instead of zip package to support large dependencies
resource "aws_lambda_function" "video_processor" {
  function_name = "${var.project_name}-video-processor-${var.environment}"
  role          = aws_iam_role.lambda_processor.arn
  package_type  = "Image"
  # Use ECR image URI with latest tag
  image_uri     = "${aws_ecr_repository.lambda_processor.repository_url}:latest"
  
  timeout     = var.lambda_timeout
  memory_size = var.lambda_memory_size

  # Environment variables
  environment {
    variables = {
      OPENAI_API_KEY        = var.openai_api_key != "" ? var.openai_api_key : ""
      HUGGINGFACE_TOKEN     = var.huggingface_token != "" ? var.huggingface_token : ""
      PINECONE_API_KEY      = var.pinecone_api_key != "" ? var.pinecone_api_key : ""
      AWS_S3_BUCKET_NAME    = aws_s3_bucket.videos.id
      AWS_SQS_QUEUE_URL     = aws_sqs_queue.video_processing.id
      AWS_SQS_DLQ_URL       = aws_sqs_queue.video_processing_dlq.id
      # AWS_REGION is automatically provided by Lambda - do not set it manually
      PINECONE_INDEX_NAME   = var.pinecone_index_name != "" ? var.pinecone_index_name : "lifestream-dev"
      PINECONE_ENVIRONMENT  = var.pinecone_environment != "" ? var.pinecone_environment : "us-east-1"
      LLM_MODEL             = "gpt-4o"
      EMBEDDING_MODEL_NAME  = "text-embedding-3-small"
      # Whisper uses /tmp in Lambda (only writable dir); avoids read-only filesystem errors
      WHISPER_CACHE_DIR     = "/tmp/whisper_cache"
    }
  }

  # VPC configuration (if needed for RDS access)
  # vpc_config {
  #   subnet_ids         = data.aws_subnets.default.ids
  #   security_group_ids = [aws_security_group.lambda.id]
  # }

  tags = {
    Name = "${var.project_name}-video-processor-${var.environment}"
  }

  depends_on = [
    aws_ecr_repository.lambda_processor
  ]
}

# Lambda Event Source Mapping (SQS trigger)
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.video_processing.arn
  function_name    = aws_lambda_function.video_processor.arn
  batch_size       = 1  # Process one video at a time
  enabled          = true
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_processor" {
  name              = "/aws/lambda/${aws_lambda_function.video_processor.function_name}"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-lambda-logs-${var.environment}"
  }
}
