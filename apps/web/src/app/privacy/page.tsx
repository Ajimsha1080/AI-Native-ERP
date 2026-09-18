import Link from "next/link";

export default function PrivacyPolicyPage() {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", color: "var(--text)", padding: "48px 24px" }}>
      <div style={{ maxWidth: "800px", margin: "0 auto" }}>
        <div style={{ marginBottom: "32px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h1 style={{ fontSize: "28px", fontWeight: 700, letterSpacing: "-0.5px", marginBottom: "8px" }}>
              Privacy &amp; GDPR Policy
            </h1>
            <p style={{ color: "var(--text-dim)", fontSize: "14px" }}>
              Last updated: September 18, 2026 • GDPR &amp; CCPA Compliant
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
              1. Overview &amp; Data Controller
            </h2>
            <p style={{ color: "var(--text-secondary)" }}>
              This Privacy Policy explains how our AI-Native Enterprise Platform collects, uses, processes, and protects your
              personal and commercial data. As a data processor for your enterprise, we provide administrative tools to inspect,
              export, and purge your information at any time.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text)", marginBottom: "12px" }}>
              2. Information We Collect
            </h2>
            <ul style={{ color: "var(--text-secondary)", paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "8px" }}>
              <li><strong>Account &amp; Auth Information:</strong> Name, work email address, hashed passwords, IP address, and role permissions.</li>
              <li><strong>ERP Operational Records:</strong> Inventory levels, purchase orders, customer invoices, accounting ledger entries, and supplier data.</li>
              <li><strong>AI &amp; Agent Execution Telemetry:</strong> Prompts, tool execution parameters, approval logs, and LangGraph workflow trace states.</li>
              <li><strong>Audit Events:</strong> Comprehensive timestamped logs of all security, data modification, and administrative events.</li>
            </ul>
          </section>

          <section>
            <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text)", marginBottom: "12px" }}>
              3. GDPR Data Subject Rights (Articles 15 - 22)
            </h2>
            <p style={{ color: "var(--text-secondary)", marginBottom: "12px" }}>
              Under GDPR, EU/EEA citizens and global users of our platform are granted fundamental rights:
            </p>
            <ul style={{ color: "var(--text-secondary)", paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "8px" }}>
              <li><strong>Right of Access (Art. 15):</strong> Request a full machine-readable copy of your tenant data via <code>GET /api/v1/compliance/export</code>.</li>
              <li><strong>Right to Rectification (Art. 16):</strong> Modify inaccurate profile or business records directly through the ERP settings.</li>
              <li><strong>Right to Erasure / &ldquo;Right to be Forgotten&rdquo; (Art. 17):</strong> Authorize complete deletion of your personal records and organization via <code>POST /api/v1/compliance/delete-account</code>.</li>
              <li><strong>Right to Data Portability (Art. 20):</strong> Export audit events and operational records in JSON and CSV formats.</li>
            </ul>
          </section>

          <section>
            <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text)", marginBottom: "12px" }}>
              4. Security Measures &amp; Encryption
            </h2>
            <p style={{ color: "var(--text-secondary)" }}>
              We enforce multi-tenant isolation through PostgreSQL Row-Level Security (RLS) policies, session token-bucket rate limiting,
              HTTP-only secure cookies with Strict SameSite policy, and end-to-end cryptographic hashing of sensitive secrets.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--text)", marginBottom: "12px" }}>
              5. Data Protection Officer (DPO)
            </h2>
            <p style={{ color: "var(--text-secondary)" }}>
              If you have inquiries regarding our data handling practices or wish to submit a formal Data Protection Request,
              reach out to our Data Protection Officer at privacy@agentic-erp.io.
            </p>
          </section>
        </div>

        <div style={{ marginTop: "24px", textAlign: "center", fontSize: "13px", color: "var(--text-dim)" }}>
          AI-Native ERP Platform • Built for Enterprise Compliance
        </div>
      </div>
    </div>
  );
}
