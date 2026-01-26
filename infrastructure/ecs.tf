# ECS Fargate for video processor (on-demand RunTask, no long-running service)
# Dispatcher Lambda consumes SQS and starts one ECS task per job.

locals {
  processor_cpu    = 4096   # 4 vCPU
  processor_memory = 8192   # 8 GB
}

# Security group for processor tasks (uses data.aws_vpc.default from main.tf)
resource "aws_security_group" "ecs_processor" {
  name        = "${var.project_name}-ecs-processor-${var.environment}"
  description = "Egress only for processor Fargate tasks"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-ecs-processor-${var.environment}"
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "processor" {
  name = "${var.project_name}-processor-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = {
    Name = "${var.project_name}-processor-${var.environment}"
  }
}

# CloudWatch log group for processor tasks
resource "aws_cloudwatch_log_group" "processor_task" {
  name              = "/ecs/${var.project_name}-processor-${var.environment}"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-processor-logs-${var.environment}"
  }
}

# Task execution role: ECR pull, CloudWatch logs
resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project_name}-ecs-task-execution-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-ecs-task-execution-${var.environment}"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow ECS task to read secrets from Secrets Manager
resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name   = "${var.project_name}-ecs-execution-secrets-${var.environment}"
  role   = aws_iam_role.ecs_task_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [
          aws_secretsmanager_secret.openai_api_key.arn,
          aws_secretsmanager_secret.huggingface_token.arn,
          aws_secretsmanager_secret.pinecone_api_key.arn,
        ]
      }
    ]
  })
}

# Task role: S3, DynamoDB (idempotency + jobs)
resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-ecs-task-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-ecs-task-${var.environment}"
  }
}

resource "aws_iam_role_policy" "ecs_task" {
  name   = "${var.project_name}-ecs-task-policy-${var.environment}"
  role   = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.videos.arn,
          "${aws_s3_bucket.videos.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"]
        Resource = [
          aws_dynamodb_table.idempotency.arn,
          aws_dynamodb_table.jobs.arn
        ]
      }
    ]
  })
}

# Fargate task definition for processor
resource "aws_ecs_task_definition" "processor" {
  family                   = "${var.project_name}-processor-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = local.processor_cpu
  memory                   = local.processor_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "processor"
      image     = "${aws_ecr_repository.lambda_processor.repository_url}:latest"
      essential = true

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.processor_task.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "processor"
        }
      }

      environment = [
        { name = "AWS_DEFAULT_REGION", value = var.aws_region },
        { name = "AWS_S3_BUCKET_NAME", value = aws_s3_bucket.videos.id },
        { name = "IDEMPOTENCY_TABLE_NAME", value = aws_dynamodb_table.idempotency.name },
        { name = "JOBS_TABLE_NAME", value = aws_dynamodb_table.jobs.name },
        { name = "PINECONE_INDEX_NAME", value = var.pinecone_index_name != "" ? var.pinecone_index_name : "lifestream-dev" },
        { name = "PINECONE_ENVIRONMENT", value = var.pinecone_environment != "" ? var.pinecone_environment : "us-east-1" },
        # Same region as S3 + VPC Gateway endpoint for fast S3 access; streaming overlaps download with audio decode
        { name = "USE_STREAMING_VIDEO_INTAKE", value = "true" },
      ]

      secrets = concat(
        var.openai_api_key != "" ? [{ name = "OPENAI_API_KEY", valueFrom = aws_secretsmanager_secret.openai_api_key.arn }] : [],
        var.huggingface_token != "" ? [{ name = "HUGGINGFACE_TOKEN", valueFrom = aws_secretsmanager_secret.huggingface_token.arn }] : [],
        var.pinecone_api_key != "" ? [{ name = "PINECONE_API_KEY", valueFrom = aws_secretsmanager_secret.pinecone_api_key.arn }] : []
      )

      linuxParameters = {
        initProcessEnabled = true
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-processor-task-${var.environment}"
  }
}
