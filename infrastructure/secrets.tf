# Secrets Manager: store API keys and inject into ECS processor (and optionally API Lambda).

resource "aws_secretsmanager_secret" "openai_api_key" {
  name        = "${var.project_name}/openai-api-key-${var.environment}"
  description = "OpenAI API key for LifeStream processor"
  tags        = { Name = "${var.project_name}-openai-key-${var.environment}" }
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  count         = var.openai_api_key != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = var.openai_api_key
}

resource "aws_secretsmanager_secret" "huggingface_token" {
  name        = "${var.project_name}/huggingface-token-${var.environment}"
  description = "Hugging Face token for LifeStream processor"
  tags        = { Name = "${var.project_name}-hf-token-${var.environment}" }
}

resource "aws_secretsmanager_secret_version" "huggingface_token" {
  count         = var.huggingface_token != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.huggingface_token.id
  secret_string = var.huggingface_token
}

resource "aws_secretsmanager_secret" "pinecone_api_key" {
  name        = "${var.project_name}/pinecone-api-key-${var.environment}"
  description = "Pinecone API key for LifeStream processor"
  tags        = { Name = "${var.project_name}-pinecone-key-${var.environment}" }
}

resource "aws_secretsmanager_secret_version" "pinecone_api_key" {
  count         = var.pinecone_api_key != "" ? 1 : 0
  secret_id     = aws_secretsmanager_secret.pinecone_api_key.id
  secret_string = var.pinecone_api_key
}
