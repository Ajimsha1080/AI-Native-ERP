# Known Limitations & Operational Boundaries

This document records the current known technical limitations, architectural constraints, and operational boundaries of the AI-Native-ERP platform as of Version 1.0.0.

---

## 1. Multi-Tenancy & Database Engine

1. **PostgreSQL Exclusivity for Row-Level Security (RLS)**:
   - Row-Level Security (RLS) policies are natively enforced via PostgreSQL kernel mechanisms (`SET LOCAL app.tenant_id = :org_id`).
   - SQLite does not support native Row-Level Security policies; SQLite fallback is supported only for isolated in-memory unit tests that do not evaluate multi-tenant boundaries. All production, staging, and multi-tenant test suites strictly require PostgreSQL 16+.

2. **Cross-Tenant Joins Are Prevented by Design**:
   - Because RLS policies evaluate `organization_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid`, queries cannot join across tenants. Global superuser reports spanning multiple organizations must explicitly connect using a dedicated superuser role that bypasses RLS policies outside the standard request connection pool.

3. **Tenant Migration Between Databases**:
   - While tenants can export their complete data via `GET /api/v1/organizations/{id}/export`, single-tenant database extraction into an independent standalone RDS instance requires running custom dump scripts (`pg_dump --section=data --table=...`) filtered by `organization_id`.

---

## 2. Authentication & Identity Management

1. **SCIM 2.0 Directory Sync**:
   - Enterprise SAML/SSO is supported via Google, Azure AD, and Okta OAuth/OIDC providers. Automated SCIM (System for Cross-domain Identity Management) directory synchronization is currently not implemented; user deprovisioning must be performed via the REST API (`DELETE /api/v1/users/{id}`) or UI admin console.

2. **Hardware Security Keys (WebAuthn / FIDO2)**:
   - Authentication supports Argon2id passwords with time/memory cost parameters exceeding OWASP standards, JWT rotation with family tracking, and TOTP MFA. Direct WebAuthn / FIDO2 hardware biometric key integration is planned for a future minor release.

3. **Global Email Uniqueness**:
   - User email addresses are currently unique across the platform. A user invited to multiple organizations shares a single user identity with distinct `organization_members` role records.

---

## 3. Stripe Billing & Usage Metering

1. **Near-Real-Time Usage Quotas**:
   - Daily and monthly LLM token consumption is tracked in PostgreSQL and Redis. Quota checks occur at the beginning of each agent execution. If multiple concurrent agent runs are initiated right at the boundary of a token cap, token consumption may slightly overshoot the limit before subsequent calls are blocked.

2. **Single Currency per Organization**:
   - Invoicing is currently billed in USD ($) by default. Multi-currency price localization (EUR, GBP, JPY) on Stripe Checkout requires defining separate Stripe Price IDs in environment configuration.

---

## 4. AI Agents & LLM Inference

1. **LLM Provider Latencies**:
   - Agent execution latency is subject to upstream LLM API latency (OpenAI / Anthropic / Google). While streaming is supported on chat endpoints, complex multi-agent workflows involving multiple tools may take between 3 to 10 seconds to execute. High-latency batch jobs should be routed to Celery background workers.

2. **Dual-Human Approval Boundaries**:
   - Financial operations exceeding `$1,000.00` require dual-human approval in `/approvals`. If an organization has only a single administrator, approval must be granted by the Organization Owner.
