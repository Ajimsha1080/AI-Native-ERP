variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS deployment region"
}

variable "environment" {
  type        = string
  default     = "production"
  description = "Deployment environment name (production, staging)"
}

variable "vpc_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "VPC CIDR block"
}

variable "db_instance_class" {
  type        = string
  default     = "db.r6g.xlarge"
  description = "RDS PostgreSQL compute instance class"
}

variable "db_allocated_storage" {
  type        = number
  default     = 100
  description = "Allocated storage in GB for PostgreSQL"
}

variable "db_max_allocated_storage" {
  type        = number
  default     = 1000
  description = "Auto-scaling maximum storage in GB"
}

variable "redis_node_type" {
  type        = string
  default     = "cache.r6g.large"
  description = "ElastiCache Redis node type"
}

variable "domain_name" {
  type        = string
  default     = "erp.example.com"
  description = "Apex domain name for the application"
}

variable "acm_certificate_arn" {
  type        = string
  default     = "arn:aws:acm:us-east-1:123456789012:certificate/placeholder"
  description = "ARN of validated AWS ACM TLS certificate for HTTPS listener"
}

variable "alarm_email" {
  type        = string
  default     = "devops-alerts@example.com"
  description = "Email address to receive CloudWatch alerts"
}
