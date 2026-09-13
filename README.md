# 🤖 Agentic ERP — Enterprise Multi-Agent Operating System

> **A production-ready, zero-hallucination, agentic ERP platform powering multi-agent enterprise automation, real-time data integration, and human-in-the-loop financial governance.**

---

## 🌟 Key Platform Capabilities

- **🤖 8 Specialized Autonomous Domain Agents**:
  - **Finance Agent**: P&L variance, overdue AR collections, cash runway, ledger reconciliation.
  - **Inventory Agent**: SKU velocity, stockout risk prediction, WMS reorder points.
  - **Procurement Agent**: Supplier RFQ comparison, purchase order (PO) drafting, contract terms.
  - **Sales Agent**: CRM deal pipeline tracking, win/loss variance, customer churn alerts.
  - **Operations Agent**: Logistics SLA tracking, active freight shipment watch, delay alerts.
  - **HR Agent**: Automated payroll calculations, employee onboarding verification, policy enforcement.
  - **Analytics Agent**: Cross-functional BI digests, real-time LLM token counter, hours saved metrics.
  - **Compliance Agent**: GDPR retention audits, Zero-Trust RBAC access enforcement, immutable audit trails.
  - **Master Agent Orchestrator**: Intent classification & multi-node task routing via the AI Command Center.

- **📁 Company Knowledge Base & RAG Engine** (`/knowledge`):
  - **Native File Upload Dropzone**: Interactive `<input type="file">` selector supporting `.pdf`, `.docx`, `.csv`, `.xlsx`, `.txt`, and `.md` formats.
  - **Semantic Vector Chunking**: Documents are parsed and indexed with vector embeddings for sub-10ms similarity search.
  - **Departmental Access Scoping**: Restrict knowledge documents to specific domain agents (*Global*, *Finance Only*, *Compliance Only*).

- **🧠 Dual-Layer Agent Memory Engine** (`packages/agents/memory.py`):
  - **Short-Term Conversational Buffer**: Preserves active chat turns for seamless multi-turn follow-ups.
  - **Long-Term Episodic Memory**: Remembers past executive decisions, vendor preferences, and approved PO thresholds across user sessions.

- **🛡️ Enterprise AI Guardrails & Anti-Hallucination Engine** (`packages/security/guardrails.py`):
  - **Zero Temperature Math**: Forces `temperature = 0.0` for all ERP financial and inventory queries.
  - **Strict Source Grounding**: Every answer is verified against real ERP database records (`SAP S/4HANA`, `QuickBooks`, `Salesforce`).
  - **Prompt Injection Defense**: Intercepts jailbreaks and system override attacks.
  - **PII Redaction Engine**: Masks credit card numbers, SSNs, passwords, and secret API tokens.
  - **Human-in-the-Loop Threshold Enforcement**: Automatically intercepts any monetary disbursement exceeding **$1,000.00** for human accountant authorization in `/approvals`.

- **🔗 UI-Driven Integrations & Connectors Hub** (`/connectors`):
  - Real-time connector cards powered by `GET /api/v1/connectors/available`.
  - Native integration cards for **SAP S/4HANA**, **Salesforce CRM**, **Shopify Store**, **QuickBooks Online**, **Oracle NetSuite**, and **Custom REST APIs**.
  - Instant **`[+ Connect Stream]`** workflow wizard to bind OAuth credentials and assign routing agents.

- **🧹 Zero Mock Data Standard**:
  - All dashboards start at clean baseline zero metrics (`0` tasks completed, `100%` success rate, `0ms` vector retrieval).
  - Metrics populate dynamically from live ERP streams and user actions.

---

## 🏗️ Monorepo Architecture Overview

```text
Agentic ERP Monorepo Structure:

├── apps/
│   ├── web/               # Next.js 16 App Router (Turbopack) UI Workspace (Port 3000)
│   │   └── src/app/       # 20 Production Static & Dynamic Prerendered Routes
│   ├── api/               # FastAPI REST Gateway & Endpoint Controllers (Port 8000)
│   │   ├── main.py        # Application Entry Point & Router Mounts
│   │   └── v1/            # API v1 REST & SSE Chat Routers
│   └── worker/            # Celery Background Task Workers & Data Pipelines
│
├── packages/
│   ├── agents/            # Core ReAct Agents & Memory Engine (base.py, memory.py, api.py)
│   ├── connectors/        # Enterprise ERP Connectors (generic_rest.py, base.py)
│   ├── security/          # Guardrails & Safety Engine (guardrails.py)
│   ├── tools/             # Domain Tools (erp_tools.py)
│   ├── database/          # SQLAlchemy Models, Core Engine, & Alembic Migrations
│   ├── models/            # Pydantic Request/Response Data Schemas
│   └── rag/               # Document Embeddings & Vector Search Indexing
│
├── infra/
│   ├── docker/            # Production Docker & Docker Compose Configurations
│   ├── kubernetes/        # K8s Deployment & Service Manifests
│   └── terraform/         # Infrastructure as Code (AWS RDS, App Runner)
│
├── docker-compose.yml     # Multi-Container Deployment Orchestrator (Ports 80 & 8000)
├── mock_api.py            # Local Developer Gateway Server (Port 8000)
├── requirements.txt       # Production PyPI Dependencies
└── tests/
    ├── unit/              # Automated Security & Guardrail Unit Tests (pytest)
    └── integration/       # API Gateway & Connector Integration Tests
```

