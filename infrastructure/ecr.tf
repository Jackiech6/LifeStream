# ECR Repository for Lambda Container Images

resource "aws_ecr_repository" "lambda_processor" {
  name                 = "${var.project_name}-lambda-processor-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${var.project_name}-lambda-processor-${var.environment}"
  }
}

# ECR Lifecycle Policy (keep last 10 images)
resource "aws_ecr_lifecycle_policy" "lambda_processor" {
  repository = aws_ecr_repository.lambda_processor.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ECR Repository for API Lambda Container Image
resource "aws_ecr_repository" "lambda_api" {
  name                 = "${var.project_name}-lambda-api-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${var.project_name}-lambda-api-${var.environment}"
  }
}

# ECR Lifecycle Policy for API (keep last 10 images)
resource "aws_ecr_lifecycle_policy" "lambda_api" {
  repository = aws_ecr_repository.lambda_api.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
