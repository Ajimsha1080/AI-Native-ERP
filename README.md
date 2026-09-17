# 🤖 Agentic ERP — Enterprise Multi-Tenant AI-Native ERP Platform

> **A production-grade, multi-tenant Agentic ERP platform built on FastAPI (Python 3.12+), PostgreSQL 16 with Row-Level Security (RLS), LangGraph multi-agent orchestration, SQLAlchemy 2.0 + Alembic, Redis, Celery, and Stripe.**

---

## 🌟 Key Platform Capabilities

### 1. 🏢 Multi-Tenancy & PostgreSQL Row-Level Security (RLS)
- **Database-Enforced Isolation**: Every business table carries `organization_id`. PostgreSQL Row-Level Security (RLS) policies restrict queries dynamically via `SET LOCAL app.tenant_id = :org_id` on every authenticated request transaction.
- **Cross-Tenant Leakage Prevention**: Formally verified via integration tests (`test_tenant_isolation.py`) proving Tenant A cannot read, query, or mutate Tenant B's data under any circumstance.

### 2. 🔐 Enterprise Authentication & RBAC
- **Argon2id Cryptographic Hashing**: Passwords hashed with `argon2-cffi` (`time_cost=2`, `memory_cost=64MB`, `parallelism=2`) exceeding OWASP guidelines, with transparent parameter re-hashing support.
- **JWT Access & Refresh Tokens**: Short-lived HS256 access tokens (30 min) carrying `sub`, `org_id`, and `role`, plus rotating long-lived refresh tokens (7 days).
- **Declarative RBAC Dependency**: Role enforcement (`require_role("owner", "admin", "manager", "viewer")`) applied cleanly at the route level via FastAPI dependencies.
- **Account Verification & Recovery**: Cryptographically signed email verification tokens and password reset workflows.

### 3. 📦 5 Core ERP Business Modules (Full CRUD, Validation & State Machines)
- **🏭 Inventory & WMS** (`/inventory`):
  - Products, warehouses, multi-warehouse stock levels, and immutable stock movement audit ledger.
  - **Business Rules**: Hard database CHECK and service-level constraints preventing negative stock (`quantity_on_hand >= 0` / `InsufficientStockError`).
- **💰 Sales & Invoicing** (`/sales`):
  - Customer accounts, Sales Orders (Draft → Confirmed → Shipped → Delivered), Invoices, and Payments.
  - **Business Rules**: `line_total = quantity * unit_price`, strict invoice validation (`total_amount == sum(lines.line_total)`), and automatic invoice status transition to `PAID` upon payment reconciliation.
- **🚚 Purchasing & Procurement** (`/purchasing`):
  - Approved vendor management, Purchase Orders (Draft → Sent → Acknowledged → Received), and Goods Receipts.
  - **Business Rules**: Goods receipts automatically generate corresponding incoming `StockMovement` records in inventory.
- **⚖️ Double-Entry Accounting & Ledger** (`/accounting`):
  - Hierarchical Chart of Accounts (Asset, Liability, Equity, Revenue, Expense) and Journal Entries.
  - **Business Rules**: Double-entry bookkeeping balance rule `sum(debit) == sum(credit)` strictly enforced before posting (`JournalImbalanceError`); single-side non-zero line constraints.
- **👥 Human Resources (HR)** (`/hr`):
  - Departments, Employees (with optional system User account linking), daily attendance records with automatic hours computation on checkout, and leave request approval workflows.

### 4. 🧠 LangGraph Multi-Agent Orchestration & Governance
- **Supervisor Routing**: LangGraph `StateGraph` supervisor dynamically classifies intent and routes queries to specialist agents (*Inventory*, *Sales*, *Purchasing*, *Finance*, *General*).
- **Typed Service Tools**: Every agent tool is a typed function invoking the same service layer that the REST API uses — zero raw SQL execution from agents.
- **Risk-Tier Human-in-the-Loop (HIL) Approvals** (`/approvals`):
  - Read-only tools auto-execute instantly.
  - High-risk write operations (financial disbursements, journal entries, and stock adjustments > 100 units) require human authorization in `/approvals`.
- **Audit Logging & Token Budgets**:
  - Full execution tracking in `agent_runs` and `tool_executions` (prompt, response, tokens, cost, latency).
  - Per-tenant monthly token budget enforcement (Free: 100k, Pro: 5M, Enterprise: 50M).

### 5. 💳 Stripe Subscriptions & Billing
- **Tiered Subscriptions**: Free, Pro, and Enterprise tiers.
- **Stripe Checkout**: Generates hosted Stripe Checkout sessions.
- **Idempotent Webhook Handler**: Signature-verified webhook processing updating organization subscription state.
- **Plan Limit Middleware**: Enforces plan-based API and agent usage quotas.

### 6. ⚡ Asynchronous Task Processing (Celery & Redis)
- Asynchronous valuation reports, sales revenue summaries, bulk product CSV imports, and background agent runs.
- Async job polling API (`GET /api/v1/jobs/{job_id}/status`).

### 7. 📊 Observability & DevOps
- **Structured JSON Logging**: `structlog` emitting structured JSON logs enriched with `request_id` and `tenant_id`.
- **Health & Readiness Probes**: `/health` (liveness) and `/ready` (database readiness probe).
- **Production Containerization**: Multi-stage `Dockerfile` and `docker-compose.yml` (PostgreSQL 16, Redis 7, FastAPI API, Celery Worker).
- **CI/CD Pipeline**: GitHub Actions running automated linting and tests against live PostgreSQL and Redis services.

