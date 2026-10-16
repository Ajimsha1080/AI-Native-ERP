# AWS KMS & Secrets Manager Configuration

resource "aws_kms_key" "main_key" {
  description             = "KMS Key for ${var.environment} Agentic ERP Data Encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "${var.environment}-erp-kms-key"
  }
}

resource "aws_kms_alias" "main_key_alias" {
  name          = "alias/${var.environment}-agentic-erp"
  target_key_id = aws_kms_key.main_key.key_id
}

# Database credentials & application secrets in Secrets Manager
resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "${var.environment}/agentic-erp/app-secrets"
  kms_key_id              = aws_kms_key.main_key.arn
  recovery_window_in_days = 7

  tags = {
    Name = "${var.environment}-erp-app-secrets"
  }
}

resource "aws_secretsmanager_secret_version" "app_secrets_template" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    DATABASE_URL          = "postgresql://app_user:CHANGE_ME@endpoint:5432/agentic_platform"
    SECRET_KEY            = "CHANGE_ME_MIN_32_CHARS_SECURE_KEY"
    STRIPE_SECRET_KEY     = "sk_live_placeholder"
    STRIPE_WEBHOOK_SECRET = "whsec_placeholder"
    OPENAI_API_KEY        = "sk-placeholder"
    REDIS_URL             = "rediss://endpoint:6379/0"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
