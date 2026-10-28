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

# Empty Secrets Manager shell for runtime application secrets (populated securely via KMS outside git)
resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "${var.environment}/agentic-erp/app-secrets"
  kms_key_id              = aws_kms_key.main_key.arn
  recovery_window_in_days = 7

  tags = {
    Name = "${var.environment}-erp-app-secrets"
  }
}
