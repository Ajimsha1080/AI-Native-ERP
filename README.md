# 🤖 AI-Native-ERP — Enterprise Multi-Tenant SaaS Platform

> **A launch-ready, enterprise-grade multi-tenant Agentic ERP platform built on FastAPI (Python 3.12+), PostgreSQL 16 with Row-Level Security (RLS), LangGraph multi-agent orchestration, SQLAlchemy 2.0 async + Alembic, Redis, Celery, Stripe, and Next.js 16.**

[![CI Quality Gates](https://github.com/Ajimsha1080/Agentic-ERP-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/Ajimsha1080/Agentic-ERP-backend/actions)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Security Policy](https://img.shields.io/badge/Security-ASVS%20L2%20Compliant-green.svg)](SECURITY.md)
[![Tests Passing](https://img.shields.io/badge/Tests-46%2F46%20Passing-brightgreen.svg)](tests/)

---

## 🌟 Architecture & Enterprise SaaS Foundations

### 1. 🏢 Tenant Isolation & PostgreSQL Row-Level Security (RLS)
- **Database Engine Kernel Enforcement**: Every business table carries `organization_id`. PostgreSQL Row-Level Security (RLS) policies dynamically isolate records via `SET LOCAL app.tenant_id = :org_id` inside each request transaction.
- **Unprivileged Connection Pool Role**: The application database pool connects under a dedicated unprivileged role (`app_user`) that cannot bypass RLS.
- **Zero Cross-Tenant Leakage**: Formally verified via integration suites (`test_tenant_isolation.py`), proving cross-tenant reads, writes, and pooled connection leakage are impossible.
- **Startup Table Assertions**: Automated assertion (`assert_rls_policies_active`) runs during startup and CI to verify that **all 45 tenant tables** have active RLS policies.

### 2. 🔐 Cryptographic Authentication Hardening & Real RBAC
- **Unified Auth Stack**: Consolidated under `packages/auth/` (legacy stacks deleted).
- **Argon2id Hashing**: Passwords hashed with salted Argon2id (`time_cost=2`, `memory_cost=64MB`, `parallelism=2`) exceeding OWASP ASVS standards.
- **Refresh Token Family Rotation & Reuse Detection**: Refresh tokens carry a `family_id` and unique `jti`. If a previously used refresh token is presented, the entire token family is immediately revoked to prevent session hijacking.
- **Single-Use Verification & Reset Tokens**: Password reset and email verification tokens carry unique `jti` identifiers tracked in the database and are strictly single-use.
- **Four-Tier Database RBAC**: Explicit membership roles (`owner`, `admin`, `manager`, `viewer`) stored in `organization_members`. Protected endpoints enforce `require_min_role`.
- **Owner Safeguards**: Demoting or deleting the last remaining Owner of an organization is strictly blocked at router and database levels.

### 3. 💳 Stripe Enterprise Billing & Quota Management
- **Cryptographic Webhook Verification**: Webhooks enforce HMAC-SHA256 signature verification via `STRIPE_WEBHOOK_SECRET` (startup fails fast outside tests if missing).
- **Idempotency Deduplication**: All webhook events are logged in `processed_stripe_events`; replayed events return `duplicate_skipped`.
- **Billing Portal & Grace Periods**: Self-service Stripe Customer Portal integration (`/api/v1/billing/portal`). Payment failures trigger a 7-day grace period before write operations and agent automation are gated.
- **Seat & Token Quotas**: Centralized `PlanLimitEnforcer` enforces seat caps (Free: 3, Pro: 20, Enterprise: 1,000) and monthly LLM token limits (Free: 100k, Pro: 5M, Enterprise: 50M).
- **Phishing Protection**: Redirect URLs (`success_url`, `cancel_url`) are validated against a strict domain allowlist.

### 4. 📦 5 Core ERP Modules & Business Invariants
- **🏭 Inventory & WMS** (`/inventory`): Multi-warehouse stock tracking, negative stock prevention (`InsufficientStockError`), immutable stock movement audits.
- **💰 Sales & Invoicing** (`/sales`): Customer accounts, Sales Orders, strict invoice arithmetic verification (`total == sum(line_total)`), automatic status transitions upon payment reconciliation.
- **🚚 Purchasing** (`/purchasing`): Approved vendor catalogues, Purchase Orders, and automatic stock movement generation on Goods Receipt.
- **⚖️ Double-Entry Accounting** (`/accounting`): General ledger and journal entries with strict double-entry balance enforcement (`sum(debit) == sum(credit)` / `JournalImbalanceError`).
- **👥 Human Resources** (`/hr`): Departments, Employees, automated daily hours computation on checkout, leave request approval workflows.

### 5. 🧠 LangGraph Multi-Agent Orchestration & Governance
- **StateGraph Supervisor Routing**: Routes user intent to specialist domain agents (Inventory, Sales, Purchasing, Finance).
- **Dual-Approval Financial Gates**: Transactions exceeding `$1,000.00` automatically divert to human manager/owner approval before ledger commit.
- **Typed Service Tools**: Agents interact solely via typed service functions matching REST API contracts — zero raw SQL execution.

### 6. 🛡️ Product Compliance, GDPR & Observability
- **GDPR Article 20 (Data Portability)**: Structured JSON data exports via `GET /api/v1/users/me/export` and `GET /api/v1/organizations/{id}/export`.
- **GDPR Article 17 (Right to be Forgotten)**: Self-service account deactivation and PII anonymization via `DELETE /api/v1/users/me`.
- **Immutable Audit Logging**: Admin and security events logged in `audit_events`.
- **Observability**: Official `prometheus-client` exposition (`/metrics`), Sentry APM, OpenTelemetry tracing, and correlation request IDs (`X-Request-ID`).
- **Web App Security Headers**: Strict Content Security Policy (`CSP`), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`.

---

## 🏗️ Repository Structure

```text
├── apps/
│   ├── api/                   # FastAPI REST API Gateway (Port 8000)
│   │   ├── main.py            # App lifespan, security middleware, Prometheus metrics, routers
│   │   └── v1/routes/         # auth, users, inventory, sales, purchasing, accounting, hr, billing...
│   ├── web/                   # Next.js 16 Web Application (Port 3000)
│   │   ├── e2e/               # Playwright end-to-end tests
│   │   └── src/app/           # App router pages, terms, privacy, dashboard
│   └── worker/                # Celery background worker
│       ├── celery.py          # Dynamic broker configuration (REDIS_URL / CELERY_BROKER_URL)
│       └── tasks/             # Health checks, reports, imports, background agent runs
│
├── packages/
│   ├── auth/                  # Unified JWT tokens, rotation, reuse detection, RBAC dependencies
│   ├── billing/               # Stripe client, webhook deduplication, PlanLimitEnforcer
│   ├── config/                # Pydantic Settings and security validation
│   ├── database/              # SQLAlchemy 2.0 async engine, TenantDB (SET LOCAL RLS)
│   │   ├── alembic/           # Alembic single migration source of truth (68 tables)
│   │   └── models/            # All ORM models (users, orgs, audit, billing, ERP)
│   ├── erp/                   # Domain services and repositories enforcing business rules
│   ├── rag/                   # PostgreSQL pgvector document store
│   └── security/              # Security middleware, audit logging service, guardrails
│
├── infra/
│   └── terraform/             # Production AWS IaC (VPC, RDS Multi-AZ, ElastiCache, ALB, WAF)
├── docs/
│   ├── legal/                 # Terms of Service & Privacy Policy
│   ├── runbooks/              # PostgreSQL Backup, Restore & PITR runbook
│   └── security/              # OWASP ASVS L2 self-audit report
├── tests/
│   └── integration/           # Pytest integration test suite (46/46 passed)
├── scripts/
│   ├── seed_demo.py           # Explicit CLI seed script (refuses in prod/staging)
│   └── smoke_test.py          # End-to-end verification script
├── docker-compose.yml         # Full-stack orchestrator (db, redis, migrate, api, worker, web)
└── Dockerfile                 # Hardened non-root production container
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.12+**
- **Node.js 20+** & `npm`
- **Docker** & **Docker Compose**

### 2. Environment Setup
```bash
cp .env.example .env
```

### 3. Running with Docker Compose (Full Stack)
```bash
docker compose up --build
```
Services started:
- 🐘 **PostgreSQL 16**: `localhost:5432`
- ⚡ **Redis 7**: `localhost:6379`
- 🔄 **Alembic Migrate**: One-shot migration job
- 🚀 **FastAPI Backend**: `http://localhost:8000`
- 💼 **Celery Worker**: Background task executor
- 🌐 **Next.js Web UI**: `http://localhost:3000`

### 4. Running the Smoke Test
```bash
python scripts/smoke_test.py
```
Validates the complete signup → verify → login → create product → agent chat flow.

---

## 🧪 Automated Testing & Verification

The test suite validates all security boundaries, database invariants, and agent workflows:

```bash
pytest
```

### Test Suite Execution Results (100% Passing)

| Test Module | Coverage | Status |
| :--- | :--- | :---: |
| `test_alembic_migrations.py` | Validates clean DB migration yields schema matching all models | ✅ **1/1 PASSED** |
| `test_auth_hardening.py` | Refresh token reuse detection, single-use reset, lockout/backoff | ✅ **7/7 PASSED** |
| `test_billing.py` | Stripe checkout session generation & verified webhook processing | ✅ **6/6 PASSED** |
| `test_billing_phase3.py` | Webhook idempotency, customer lookup, grace period & plan limits | ✅ **6/6 PASSED** |
| `test_connectors.py` | External ERP data connectors & synchronization | ✅ **7/7 PASSED** |
| `test_database_config.py` | Multi-tenant DB session configuration & dialect verification | ✅ **4/4 PASSED** |
| `test_erp_business_rules.py` | Negative stock prevention, balanced journal entries & approval gates | ✅ **3/3 PASSED** |
| `test_gdpr_audit.py` | GDPR Article 17 self-deletion, Article 20 data export & audit trails | ✅ **1/1 PASSED** |
| `test_rbac_matrix.py` | Complete RBAC matrix across all roles & Owner safeguard checks | ✅ **1/1 PASSED** |
| `test_tenant_isolation.py` | Proves cross-tenant data isolation under PostgreSQL RLS | ✅ **3/3 PASSED** |
| `test_webhook_edge_cases.py` | Missing/invalid signature rejection, replay deduplication | ✅ **2/2 PASSED** |
| `test_worker_tasks.py` | Celery background jobs & health check tasks | ✅ **5/5 PASSED** |
| **TOTAL** | **Comprehensive Full-Stack Integration Suite** | ✅ **46/46 PASSED (100%)** |

---

## 📄 Documentation & Compliance

- [Security Policy & Vulnerability Disclosure](SECURITY.md)
- [OWASP ASVS Level 2 Self-Audit](docs/security/OWASP_ASVS_L2_AUDIT.md)
- [Database Backup & Disaster Recovery Runbook](docs/runbooks/backup_restore.md)
- [Terms of Service](docs/legal/TERMS_OF_SERVICE.md)
- [Privacy Policy](docs/legal/PRIVACY_POLICY.md)
- [Known Limitations](KNOWN_LIMITATIONS.md)
- [License](LICENSE)