---

## 🧭 Full Web UI Route Sitemap

| Route | Page Name | Description |
|---|---|---|
| `/` | **AI Command Center** | Natural language executive copilot with real-time agent routing. |
| `/agents` | **AI Workforce Hub** | Status, success rates, and pause/resume controls for all 8 domain agents. |
| `/agents/[id]` | **Agent Control Center** | Detailed prompt configuration, dynamic domain tools, and boot logs. |
| `/finance` | **Finance & Treasury** | Real-time P&L analytics, cash flow streams, and ledger tables. |
| `/inventory` | **Inventory & WMS** | SKU stock velocity, reorder point triggers, and warehouse status. |
| `/procurement` | **Procurement & POs** | Supplier RFQ comparisons and purchase order drafting modal. |
| `/sales` | **Sales & CRM** | Opportunity pipeline tracker, deal velocity, and revenue forecasts. |
| `/operations` | **Operations & Freight**| Active shipment tracker, delay alerts, and logistics routes. |
| `/approvals` | **Approvals Queue** | Human-in-the-loop authorization for actions > $1,000.00. |
| `/knowledge` | **Knowledge Base** | RAG document manager with file upload dropzone and vector search stats. |
| `/connectors` | **Connectors Hub** | Enterprise data stream manager for SAP, Salesforce, Shopify, etc. |
| `/activity` | **Agent Activity** | Real-time event log of all autonomous agent actions. |
| `/audit` | **Audit Trail** | Immutable security logs of human and AI events across systems. |
| `/security` | **Security Matrix** | Zero-Trust RBAC policies, prompt injection filters, and PII masking. |
| `/billing` | **Usage & Billing** | LLM token consumption meter and subscription management. |
| `/analytics` | **Analytics & BI** | Platform metrics, token graphs, and hours saved calculations. |
| `/workflows` | **Workflows** | Multi-agent autonomous pipeline orchestrator. |
| `/settings` | **Settings** | Organization profiles, theme settings, and API credentials. |

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Python 3.10+** (Python 3.11 / 3.14 verified)
- **Node.js 18+** & `npm`
- **Git**

### 2. Environment Configuration
Copy the example environment file and configure your keys:

```bash
cp .env.example .env
```

```env
OPENAI_API_KEY=sk-proj-your-api-key-here
SECRET_KEY=your-super-secret-security-key
DATABASE_URL=sqlite:///agents.db
ENVIRONMENT=development
```

---

### 3. Running Locally

#### Option A: Native Dual-Server Mode (Fast Development)

```powershell
# 1. Start Python API Gateway (Terminal 1)
$env:PYTHONPATH="."
python mock_api.py

# 2. Start Next.js 16 Web Dashboard (Terminal 2)
cd apps/web
npm install
npm run dev
```

- 🌐 **Frontend UI**: [http://localhost:3000](http://localhost:3000)
- ⚡ **Backend API**: [http://localhost:8000](http://localhost:8000)
- 📜 **Swagger OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

#### Option B: Multi-Container Docker Compose

```bash
docker compose up -d --build
```

---

## ☁️ AWS EC2 Production Deployment Guide

### 1. Connect to EC2 Server
```bash
ssh -i "your-key.pem" ubuntu@your-ec2-ip
```

### 2. Expand Root Storage (AWS Free 30 GB EBS)
AWS free tier provides up to 30 GB storage at `$0.00` cost. Expand your root partition:
```bash
sudo growpart /dev/nvme0n1 1
sudo resize2fs /dev/nvme0n1p1
```

### 3. Deploy Latest Code via Docker Compose
```bash
cd ~/Agentic-ERP-backend
git pull https://github.com/Ajimsha1080/Agentic-ERP-backend.git main
sudo docker compose up -d --build
```

Once running, access your site at **`http://your-ec2-ip`** (Port 80) and **`http://your-ec2-ip:8000`** (FastAPI Gateway).

---

## 🧪 Testing & Quality Assurance

All suites pass with **0 errors**:

```powershell
# 1. Compile all Python backend files (0 Errors)
python -m compileall apps packages mock_api.py

# 2. Run automated security guardrail unit tests (6/6 Passed)
$env:PYTHONPATH="."
pytest tests/unit/test_security.py

# 3. Compile Next.js 16 production build (20/20 Routes Prerendered)
cd apps/web
npm run build
```

---

## 📄 License & Support

Copyright © 2026. All rights reserved.  
Repository: [https://github.com/Ajimsha1080/Agentic-ERP-backend.git](https://github.com/Ajimsha1080/Agentic-ERP-backend.git)