---

## 🏗️ Architecture & Package Layout

```text
Agentic ERP Monorepo Structure:

├── apps/
│   ├── api/                   # FastAPI REST Gateway (Port 8000)
│   │   ├── main.py            # Lifespan hooks, middleware, router registry, /health & /ready
│   │   └── v1/routes/         # auth, inventory, sales, purchasing, accounting, hr, approvals, jobs, billing...
│   ├── web/                   # Next.js 16 App Router UI (Port 3000)
│   └── worker/                # Celery background workers (reports, imports, agent_runs)
│
├── packages/
│   ├── agents/                # LangGraph StateGraph, supervisor, specialist agents, approval manager
│   ├── auth/                  # argon2id hashing, JWT access/refresh tokens, RBAC dependencies
│   ├── billing/               # Stripe client, webhook verification, plan limit middleware
│   ├── database/              # SQLAlchemy 2.0 models, tenant context (Postgres RLS), Alembic migrations
│   │   └── models/erp/        # inventory, sales, purchasing, accounting, hr, agent_runs
│   ├── erp/                   # Layered ERP Domain Architecture
│   │   ├── repositories/      # Data access layer (inventory, sales, purchasing, accounting, hr)
│   │   └── services/          # Business rule validation layer
│   ├── observability/         # structlog structured JSON logging
│   └── schemas/               # Pydantic v2 request & response schemas
│
├── .github/workflows/ci.yml   # GitHub Actions CI pipeline
├── docker-compose.yml         # Postgres 16, Redis 7, API, Celery Worker
├── Dockerfile                 # Multi-stage production container
├── pytest.ini                 # Pytest configuration
├── requirements.txt           # Production dependencies
└── tests/integration/         # Integration test suite (17/17 tests passing)
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.12+** (Python 3.12, 3.13, 3.14 verified)
- **Node.js 18+** & `npm`
- **Docker** & **Docker Compose** (for PostgreSQL & Redis)

### 2. Environment Configuration
```bash
cp .env.example .env
```
Key configuration settings in `.env`:
```env
DATABASE_URL=postgresql+asyncpg://agentic_user:agentic_password@localhost:5432/agentic_platform
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-super-secret-security-key-at-least-32-chars
ENVIRONMENT=development
OPENAI_API_KEY=sk-proj-...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

---

### 3. Running with Docker Compose (Full Stack)

```bash
docker-compose up --build
```
Services started:
- 🐘 **PostgreSQL 16**: `localhost:5432`
- ⚡ **Redis 7**: `localhost:6379`
- 🚀 **FastAPI Backend API**: `http://localhost:8000`
- 💼 **Celery Worker**: Background task executor
- 🌐 **Next.js Web UI**: `http://localhost:3000`

---

### 4. Running Locally (Development Mode)

```powershell
# 1. Start Python FastAPI Gateway (Terminal 1)
$env:PYTHONPATH="."
python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

# 2. Start Celery Worker (Terminal 2)
$env:PYTHONPATH="."
celery -A apps.worker.celery worker --loglevel=info

# 3. Start Next.js Frontend (Terminal 3)
cd apps/web
npm install
npm run dev
```

- 🌐 **Frontend UI**: [http://localhost:3000](http://localhost:3000)
- ⚡ **Backend API**: [http://localhost:8000](http://localhost:8000)
- 📜 **Interactive Swagger Docs**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- ❤️ **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- 🔍 **Readiness Probe**: [http://localhost:8000/ready](http://localhost:8000/ready)

---

## 🧪 Automated Testing & Verification

The test suite validates all security boundaries, database invariants, and agent workflows:

```powershell
# Run the complete integration test suite (17/17 Passed)
pytest tests/integration/ -v
```

### Verified Test Suite Summary:

| Test Module | Coverage | Status |
| :--- | :--- | :---: |
| `test_tenant_isolation.py` | Proves cross-tenant data isolation under PostgreSQL RLS | ✅ **PASSED** |
| `test_auth.py` | Argon2id password hashing, JWT access/refresh token rotation & RBAC | ✅ **PASSED** |
| `test_inventory.py` | Product CRUD & strict non-negative stock constraint enforcement | ✅ **PASSED** |
| `test_accounting.py` | Balanced journal posting & rejection of imbalanced entries | ✅ **PASSED** |
| `test_sales.py` | Invoice line total validation (`total == sum(lines)`) & payment reconciliation | ✅ **PASSED** |
| `test_agent.py` | LangGraph supervisor routing & risk-tier approval gate enforcement | ✅ **PASSED** |
| `test_billing.py` | Stripe checkout session generation & verified webhook processing | ✅ **PASSED** |
| `test_agent_execution.py` | ReAct multi-turn loop, ChromaDB RAG scoping, & QuickBooks connector | ✅ **PASSED** |

---

## 📄 License & Support

Copyright © 2026. All rights reserved.  
Repository: [https://github.com/Ajimsha1080/Agentic-ERP-backend.git](https://github.com/Ajimsha1080/Agentic-ERP-backend.git)
