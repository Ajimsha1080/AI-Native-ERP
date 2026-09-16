# 🤖 Agentic ERP — Enterprise Multi-Agent Operating System

> **An enterprise-grade, agentic ERP backend platform powering autonomous ReAct multi-agent orchestration, persistent ChromaDB RAG, database-backed RBAC tool enforcement, and human-in-the-loop financial governance.**

---

## 🌟 Key Platform Capabilities

- **🤖 Autonomous Domain Agents & ReAct Core** (`packages/agents/base.py`):
  - **Multi-Turn Function Calling**: Real OpenAI / Anthropic tool loop with deterministic offline fallback executing live ERP methods (`get_inventory`, `create_purchase_order`, `get_customers`, `create_invoice`, `check_revenue`).
  - **Master Agent Orchestrator** (`apps/api/v1/chat.py`): Real intent classification and automatic routing to specialized domain agents (*Finance Agent*, *Inventory Agent*, *Procurement Agent*, *Master ERP Orchestrator*).
  - **Dual-Layer Agent Memory** (`packages/agents/memory.py`): Short-term conversational buffer maintaining active chat history per session and long-term memory for executive decisions.

- **📁 Company Knowledge Base & RAG Engine** (`packages/rag/vector_store.py` & `/knowledge`):
  - **Native File Upload Dropzone**: Interactive `<input type="file">` selector supporting `.pdf`, `.docx`, `.csv`, `.xlsx`, `.txt`, and `.md` formats.
  - **Persistent ChromaDB Vector Store**: Text chunking, 384-dimensional semantic embedding generation, and cosine similarity ranking.
  - **Departmental Access Scoping**: Restrict knowledge retrieval to specific domain scopes (*Global*, *Finance Only*, *Compliance Only*).

- **🛡️ Enterprise AI Guardrails & Anti-Hallucination Engine** (`packages/security/guardrails.py`):
  - **Zero Temperature Math**: Forces `temperature = 0.0` for all ERP financial and inventory queries.
  - **Strict Source Grounding**: Every answer is verified with evidence citations and numerical fact verification.
  - **Prompt Injection Defense**: Intercepts jailbreaks, delimiter smuggling, and instruction reset attacks.
  - **PII Redaction Engine**: Masks credit card numbers, SSNs, passwords, and secret API tokens.
  - **Human-in-the-Loop Threshold Enforcement**: Automatically intercepts any monetary disbursement exceeding **$1,000.00** for human authorization in `/approvals`.

- **🔐 Database-Backed RBAC Policy Checks** (`packages/tools/erp_tools.py`):
  - Fail-closed permission checking verifying `AgentTool` and `Tool` permission levels (`READ`, `WRITE`, `EXECUTE`, `APPROVE`).

- **🔗 Integrations & Connectors Hub** (`/connectors`):
  - **Live Connectors**: **Intuit QuickBooks Online** (OAuth 2.0 token injection, live invoice/customer querying) and **Generic REST API** connector (`httpx.AsyncClient`).
  - **Additional Adapters**: SAP S/4HANA, Salesforce CRM, Shopify Store, and Oracle NetSuite adapters in progress.

---

## 🏗️ Monorepo Architecture Overview

```text
Agentic ERP Monorepo Structure:

├── apps/
│   ├── web/               # Next.js 16 App Router (Turbopack) UI Workspace (Port 3000)
│   │   └── src/app/       # 20 Production Static & Dynamic Prerendered Routes
│   ├── api/               # FastAPI REST Gateway & Endpoint Controllers (Port 8000)
│   │   ├── main.py        # Application Entry Point & Lifespan Hooks
│   │   └── v1/            # API v1 REST & SSE Chat Routers
│   └── worker/            # Celery Background Task Workers & Data Pipelines
│
├── packages/
│   ├── agents/            # Core ReAct Agents & Memory Engine (base.py, memory.py, api.py)
│   ├── connectors/        # Enterprise Connectors (quickbooks.py, generic_rest.py, base.py)
│   ├── security/          # Guardrails & Safety Engine (guardrails.py, auth.py, utils.py)
│   ├── tools/             # Domain Tools & RBAC Layer (erp_tools.py)
│   ├── database/          # SQLAlchemy Models, Core Engine, & Alembic Migrations
│   ├── models/            # Pydantic Request/Response Data Schemas
│   └── rag/               # Document Embeddings & ChromaDB Vector Search (vector_store.py)
│
├── pytest.ini             # Pytest Configuration (pythonpath & asyncio mode)
├── requirements.txt       # Production PyPI Dependencies
└── tests/
    ├── unit/              # Security & Guardrail Unit Tests (pytest)
    └── integration/       # ReAct Loop, RBAC, Chroma RAG, and Connector Tests
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
| `/connectors` | **Connectors Hub** | Enterprise data stream manager for QuickBooks Online and REST endpoints. |
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

#### Native Dual-Server Mode (Development & Production)

```powershell
# 1. Start Python FastAPI Enterprise Gateway (Terminal 1)
$env:PYTHONPATH="."
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

# 2. Start Next.js 16 Web Dashboard (Terminal 2)
cd apps/web
npm install
npm run dev
```

- 🌐 **Frontend UI**: [http://localhost:3000](http://localhost:3000)
- ⚡ **Backend API**: [http://localhost:8000](http://localhost:8000)
- 📜 **Swagger OpenAPI Docs**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

---

## 🧪 Testing & Quality Assurance

All suites pass with **100% success**:

```powershell
# 1. Compile all Python backend files (0 Errors)
python -m compileall apps packages tests

# 2. Run full automated unit and integration test suite (20/20 Passed)
pytest tests -v

# 3. Run live API endpoint integration test suite (14/14 Passed)
python scripts/test_integration.py
```

---

## 📄 License & Support

Copyright © 2026. All rights reserved.  
Repository: [https://github.com/Ajimsha1080/Agentic-ERP-backend.git](https://github.com/Ajimsha1080/Agentic-ERP-backend.git)

