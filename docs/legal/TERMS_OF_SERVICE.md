# AI-Native Enterprise ERP SaaS Terms of Service

> [!WARNING]
> **LEGAL REVIEW PENDING**: This document is an engineering operational template for software terms of service and must be reviewed, customized, and approved by qualified legal counsel for your specific jurisdiction before commercial execution.

**Effective Date: October 15, 2026**  
**Last Updated: October 15, 2026**

These Terms of Service ("Terms") constitute a legally binding agreement between your organization ("Customer", "You") and AI-Native-ERP Inc. ("Company", "We", "Us"). By accessing or using the AI-Native-ERP SaaS platform, API endpoints, web dashboards, or background agentic execution engines (collectively, the "Service"), Customer agrees to be bound by these Terms.

---

## 1. Multi-Tenant SaaS Platform & Accounts

1.1. **Authorized Tenants & Organizations**: Access to the Service is partitioned by Organization. Customer is assigned a dedicated logical Tenant governed by cryptographic Row-Level Security (RLS). Customer is strictly prohibited from attempting to bypass tenant isolation boundaries, manipulate session parameters (`app.tenant_id`), or inspect data belonging to other tenants.

1.2. **RBAC & User Credentials**: Access is governed by Role-Based Access Control (`owner`, `admin`, `manager`, `viewer`). Customer's designated Organization Owner is responsible for provisioning authorized accounts, enforcing multi-factor authentication where enabled, and immediately revoking credentials of departing personnel.

1.3. **Account Security**: Customer must maintain strict confidentiality of authentication credentials, API keys, and session tokens. Company will not be liable for unauthorized actions taken using valid Customer credentials.

---

## 2. Subscription, Billing, and Plan Limits

2.1. **Subscription Plans**: The Service is offered under tiered subscription plans (Free, Pro, Enterprise) billed on a recurring monthly or annual basis via Stripe.

2.2. **Plan Limits & Metering**: Each plan includes distinct seat allowances and monthly AI token budgets:
- **Free**: Up to 3 seats, 100,000 monthly tokens.
- **Pro**: Up to 20 seats, 5,000,000 monthly tokens, advanced autonomous workflows.
- **Enterprise**: Custom seat thresholds, 50,000,000+ monthly tokens, dedicated SLAs.

2.3. **Grace Period & Payment Failure**: If a recurring payment fails, Customer enters a seven (7) calendar day grace period. If payment is not reconciled within the grace period, write operations and agentic execution will be suspended until payment is settled.

2.4. **Cancellation**: Organization Owners may cancel subscriptions via the Stripe Customer Portal or API. Cancellations take effect at the conclusion of the current billing cycle.

---

## 3. Autonomous AI Agents & Guardrails

3.1. **Agent Actions & Financial Thresholds**: The Service includes autonomous AI agents capable of generating financial transactions, inventory adjustments, and purchasing requests. Company enforces automated safety guardrails:
- Routine transactions below $1,000.00 may be processed autonomously if configured.
- Transactions exceeding $1,000.00 strictly require dual-human manager/owner approval before ledger posting.

3.2. **Customer Verification**: While AI models are designed for high precision, Customer retains sole responsibility for reviewing and verifying AI-generated accounting entries, payroll computations, and tax schedules prior to official filings.

---

## 4. Data Privacy, Confidentiality & GDPR

4.1. **Customer Data Ownership**: Customer retains all right, title, and interest in and to Customer Data uploaded or generated within Customer's tenant.

4.2. **Data Portability (GDPR Article 20)**: Customer may export tenant data in structured JSON format at any time via `/api/v1/organizations/{id}/export` or `/api/v1/users/me/export`.

4.3. **Right to Erasure (GDPR Article 17)**: Users may request permanent account deletion and personal identifying information (PII) anonymization via `/api/v1/users/me`.

---

## 5. Warranties & Limitation of Liability

5.1. **Service Level Agreement (SLA)**: Enterprise subscriptions include a 99.9% uptime commitment, excluding scheduled maintenance.

5.2. **Limitation of Liability**: To the maximum extent permitted by law, Company's total liability arising out of or related to these Terms will not exceed the total fees paid by Customer during the twelve (12) months preceding the incident.
