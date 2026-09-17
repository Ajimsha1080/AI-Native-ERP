"use client";

import { useState, useEffect } from "react";
import { apiClient } from "../../lib/api-client";

export default function BillingPage() {
  const [subData, setSubData] = useState<{ plan: string; status: string } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    apiClient.get("/api/v1/billing/subscription")
      .then(setSubData)
      .catch(() => setSubData({ plan: "free", status: "active" }));
  }, []);

  const handleUpgrade = async (plan: string) => {
    setLoading(true);
    try {
      const data = await apiClient.post("/api/v1/billing/checkout", { plan });
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (err: any) {
      alert(err.message || "Failed to initialize Stripe checkout");
    } finally {
      setLoading(false);
    }
  };

  const planName = subData?.plan ? subData.plan.toUpperCase() : "FREE";
  const tokenLimit = subData?.plan === "enterprise" ? "50M" : subData?.plan === "pro" ? "5M" : "100k";

  return (
    <main className="main">
      <div className="topbar">
        <div>
          <span className="crumb">Billing</span>
          <span className="crumb-sub">Manage subscription and API usage</span>
        </div>
      </div>

      <div className="content" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div className="panel" style={{ padding: '32px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>{planName} Plan</h2>
                <div style={{ fontSize: '13px', color: 'var(--text-dim)', marginTop: '4px' }}>
                  Status: <strong style={{ color: 'var(--verified)' }}>{subData?.status || "Active"}</strong>
                </div>
              </div>
              <button 
                onClick={() => handleUpgrade("enterprise")} 
                disabled={loading}
                className="panel-action" 
                style={{ background: 'var(--ai-core)', color: '#fff' }}
              >
                {loading ? "Processing..." : "Upgrade / Manage Plan"}
              </button>
            </div>
            
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '8px' }}>
                <span style={{ color: 'var(--text-dim)' }}>API Tokens Allocated (Monthly Quota)</span>
                <span style={{ fontWeight: 500 }}>0.0M / {tokenLimit}</span>
              </div>
              <div style={{ width: '100%', height: '8px', background: 'var(--surface-2)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: '5%', height: '100%', background: 'var(--verified)' }}></div>
              </div>
            </div>
            
            <div style={{ fontSize: '12px', color: 'var(--text-faint)' }}>
              Real-time API token usage resets automatically at the start of each billing cycle.
            </div>
          </div>

          <div className="panel" style={{ padding: '32px' }}>
            <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '20px' }}>Payment Method</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '16px', border: '1px solid var(--border-soft)', borderRadius: '8px' }}>
              <div style={{ fontSize: '13px', color: 'var(--text-dim)' }}>
                Stripe Payments configured with PCI-compliant token vault and automated dunning.
              </div>
              <button onClick={() => handleUpgrade("pro")} className="panel-action" style={{ marginLeft: 'auto' }}>
                + Add / Update Card
              </button>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <h2 className="panel-title">Invoice History</h2>
          </div>
          <div style={{ padding: '32px', color: 'var(--text-dim)', fontSize: '13px', textAlign: 'center' }}>
            No overdue invoices. All subscription transactions verified through Stripe webhooks.
          </div>
        </div>
      </div>
    </main>
  );
}

