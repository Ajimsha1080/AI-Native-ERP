"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "../../lib/auth-context";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [orgName, setOrgName] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { signup } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const res = await signup({
      email,
      password,
      organization_name: orgName,
      first_name: firstName,
      last_name: lastName,
    });

    setLoading(false);

    if (res.success) {
      router.push("/");
      router.refresh();
    } else {
      setError(res.error || "Registration failed");
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg)", padding: "24px" }}>
      <div className="panel" style={{ width: "100%", maxWidth: "480px", padding: "40px", borderRadius: "16px", boxShadow: "0 20px 40px rgba(0,0,0,0.1)" }}>
        <div style={{ textAlign: "center", marginBottom: "28px" }}>
          <div style={{ width: "48px", height: "48px", borderRadius: "12px", background: "var(--verified)", color: "#000", margin: "0 auto 16px auto", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: "20px" }}>
            ⚡
          </div>
          <h1 style={{ fontSize: "22px", fontWeight: 700, margin: "0 0 6px 0" }}>Create Enterprise Workspace</h1>
          <p style={{ fontSize: "13px", color: "var(--text-dim)", margin: 0 }}>Launch your autonomous multi-agent ERP tenant</p>
        </div>

        {error && (
          <div style={{ background: "rgba(240, 85, 91, 0.1)", border: "1px solid var(--danger)", color: "var(--danger)", padding: "12px 14px", borderRadius: "8px", fontSize: "13px", marginBottom: "20px" }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-faint)", textTransform: "uppercase", marginBottom: "6px" }}>
              Company / Organization Name
            </label>
            <input
              type="text"
              required
              className="ai-cmd-input"
              style={{ width: "100%", padding: "10px 14px", fontSize: "14px", borderRadius: "8px" }}
              placeholder="Acme Industrial Corp"
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-faint)", textTransform: "uppercase", marginBottom: "6px" }}>
                First Name
              </label>
              <input
                type="text"
                required
                className="ai-cmd-input"
                style={{ width: "100%", padding: "10px 14px", fontSize: "14px", borderRadius: "8px" }}
                placeholder="Alex"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
            </div>
            <div>
              <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-faint)", textTransform: "uppercase", marginBottom: "6px" }}>
                Last Name
              </label>
              <input
                type="text"
                required
                className="ai-cmd-input"
                style={{ width: "100%", padding: "10px 14px", fontSize: "14px", borderRadius: "8px" }}
                placeholder="Morgan"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-faint)", textTransform: "uppercase", marginBottom: "6px" }}>
              Work Email
            </label>
            <input
              type="email"
              required
              className="ai-cmd-input"
              style={{ width: "100%", padding: "10px 14px", fontSize: "14px", borderRadius: "8px" }}
              placeholder="alex@acme.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-faint)", textTransform: "uppercase", marginBottom: "6px" }}>
              Password (Min 8 characters)
            </label>
            <input
              type="password"
              required
              minLength={8}
              className="ai-cmd-input"
              style={{ width: "100%", padding: "10px 14px", fontSize: "14px", borderRadius: "8px" }}
              placeholder="••••••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary"
            style={{ width: "100%", padding: "12px", fontSize: "14px", fontWeight: 600, marginTop: "8px", background: "var(--ai-core)" }}
          >
            {loading ? "Creating workspace..." : "Create Workspace →"}
          </button>
        </form>

        <div style={{ marginTop: "24px", textAlign: "center", fontSize: "13px", color: "var(--text-dim)" }}>
          Already have an account?{" "}
          <Link href="/login" style={{ color: "var(--ai-core)", fontWeight: 600, textDecoration: "none" }}>
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
}
