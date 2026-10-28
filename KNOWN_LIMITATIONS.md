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

## 4. AI Agents, RAG & LLM Inference

1. **Zero-Mock Production Behavior**:
   - The platform strictly prohibits canned, simulated, or mock fallbacks in all production pathways. If external LLM or embedding providers are unreachable or unconfigured, endpoints return an explicit HTTP 503 (`Service Unavailable`) instead of returning simulated data or hash-based approximations.

2. **Embedding Model & Vector Dimension Coupling**:
   - The pgvector schema and dense knowledge retrieval are strictly coupled to 1536-dimensional embeddings (e.g., OpenAI `text-embedding-3-small`). Using self-hosted embedding models (e.g., Ollama, HuggingFace) requires matching the 1536 dimension or creating an Alembic migration to resize the `embedding` column on `knowledge_chunks`.

3. **Dual-Human Approval Boundaries**:
   - State-changing agent operations (disbursements, POs, inventory adjustments) exceeding the `$1,000.00` threshold strictly enforce server-side dual-approval: two distinct users with `manager`, `admin`, or `owner` roles must approve. The requester is cryptographically and server-side barred from approving their own request. Organizations with only a single employee must adjust the organization approval threshold or add a second manager.

4. **Token Revocation & Fail-Closed Behavior**:
   - Access token revocation and session blacklisting require an active Redis instance. If Redis becomes unreachable outside automated test environments, the auth gateway fails closed with HTTP 503 to prevent serving potentially revoked credentials.

5. **SCIM 2.0 Directory Ingestion**:
   - While OIDC / OAuth SSO is architecturally supported, automated inbound SCIM 2.0 user provisioning and deprovisioning is not yet implemented. Deprovisioning must be conducted via the user management API or admin dashboard.
