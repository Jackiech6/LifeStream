terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment and configure for remote state (recommended for production)
  # backend "s3" {
  #   bucket = "lifestream-terraform-state"
  #   key    = "terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# S3 Bucket for video storage
resource "aws_s3_bucket" "videos" {
  bucket = var.s3_bucket_name != "" ? var.s3_bucket_name : "${var.project_name}-videos-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-videos-${var.environment}"
  }
}

# S3 Bucket versioning
resource "aws_s3_bucket_versioning" "videos" {
  bucket = aws_s3_bucket.videos.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket lifecycle configuration (auto-delete after 30 days)
resource "aws_s3_bucket_lifecycle_configuration" "videos" {
  bucket = aws_s3_bucket.videos.id

  rule {
    id     = "delete-old-videos"
    status = "Enabled"

    filter {
      prefix = ""  # Apply to all objects
    }

    expiration {
      days = 30
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}

# S3 Bucket CORS configuration for web uploads
resource "aws_s3_bucket_cors_configuration" "videos" {
  bucket = aws_s3_bucket.videos.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE", "HEAD"]
    allowed_origins = ["*"] # Restrict in production
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# S3 Bucket public access block (security)
resource "aws_s3_bucket_public_access_block" "videos" {
  bucket = aws_s3_bucket.videos.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket notification configuration (triggers SQS on upload)
resource "aws_s3_bucket_notification" "video_upload_trigger" {
  bucket = aws_s3_bucket.videos.id

  queue {
    queue_arn = aws_sqs_queue.video_processing.arn
    events    = ["s3:ObjectCreated:*"]
    filter_prefix = "uploads/"
    filter_suffix = ".mp4"
  }

  # Also trigger for other common video formats
  queue {
    queue_arn = aws_sqs_queue.video_processing.arn
    events    = ["s3:ObjectCreated:*"]
    filter_prefix = "uploads/"
    filter_suffix = ".mov"
  }

  queue {
    queue_arn = aws_sqs_queue.video_processing.arn
    events    = ["s3:ObjectCreated:*"]
    filter_prefix = "uploads/"
    filter_suffix = ".avi"
  }

  queue {
    queue_arn = aws_sqs_queue.video_processing.arn
    events    = ["s3:ObjectCreated:*"]
    filter_prefix = "uploads/"
    filter_suffix = ".mkv"
  }

  depends_on = [aws_sqs_queue.video_processing]
}

# SQS Queue for video processing jobs
resource "aws_sqs_queue" "video_processing" {
  name                       = "${var.project_name}-video-processing-${var.environment}"
  visibility_timeout_seconds = var.lambda_timeout + 60 # Lambda timeout + buffer
  message_retention_seconds  = 86400                   # 24 hours
  receive_wait_time_seconds  = 20                      # Long polling

  tags = {
    Name = "${var.project_name}-video-processing-${var.environment}"
  }
}

# Dead-letter queue for failed jobs
resource "aws_sqs_queue" "video_processing_dlq" {
  name = "${var.project_name}-video-processing-dlq-${var.environment}"

  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name = "${var.project_name}-video-processing-dlq-${var.environment}"
  }
}

# Connect main queue to DLQ
resource "aws_sqs_queue_redrive_policy" "video_processing" {
  queue_url = aws_sqs_queue.video_processing.id

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.video_processing_dlq.arn
    maxReceiveCount     = 3
  })
}

# SQS Queue Policy to allow S3 to send messages
resource "aws_sqs_queue_policy" "video_processing" {
  queue_url = aws_sqs_queue.video_processing.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.video_processing.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = "arn:aws:s3:::${aws_s3_bucket.videos.id}"
          }
        }
      }
    ]
  })
}

# IAM Role for Lambda processing function
resource "aws_iam_role" "lambda_processor" {
  name = "${var.project_name}-lambda-processor-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-lambda-processor-${var.environment}"
  }
}

# IAM Policy for Lambda to access S3, SQS, and CloudWatch
resource "aws_iam_role_policy" "lambda_processor" {
  name = "${var.project_name}-lambda-processor-policy-${var.environment}"
  role = aws_iam_role.lambda_processor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.videos.arn,
          "${aws_s3_bucket.videos.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:SendMessage"
        ]
        Resource = [
          aws_sqs_queue.video_processing.arn,
          aws_sqs_queue.video_processing_dlq.arn
        ]
      }
    ]
  })
}

# VPC and Security Group for RDS (if needed)
# For now, using public RDS for simplicity (restrict in production)

# RDS Subnet Group (using default VPC)
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group-${var.environment}"
  subnet_ids = data.aws_subnets.default.ids

  tags = {
    Name = "${var.project_name}-db-subnet-group-${var.environment}"
  }
}

# Get default VPC subnets
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# RDS Security Group
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg-${var.environment}"
  description = "Security group for RDS database"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "PostgreSQL from VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-rds-sg-${var.environment}"
  }
}

# RDS Instance (PostgreSQL)
resource "aws_db_instance" "main" {
  identifier        = "${var.project_name}-db-${var.environment}"
  engine            = "postgres"
  engine_version    = "15.4"
  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "lifestream"
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "mon:04:00-mon:05:00"

  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = var.environment == "prod" ? "${var.project_name}-db-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}" : null

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = {
    Name = "${var.project_name}-db-${var.environment}"
  }
}

# CloudWatch Billing Alarm (if enabled)
resource "aws_cloudwatch_metric_alarm" "billing" {
  count = var.enable_billing_alerts && var.notification_email != "" ? 1 : 0

  alarm_name          = "${var.project_name}-billing-alert-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = 86400 # 24 hours
  statistic           = "Maximum"
  threshold           = var.billing_alert_threshold
  alarm_description   = "Alert when estimated charges exceed ${var.billing_alert_threshold} USD"
  alarm_actions       = [aws_sns_topic.billing_alerts[0].arn]

  dimensions = {
    Currency = "USD"
  }
}

# SNS Topic for billing alerts
resource "aws_sns_topic" "billing_alerts" {
  count = var.enable_billing_alerts && var.notification_email != "" ? 1 : 0
  name  = "${var.project_name}-billing-alerts-${var.environment}"
}

# SNS Topic Subscription (email)
resource "aws_sns_topic_subscription" "billing_alerts" {
  count     = var.enable_billing_alerts && var.notification_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.billing_alerts[0].arn
  protocol  = "email"
  endpoint  = var.notification_email
}
