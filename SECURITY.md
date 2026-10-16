# Security Policy

## Reporting Security Vulnerabilities

We take the security of AI-Native-ERP seriously. If you believe you have discovered a vulnerability, security bug, or privacy flaw, please report it responsibly so we can resolve the issue before disclosure.

### Contact Information
Please send your report to our dedicated Security Team:
- **Email**: [security@agentic-erp.example.com](mailto:security@agentic-erp.example.com)
- **PGP Key**: Fingerprint `A9F1 34B2 E89D 1104 57CF  43B9 9C81 22A0 7F56 88D2`
- **Response Window**: Initial acknowledgment within 24 hours; status updates every 48 hours until remediated.

**Please DO NOT submit public GitHub issues for security vulnerabilities.**

---

## Supported Versions

Only the latest major/minor release and current production deployments receive active security patches.

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0.0 | :x:                |

---

## Vulnerability Handling Timeline

1. **Receipt & Triage (0-24 Hours)**:
   - Acknowledge receipt of the report.
   - Verify reproduction steps in an isolated staging environment.
2. **Impact & Severity Assessment (24-48 Hours)**:
   - Assign CVSS v3.1 score.
   - Determine affected components (FastAPI API, PostgreSQL RLS, JWT Auth, Stripe billing, Next.js frontend).
3. **Remediation & Testing (48-96 Hours)**:
   - Develop targeted patch with regression tests.
   - Verify tenant isolation assertion test suite passes.
4. **Coordinated Disclosure (Post-Patch)**:
   - Deploy fix to production SaaS environments.
   - Publish security advisory with CVE identifier (if applicable) and credit reporter.

---

## Security Architecture & Defenses

AI-Native-ERP enforces defense-in-depth across multiple operational layers:

1. **Multi-Tenant Row-Level Security (RLS)**:
   - All tenant-owned tables enforce Postgres RLS via `SET LOCAL app.tenant_id = :org_id`.
   - The application database connection pool connects under a dedicated unprivileged role (`app_user`) lacking table ownership and superuser privileges.
   - Automated startup assertions and CI tests verify that every table with `organization_id` has an active RLS policy.

2. **Cryptographic Authentication Hardening**:
   - Refresh tokens use server-side `jti` tracking, family tracking, and automatic token reuse detection (revoking all descendant sessions immediately upon reuse attempt).
   - Password reset and email verification tokens are strictly single-use and expire within 15 minutes.
   - Password hashes enforce Argon2id (or bcrypt with salt rounds >= 12).

3. **Strict RBAC & Least-Privilege**:
   - Four-tier hierarchical RBAC (`owner`, `admin`, `manager`, `viewer`) stored in database membership records.
   - Protected endpoints require minimum role validation (`require_min_role`).
   - Deletion or demotion of the last remaining Owner is blocked at both router and database levels.

4. **Web Security & Headers**:
   - Strict Content Security Policy (`CSP`), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and `Strict-Transport-Security` headers on all responses.
   - Requests carry end-to-end `X-Request-ID` correlation identifiers.
