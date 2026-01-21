variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "lifestream"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "s3_bucket_name" {
  description = "S3 bucket name for video storage"
  type        = string
  default     = ""
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 20
}

variable "db_username" {
  description = "RDS master username"
  type        = string
  default     = "lifestream_admin"
  sensitive   = true
}

variable "db_password" {
  description = "RDS master password"
  type        = string
  sensitive   = true
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 900 # 15 minutes
}

variable "lambda_memory_size" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 3008 # Maximum for better performance
}

variable "enable_billing_alerts" {
  description = "Enable CloudWatch billing alerts"
  type        = bool
  default     = true
}

variable "billing_alert_threshold" {
  description = "Billing alert threshold in USD"
  type        = number
  default     = 50.0
}

variable "notification_email" {
  description = "Email for billing alerts and notifications"
  type        = string
  default     = ""
}

variable "openai_api_key" {
  description = "OpenAI API key for Lambda environment"
  type        = string
  sensitive   = true
  default     = ""
}

variable "huggingface_token" {
  description = "HuggingFace token for Lambda environment"
  type        = string
  sensitive   = true
  default     = ""
}

variable "pinecone_api_key" {
  description = "Pinecone API key for Lambda environment"
  type        = string
  sensitive   = true
  default     = ""
}

variable "pinecone_index_name" {
  description = "Pinecone index name"
  type        = string
  default     = "lifestream-dev"
}

variable "pinecone_environment" {
  description = "Pinecone environment/region"
  type        = string
  default     = "us-east-1"
}

variable "lambda_memory" {
  description = "Lambda function memory in MB (alias for lambda_memory_size)"
  type        = number
  default     = 3008
}

# API Deployment (Stage 3.3.6) - Lambda + API Gateway
# Note: Lambda auto-scales automatically, no need for min/max capacity variables

variable "openai_api_key_secret_arn" {
  description = "ARN of Secrets Manager secret for OpenAI API key (optional, can use env var instead)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "pinecone_api_key_secret_arn" {
  description = "ARN of Secrets Manager secret for Pinecone API key (optional, can use env var instead)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "huggingface_token_secret_arn" {
  description = "ARN of Secrets Manager secret for HuggingFace token (optional, can use env var instead)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "api_lambda_memory" {
  description = "Lambda API function memory in MB"
  type        = number
  default     = 512
}

variable "api_lambda_timeout" {
  description = "Lambda API function timeout in seconds"
  type        = number
  default     = 30
}
