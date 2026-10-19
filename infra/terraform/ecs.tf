# AWS ECS Fargate Infrastructure Definition
# Auto-scaling multi-container orchestration for FastAPI API, Next.js Web, and Celery Worker

# ------------------------------------------------------------------------------
# 1. ECS CLUSTER & LOGGING
# ------------------------------------------------------------------------------

resource "aws_ecs_cluster" "main" {
  name = "${var.environment}-agentic-erp-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.environment}-agentic-erp-cluster"
  }
}

# CloudWatch Log Groups for Container Stdout/Stderr
resource "aws_cloudwatch_log_group" "ecs_api" {
  name              = "/ecs/${var.environment}-agentic-erp-api"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.main_key.arn

  tags = {
    Name = "${var.environment}-ecs-api-logs"
  }
}

resource "aws_cloudwatch_log_group" "ecs_web" {
  name              = "/ecs/${var.environment}-agentic-erp-web"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.main_key.arn

  tags = {
    Name = "${var.environment}-ecs-web-logs"
  }
}

resource "aws_cloudwatch_log_group" "ecs_worker" {
  name              = "/ecs/${var.environment}-agentic-erp-worker"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.main_key.arn

  tags = {
    Name = "${var.environment}-ecs-worker-logs"
  }
}

# ------------------------------------------------------------------------------
# 2. IAM ROLES (Least Privilege Execution & Task Roles)
# ------------------------------------------------------------------------------

# Execution Role: Pulls images from ECR and retrieves secrets from Secrets Manager
resource "aws_iam_role" "ecs_execution_role" {
  name = "${var.environment}-ecs-execution-role"

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
    Name = "${var.environment}-ecs-execution-role"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution_standard" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow ECS agent to read Secrets Manager secrets and decrypt with KMS
resource "aws_iam_policy" "ecs_secrets_access" {
  name        = "${var.environment}-ecs-secrets-policy"
  description = "Allows ECS tasks to read encrypted application secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [aws_secretsmanager_secret.app_secrets.arn]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt"
        ]
        Resource = [aws_kms_key.main_key.arn]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_secrets_attach" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = aws_iam_policy.ecs_secrets_access.arn
}

# Task Role: Permissions used by the running application itself (S3, SES, etc.)
resource "aws_iam_role" "ecs_task_role" {
  name = "${var.environment}-ecs-task-role"

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
    Name = "${var.environment}-ecs-task-role"
  }
}

# ------------------------------------------------------------------------------
# 3. ECS TASK DEFINITIONS (Fargate)
# ------------------------------------------------------------------------------

# 1. FastAPI API Backend
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.environment}-erp-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${aws_ecr_repository.api_repo.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "LOG_LEVEL", value = "INFO" },
        { name = "STRUCTLOG_FORMAT", value = "json" },
        { name = "PROMETHEUS_ENABLED", value = "true" },
        { name = "LANGCHAIN_TRACING_V2", value = "true" },
        { name = "LANGCHAIN_PROJECT", value = "AI-Native-ERP" }
      ]

      secrets = [
        { name = "DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:DATABASE_URL::" },
        { name = "SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:SECRET_KEY::" },
        { name = "REDIS_URL", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:REDIS_URL::" },
        { name = "STRIPE_SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:STRIPE_SECRET_KEY::" },
        { name = "STRIPE_WEBHOOK_SECRET", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:STRIPE_WEBHOOK_SECRET::" },
        { name = "OPENAI_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:OPENAI_API_KEY::" }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_api.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "api"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 15
      }
    }
  ])

  tags = {
    Name = "${var.environment}-erp-api-task"
  }
}

# 2. Next.js Web Frontend
resource "aws_ecs_task_definition" "web" {
  family                   = "${var.environment}-erp-web"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "web"
      image     = "${aws_ecr_repository.web_repo.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 3000
          hostPort      = 3000
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "NODE_ENV", value = "production" },
        { name = "PORT", value = "3000" }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_web.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "web"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:3000/ || exit 1"]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    }
  ])

  tags = {
    Name = "${var.environment}-erp-web-task"
  }
}

# 3. Celery Background Worker
resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.environment}-erp-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = "${aws_ecr_repository.api_repo.repository_url}:latest"
      essential = true
      command   = ["celery", "-A", "apps.worker.celery", "worker", "--loglevel=info", "--concurrency=4"]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "LOG_LEVEL", value = "INFO" }
      ]

      secrets = [
        { name = "DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:DATABASE_URL::" },
        { name = "SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:SECRET_KEY::" },
        { name = "REDIS_URL", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:REDIS_URL::" },
        { name = "OPENAI_API_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:OPENAI_API_KEY::" }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])

  tags = {
    Name = "${var.environment}-erp-worker-task"
  }
}

# ------------------------------------------------------------------------------
# 4. ECS SERVICES (Zero-Downtime Rolling Deployment)
# ------------------------------------------------------------------------------

# 1. API Service
resource "aws_ecs_service" "api" {
  name            = "${var.environment}-erp-api-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  network_configuration {
    subnets          = [aws_subnet.app_1.id, aws_subnet.app_2.id]
    security_groups  = [aws_security_group.app_sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api_tg.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.https]

  tags = {
    Name = "${var.environment}-erp-api-service"
  }
}

# 2. Web Service
resource "aws_ecs_service" "web" {
  name            = "${var.environment}-erp-web-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.web.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  network_configuration {
    subnets          = [aws_subnet.app_1.id, aws_subnet.app_2.id]
    security_groups  = [aws_security_group.app_sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.web_tg.arn
    container_name   = "web"
    container_port   = 3000
  }

  depends_on = [aws_lb_listener.https]

  tags = {
    Name = "${var.environment}-erp-web-service"
  }
}

# 3. Worker Service
resource "aws_ecs_service" "worker" {
  name            = "${var.environment}-erp-worker-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.app_1.id, aws_subnet.app_2.id]
    security_groups  = [aws_security_group.app_sg.id]
    assign_public_ip = false
  }

  tags = {
    Name = "${var.environment}-erp-worker-service"
  }
}

# ------------------------------------------------------------------------------
# 5. AUTO-SCALING POLICIES (Target Tracking)
# ------------------------------------------------------------------------------

# API Service Auto-scaling
resource "aws_appautoscaling_target" "api_target" {
  max_capacity       = 10
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu_policy" {
  name               = "${var.environment}-api-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api_target.resource_id
  scalable_dimension = aws_appautoscaling_target.api_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

resource "aws_appautoscaling_policy" "api_memory_policy" {
  name               = "${var.environment}-api-memory-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api_target.resource_id
  scalable_dimension = aws_appautoscaling_target.api_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    target_value       = 75.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# Web Service Auto-scaling
resource "aws_appautoscaling_target" "web_target" {
  max_capacity       = 6
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.web.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "web_cpu_policy" {
  name               = "${var.environment}-web-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.web_target.resource_id
  scalable_dimension = aws_appautoscaling_target.web_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.web_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
