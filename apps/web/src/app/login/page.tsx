"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "../../lib/auth-context";

function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get("redirect") || "/";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const res = await login(email, password);
    setLoading(false);

    if (res.success) {
      router.push(redirect);
      router.refresh();
    } else {
      setError(res.error || "Invalid email or password");
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg)", padding: "24px" }}>
      <div className="panel" style={{ width: "100%", maxWidth: "420px", padding: "40px", borderRadius: "16px", boxShadow: "0 20px 40px rgba(0,0,0,0.1)" }}>
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <div style={{ width: "48px", height: "48px", borderRadius: "12px", background: "var(--ai-core)", margin: "0 auto 16px auto", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: 700, fontSize: "20px" }}>
            AI
          </div>
          <h1 style={{ fontSize: "22px", fontWeight: 700, margin: "0 0 6px 0" }}>Sign in to Agentic ERP</h1>
          <p style={{ fontSize: "13px", color: "var(--text-dim)", margin: 0 }}>Autonomous Business Operating Platform</p>
        </div>

        {error && (
          <div style={{ background: "rgba(240, 85, 91, 0.1)", border: "1px solid var(--danger)", color: "var(--danger)", padding: "12px 14px", borderRadius: "8px", fontSize: "13px", marginBottom: "20px" }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-faint)", textTransform: "uppercase", marginBottom: "6px" }}>
              Work Email
            </label>
            <input
              type="email"
              required
              className="ai-cmd-input"
              style={{ width: "100%", padding: "12px 14px", fontSize: "14px", borderRadius: "8px" }}
              placeholder="name@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
              <label style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-faint)", textTransform: "uppercase" }}>
                Password
              </label>
            </div>
            <input
              type="password"
              required
              className="ai-cmd-input"
              style={{ width: "100%", padding: "12px 14px", fontSize: "14px", borderRadius: "8px" }}
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
            {loading ? "Signing in..." : "Sign In →"}
          </button>
        </form>

        <div style={{ marginTop: "24px", textAlign: "center", fontSize: "13px", color: "var(--text-dim)" }}>
          Don't have an enterprise workspace?{" "}
          <Link href="/signup" style={{ color: "var(--ai-core)", fontWeight: 600, textDecoration: "none" }}>
            Create one
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>Loading...</div>}>
      <LoginForm />
    </Suspense>
  );
}
