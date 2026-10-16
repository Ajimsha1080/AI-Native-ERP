# AWS ElastiCache Redis Cluster (Multi-AZ with In-Transit & At-Rest Encryption)

resource "aws_elasticache_subnet_group" "redis_subnet_group" {
  name        = "${var.environment}-redis-subnet-group"
  description = "Subnet group for private ElastiCache Redis replication cluster"
  subnet_ids  = [aws_subnet.data_1.id, aws_subnet.data_2.id]
}

resource "aws_elasticache_parameter_group" "redis7_params" {
  name        = "${var.environment}-redis7-params"
  family      = "redis7"
  description = "Redis 7 parameter group with maxmemory policy set for robust caching"

  parameter {
    name  = "maxmemory-policy"
    value = "volatile-lru"
  }
}

resource "random_password" "redis_auth_token" {
  length  = 32
  special = false
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id          = "${var.environment}-erp-redis"
  description                   = "Production Redis replication group for Celery broker & token blacklists"
  engine                        = "redis"
  engine_version                = "7.1"
  node_type                     = var.redis_node_type
  port                          = 6379
  parameter_group_name          = aws_elasticache_parameter_group.redis7_params.name
  subnet_group_name             = aws_elasticache_subnet_group.redis_subnet_group.name
  security_group_ids            = [aws_security_group.redis_sg.id]

  # High Availability & Multi-AZ
  automatic_failover_enabled    = true
  multi_az_enabled              = true
  num_cache_clusters            = 2

  # Security & Encryption
  at_rest_encryption_enabled    = true
  transit_encryption_enabled   = true
  kms_key_id                    = aws_kms_key.main_key.arn
  auth_token                    = random_password.redis_auth_token.result

  # Maintenance & Snapshots
  snapshot_retention_limit      = 7
  snapshot_window               = "02:00-03:00"
  maintenance_window            = "Sun:03:30-Sun:04:30"
  auto_minor_version_upgrade    = true

  tags = {
    Name = "${var.environment}-erp-redis"
  }
}
