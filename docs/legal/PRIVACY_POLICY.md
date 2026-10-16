# AI-Native Enterprise ERP Privacy Policy

**Effective Date: October 15, 2026**  
**Last Updated: October 15, 2026**

AI-Native-ERP Inc. ("Company", "We", "Us") is committed to protecting the privacy and confidentiality of personal data processed across our multi-tenant SaaS platform. This Privacy Policy details how we collect, store, isolate, protect, and process personal information in compliance with the General Data Protection Regulation (GDPR), California Consumer Privacy Act (CCPA), and global data protection standards.

---

## 1. Information We Collect

1.1. **Account & Identity Information**: Name, business email address, role, password hash (salted Argon2id/bcrypt), and organization affiliation provided during registration or invitation.

1.2. **Tenant ERP Data**: Financial ledgers, invoice metadata, customer records, supplier profiles, and employee directories uploaded into Customer's isolated tenant schema.

1.3. **System Telemetry & Audit Logs**: Request IDs (`X-Request-ID`), IP addresses, user agent strings, and immutable timestamps of security events (login, role modification, user deprovisioning).

---

## 2. Multi-Tenant Cryptographic Isolation

2.1. **PostgreSQL Row-Level Security (RLS)**: Personal data is logically segregated at the database engine level. Every SQL query executes with a tenant-scoped session variable (`app.tenant_id`) enforced by PostgreSQL kernel RLS policies. Cross-tenant leakage across pooled database connections is mathematically prevented.

2.2. **Unprivileged Connection Roles**: Application servers connect using a non-superuser database role (`app_user`) that cannot bypass RLS.

---

## 3. Data Subject Rights (GDPR & CCPA)

Under GDPR (Articles 15-22), users have fundamental rights regarding their personal data:

1. **Right of Access & Portability (Article 20)**: Users may request a machine-readable export of their personal profile, memberships, and audit trails via `GET /api/v1/users/me/export`. Organization Owners may export complete tenant records via `GET /api/v1/organizations/{id}/export`.
2. **Right to Erasure / Right to be Forgotten (Article 17)**: Users may initiate self-deletion via `DELETE /api/v1/users/me`. This permanently deactivates credentials and anonymizes personal identifying information (e.g., `anonymized_xyz@deleted.local`).
3. **Right to Rectification (Article 16)**: Users may update their name, email, or settings at any time.

---

## 4. Subprocessors & Third-Party Service Providers

We utilize SOC2 / ISO 27001 certified third-party subprocessors under strict Data Processing Agreements (DPAs):

| Subprocessor | Purpose | Location |
| ------------ | ------- | -------- |
| **Amazon Web Services (AWS)** | Cloud Infrastructure, RDS PostgreSQL, KMS Encryption | USA (us-east-1) |
| **Stripe, Inc.** | Payment Processing, Billing Subscriptions & Invoicing | USA |
| **OpenAI / Anthropic** | LLM Inference for Enterprise Agents | USA |
| **Sentry** | Application Performance Monitoring & Error Tracking | USA |

---

## 5. Contact & Data Protection Officer (DPO)

For inquiries regarding this Privacy Policy or to exercise data privacy rights:
- **Email**: [privacy@agentic-erp.example.com](mailto:privacy@agentic-erp.example.com)
- **Data Protection Officer**: DPO Office, AI-Native-ERP Inc.
