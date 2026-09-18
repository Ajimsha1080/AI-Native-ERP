import Link from "next/link";

export default function TermsOfServicePage() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", color: "var(--text)", padding: "48px 24px" }}>
      <div style={{ maxWidth: "800px", margin: "0 auto" }}>
        <div style={{ marginBottom: "32px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h1 style={{ fontSize: "28px", fontWeight: 700, letterSpacing: "-0.5px", marginBottom: "8px" }}>
              Terms of Service
            </h1>
            <p style={{ color: "var(--text-dim)", fontSize: "14px" }}>
              Last updated: September 18, 2026 • Version 2.1
            </p>
          </div>
          <Link
            href="/login"
            style={{
              fontSize: "14px",
              color: "var(--accent)",
              textDecoration: "none",
              padding: "8px 16px",
              border: "1px solid var(--border)",
              borderRadius: "6px",
            }}
          >
            ← Back to App
          </Link>
        </div>

        <div
          className="panel"
          style={{
            padding: "36px",
            lineHeight: "1.7",
            fontSize: "14px",
            display: "flex",
            flexDirection: "column",
            gap: "24px",
          }}
        >
          <section>
            <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text)", marginBottom: "12px" }}>
              1. Acceptance of Terms
            </h2>
            <p style={{ color: "var(--text-secondary)" }}>
              By accessing or using the AI-Native ERP Platform (&ldquo;Service&rdquo;), provided as an autonomous enterprise
              resource planning system, you agree to be bound by these Terms of Service. If you are entering into this
              agreement on behalf of a company or other legal entity, you represent that you have the authority to bind
              such entity to these terms.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text)", marginBottom: "12px" }}>
              2. Subscription Plans, Billing & Fair Usage
            </h2>
            <p style={{ color: "var(--text-secondary)" }}>
              The Service is billed on a recurring monthly or annual basis through Stripe. Subscriptions automatically renew
              unless cancelled prior to the end of the billing cycle. Usage exceeding plan limits (e.g., agent execution tokens,
              connector synchronizations, or storage quotas) will be throttled or billed according to your tier specifications.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text)", marginBottom: "12px" }}>
              3. AI Agent Operations & Human Supervision
            </h2>
            <p style={{ color: "var(--text-secondary)" }}>
              Our platform orchestrates autonomous multi-agent workflows across inventory, sales, procurement, and accounting.
              While agents operate with built-in safety boundaries and human-in-the-loop approval mechanisms, the Customer retains
              final responsibility for reviewing and verifying high-value operational financial commitments and automated actions.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text)", marginBottom: "12px" }}>
              4. Data Privacy, Multi-Tenancy & Security
            </h2>
            <p style={{ color: "var(--text-secondary)" }}>
              Each tenant operates under strict PostgreSQL Row-Level Security (RLS) isolation. Customer data is encrypted in transit
              (TLS 1.3) and at rest (AES-256). We never train shared foundational LLM models on proprietary tenant data without explicit
              written consent.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text)", marginBottom: "12px" }}>
              5. Termination & Data Erasure
            </h2>
            <p style={{ color: "var(--text-secondary)" }}>
              You may terminate your account at any time via the billing management or GDPR compliance console. Upon termination,
              your organization&rsquo;s data can be exported and will be irreversibly erased within 30 days in compliance with GDPR Article 17.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text)", marginBottom: "12px" }}>
              6. Limitation of Liability
            </h2>
            <p style={{ color: "var(--text-secondary)" }}>
              To the maximum extent permitted by applicable law, the Service is provided &ldquo;as is&rdquo; without warranties of any kind.
              In no event shall the platform operators be liable for indirect, incidental, special, consequential, or punitive damages.
            </p>
          </section>
        </div>

        <div style={{ marginTop: "24px", textAlign: "center", fontSize: "13px", color: "var(--text-dim)" }}>
          Questions regarding these terms? Contact us at legal@agentic-erp.io
        </div>
      </div>
    </div>
  );
}
