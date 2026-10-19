# AWS Production Deployment Runbook

This guide provides step-by-step instructions for deploying the **AI-Native Agentic ERP Platform** to Amazon Web Services (AWS) using our pre-written Terraform Infrastructure-as-Code (IaC), Docker container images, and Amazon ECS Fargate orchestration.

---

## 🏛️ Architecture Overview

The platform uses a hardened, multi-tier, high-availability architecture across multiple Availability Zones:

```text
                                [ Internet Users ]
                                        │
                                        ▼ (HTTPS: 443 / WAF Protected)
                             [ AWS WAFv2 Web ACL ]
                                        │
                        [ Application Load Balancer (ALB) ]
                         ├── /api/*, /health ──► [ FastAPI Backend Target Group ]
                         └── /*              ──► [ Next.js Web Target Group ]
                                        │
           ┌────────────────────────────┴────────────────────────────┐
           ▼ (Private App Subnets)                                   ▼
 [ ECS Fargate API Tasks ]                                 [ ECS Fargate Web Tasks ]
 (Auto-scaling: 2 - 10 tasks)                              (Auto-scaling: 2 - 6 tasks)
           │
           ├────────────────────────────┐
           ▼                            ▼ (Private App Subnet)
 [ ECS Celery Worker Tasks ]   [ AWS Secrets Manager + KMS ]
           │
           ├─────────────────────────────────────────┐
           ▼ (Private Data Subnets)                  ▼ (Private Data Subnets)
 [ RDS PostgreSQL 16 (Multi-AZ) ]          [ ElastiCache Redis 7 Cluster ]
 (pgvector + Row-Level Security RLS)        (In-transit & At-rest Encryption)
```

---

## 📋 Prerequisites

Before starting deployment, ensure you have:

1. **AWS CLI v2** installed and configured:
   ```bash
   aws configure
   ```
2. **Terraform >= 1.5.0** installed.
3. **Docker** installed for building and pushing container images.
4. An active **Domain Name** managed in AWS Route 53 with an **ACM TLS Certificate**.

---

## 🚀 Deployment Steps

### Step 1: Initialize and Apply Terraform Infrastructure

Navigate to the `infra/terraform` directory:

```bash
cd infra/terraform
```

1. **Initialize Terraform & Remote S3 State**:
   ```bash
   terraform init
   ```
   *(Ensure the S3 bucket and DynamoDB lock table specified in `main.tf` exist, or use a local backend for initial testing).*

2. **Plan Infrastructure**:
   ```bash
   terraform plan -var="environment=production" -var="acm_certificate_arn=arn:aws:acm:us-east-1:YOUR_ACCOUNT_ID:certificate/YOUR_CERT_ID" -out=tfplan
   ```

3. **Provision Resources**:
   ```bash
   terraform apply tfplan
   ```

Outputs will display:
- `alb_dns_name`: Public URL of the load balancer.
- `rds_endpoint`: PostgreSQL connection endpoint.
- `redis_primary_endpoint`: Redis cache endpoint.
- `api_ecr_url`: ECR repository for the FastAPI API.
- `web_ecr_url`: ECR repository for the Next.js frontend.
- `secrets_manager_arn`: Application secrets vault.

---

### Step 2: Configure Application Secrets in AWS Secrets Manager

Populate the secrets template created by Terraform:

```bash
aws secretsmanager put-secret-value \
  --secret-id "production/agentic-erp/app-secrets" \
  --secret-string '{
    "DATABASE_URL": "postgresql+asyncpg://postgres:YOUR_DB_PASSWORD@YOUR_RDS_ENDPOINT:5432/agentic_platform",
    "SECRET_KEY": "YOUR_STRONG_CRYPTOGRAPHIC_KEY_MIN_32_CHARS",
    "REDIS_URL": "rediss://YOUR_REDIS_ENDPOINT:6379/0",
    "STRIPE_SECRET_KEY": "sk_live_...",
    "STRIPE_WEBHOOK_SECRET": "whsec_...",
    "OPENAI_API_KEY": "sk-...",
    "LANGCHAIN_API_KEY": "lsv2_pt_..."
  }'
```

---

### Step 3: Build & Push Container Images to Amazon ECR

1. **Authenticate Docker with Amazon ECR**:
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(terraform output -raw api_ecr_url | cut -d/ -f1)
   ```

2. **Build and Push Backend API Image**:
   ```bash
   # From repository root
   docker build -t $(terraform output -raw api_ecr_url):latest .
   docker push $(terraform output -raw api_ecr_url):latest
   ```

3. **Build and Push Frontend Web Image**:
   ```bash
   docker build -t $(terraform output -raw web_ecr_url):latest ./apps/web
   docker push $(terraform output -raw web_ecr_url):latest
   ```

---

### Step 4: Run Initial Database Migrations (Alembic)

Run the one-off Alembic migration task on ECS Fargate to prepare all 68 tenant tables and RLS policies:

```bash
aws ecs run-task \
  --cluster production-agentic-erp-cluster \
  --task-definition production-erp-api \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[SUBNET_ID],securityGroups=[APP_SG_ID],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides": [{"name": "api", "command": ["alembic", "upgrade", "head"]}]}'
```

---

### Step 5: Trigger Zero-Downtime ECS Rolling Deployments

Force deployment so the running ECS tasks pull the newly published images:

```bash
aws ecs update-service --cluster production-agentic-erp-cluster --service production-erp-api-service --force-new-deployment
aws ecs update-service --cluster production-agentic-erp-cluster --service production-erp-web-service --force-new-deployment
aws ecs update-service --cluster production-agentic-erp-cluster --service production-erp-worker-service --force-new-deployment
```

---

### Step 6: Post-Deployment Smoke Tests & Health Check

1. **ALB Public Health Check**:
   ```bash
   curl -I https://<YOUR_ALB_DNS_OR_DOMAIN>/health
   # Expected: HTTP/2 200 OK
   ```

2. **LangSmith Tracing Diagnostic**:
   ```bash
   curl -s -H "Authorization: Bearer <ADMIN_JWT>" https://<YOUR_DOMAIN>/api/v1/compliance/langsmith/status | jq .
   ```

3. **Prometheus Telemetry Metrics**:
   ```bash
   curl -s https://<YOUR_DOMAIN>/metrics | head -n 20
   ```

---

## 🔄 Automated CI/CD Deployment with GitHub Actions

The repository includes [`.github/workflows/deploy-aws.yml`](../../.github/workflows/deploy-aws.yml). Every push to `main` automatically:
1. Builds both backend and frontend container images.
2. Pushes versioned tags to AWS ECR.
3. Automatically triggers Alembic database migrations.
4. Executes zero-downtime rolling updates on ECS Fargate.
5. Verifies end-to-end health check status on the ALB.
