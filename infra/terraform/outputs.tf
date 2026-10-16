# Terraform Output Variables

output "vpc_id" {
  description = "VPC Identifier"
  value       = aws_vpc.main.id
}

output "alb_dns_name" {
  description = "Application Load Balancer DNS Name"
  value       = aws_lb.main_alb.dns_name
}

output "rds_endpoint" {
  description = "PostgreSQL Primary Database Endpoint"
  value       = aws_db_instance.postgresql.endpoint
}

output "redis_primary_endpoint" {
  description = "ElastiCache Redis Primary Endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "secrets_manager_arn" {
  description = "Secrets Manager ARN for Application Configuration"
  value       = aws_secretsmanager_secret.app_secrets.arn
}

output "api_ecr_url" {
  description = "FastAPI Backend ECR Repository URL"
  value       = aws_ecr_repository.api_repo.repository_url
}

output "web_ecr_url" {
  description = "Next.js Web Frontend ECR Repository URL"
  value       = aws_ecr_repository.web_repo.repository_url
}
