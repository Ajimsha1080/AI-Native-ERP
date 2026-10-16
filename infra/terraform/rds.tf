# AWS RDS PostgreSQL Multi-AZ Highly Available Database

resource "aws_db_subnet_group" "rds_subnet_group" {
  name        = "${var.environment}-rds-subnet-group"
  description = "Subnet group for private isolated PostgreSQL database"
  subnet_ids  = [aws_subnet.data_1.id, aws_subnet.data_2.id]

  tags = {
    Name = "${var.environment}-rds-subnet-group"
  }
}

resource "aws_db_parameter_group" "postgres16_pg" {
  name        = "${var.environment}-pg16-params"
  family      = "postgres16"
  description = "PostgreSQL 16 parameter group with optimized RLS and pgvector settings"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements,pgvector"
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

resource "random_password" "db_master_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_db_instance" "postgresql" {
  identifier                  = "${var.environment}-agentic-erp-postgres"
  engine                      = "postgres"
  engine_version              = "16.3"
  instance_class              = var.db_instance_class
  allocated_storage           = var.db_allocated_storage
  max_allocated_storage       = var.db_max_allocated_storage
  storage_type                = "gp3"
  iops                        = 3000
  storage_throughput          = 125

  # Security & Encryption (Private, KMS encrypted)
  publicly_accessible        = false
  storage_encrypted           = true
  kms_key_id                  = aws_kms_key.main_key.arn
  vpc_security_group_ids      = [aws_security_group.rds_sg.id]
  db_subnet_group_name        = aws_db_subnet_group.rds_subnet_group.name
  parameter_group_name        = aws_db_parameter_group.postgres16_pg.name

  # Reliability & High Availability (Multi-AZ & Backups)
  multi_az                    = true
  backup_retention_period     = 30
  backup_window               = "03:00-04:00"
  maintenance_window          = "Sun:04:30-Sun:05:30"
  copy_tags_to_snapshot       = true
  deletion_protection         = var.environment == "production" ? true : false
  skip_final_snapshot         = var.environment == "production" ? false : true
  final_snapshot_identifier   = "${var.environment}-agentic-erp-final-snapshot"

  # Performance & Monitoring
  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  performance_insights_kms_key_id       = aws_kms_key.main_key.arn
  monitoring_interval                   = 60
  auto_minor_version_upgrade            = true

  # Database Credentials
  db_name  = "agentic_platform"
  username = "erp_admin"
  password = random_password.db_master_password.result

  tags = {
    Name = "${var.environment}-agentic-erp-postgres"
  }
}
