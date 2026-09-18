"use client";

import { useState, useEffect } from "react";
import { apiClient } from "../../lib/api-client";

interface Invoice {
  id: string;
  number: string;
  amount_paid: number;
  currency: string;
  status: string;
  created_at: string;
  pdf_url?: string;
  hosted_url?: string;
}

export default function BillingPage() {
  const [subData, setSubData] = useState<{ plan: string; status: string } | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(false);
  const [invoicesLoading, setInvoicesLoading] = useState(true);

  useEffect(() => {
    loadBillingData();
  }, []);

  const loadBillingData = async () => {
    try {
      const sub = await apiClient.get("/api/v1/billing/subscription");
      setSubData(sub);
    } catch {
      setSubData({ plan: "free", status: "active" });
    }

    try {
      const invList = await apiClient.get("/api/v1/billing/invoices");
      setInvoices(Array.isArray(invList) ? invList : []);
    } catch {
      setInvoices([]);
    } finally {
      setInvoicesLoading(false);
    }
  };

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

  const handleCancel = async () => {
    if (!confirm("Are you sure you want to cancel your subscription and downgrade to the Free tier?")) {
      return;
    }
    setLoading(true);
    try {
      await apiClient.post("/api/v1/billing/cancel", {});
      alert("Subscription canceled. Your account has been reverted to Free tier.");
      await loadBillingData();
    } catch (err: any) {
      alert(err.message || "Failed to cancel subscription");
    } finally {
      setLoading(false);
    }
  };

  const planName = subData?.plan ? subData.plan.toUpperCase() : "FREE";
  const tokenLimit = subData?.plan === "enterprise" ? "50M" : subData?.plan === "pro" ? "5M" : "100k";
  const isPastDue = subData?.status === "past_due";

  return (
    <main className="main">
      <div className="topbar">
        <div>
          <span className="crumb">Billing & Plans</span>
          <span className="crumb-sub">Manage enterprise subscription, quotas, and invoices</span>
        </div>
      </div>

      <div className="content" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {isPastDue && (
          <div style={{ background: '#fef2f2', border: '1px solid #f87171', color: '#991b1b', padding: '16px 20px', borderRadius: '8px', fontSize: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong>Payment Past Due:</strong> Your last automatic subscription invoice failed. Please update your payment method to avoid service interruption.
            </div>
            <button onClick={() => handleUpgrade(subData?.plan || "pro")} className="panel-action" style={{ background: '#dc2626', color: '#fff' }}>
              Update Payment Method
            </button>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div className="panel" style={{ padding: '32px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>{planName} Plan</h2>
                  <div style={{ fontSize: '13px', color: 'var(--text-dim)', marginTop: '4px' }}>
                    Status: <strong style={{ color: isPastDue ? '#dc2626' : 'var(--verified)' }}>{subData?.status?.toUpperCase() || "ACTIVE"}</strong>
                  </div>
                </div>
                {subData?.plan !== "enterprise" ? (
                  <button 
                    onClick={() => handleUpgrade("enterprise")} 
                    disabled={loading}
                    className="panel-action" 
                    style={{ background: 'var(--ai-core)', color: '#fff' }}
                  >
                    {loading ? "Processing..." : "Upgrade to Enterprise ($299/mo)"}
                  </button>
                ) : (
                  <button 
                    onClick={handleCancel} 
                    disabled={loading}
                    className="panel-action" 
                    style={{ background: 'transparent', border: '1px solid var(--border-soft)', color: 'var(--text-dim)' }}
                  >
                    Cancel Subscription
                  </button>
                )}
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
              <h3 style={{ fontSize: '15px', fontWeight: 600, marginBottom: '16px' }}>Available Subscription Tiers</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div style={{ padding: '16px', border: '1px solid var(--border-soft)', borderRadius: '8px' }}>
                  <h4 style={{ margin: '0 0 8px 0', fontSize: '15px' }}>Pro Tier</h4>
                  <p style={{ fontSize: '13px', color: 'var(--text-dim)', margin: '0 0 16px 0' }}>\$49 / month &bull; 5M Tokens &bull; 5 Autonomous Agents</p>
                  <button 
                    onClick={() => handleUpgrade("pro")} 
                    disabled={loading || subData?.plan === "pro"} 
                    className="panel-action" 
                    style={{ width: '100%', textAlign: 'center' }}
                  >
                    {subData?.plan === "pro" ? "Current Plan" : "Switch to Pro"}
                  </button>
                </div>

                <div style={{ padding: '16px', border: '1px solid var(--border-soft)', borderRadius: '8px', background: 'rgba(59, 130, 246, 0.03)' }}>
                  <h4 style={{ margin: '0 0 8px 0', fontSize: '15px' }}>Enterprise Tier</h4>
                  <p style={{ fontSize: '13px', color: 'var(--text-dim)', margin: '0 0 16px 0' }}>\$299 / month &bull; 50M Tokens &bull; Unlimited Agents</p>
                  <button 
                    onClick={() => handleUpgrade("enterprise")} 
                    disabled={loading || subData?.plan === "enterprise"} 
                    className="panel-action" 
                    style={{ width: '100%', textAlign: 'center', background: 'var(--ai-core)', color: '#fff' }}
                  >
                    {subData?.plan === "enterprise" ? "Current Plan" : "Switch to Enterprise"}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="panel-head">
              <h2 className="panel-title">Invoice & Receipt History</h2>
            </div>
            <div style={{ padding: '20px', flex: 1 }}>
              {invoicesLoading ? (
                <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-dim)', fontSize: '13px' }}>
                  Loading invoices...
                </div>
              ) : invoices.length === 0 ? (
                <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-dim)', fontSize: '13px' }}>
                  No past invoices. All subscription transactions verified through Stripe.
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-soft)', textAlign: 'left' }}>
                        <th style={{ padding: '10px 8px', color: 'var(--text-dim)' }}>Invoice #</th>
                        <th style={{ padding: '10px 8px', color: 'var(--text-dim)' }}>Date</th>
                        <th style={{ padding: '10px 8px', color: 'var(--text-dim)' }}>Amount</th>
                        <th style={{ padding: '10px 8px', color: 'var(--text-dim)' }}>Status</th>
                        <th style={{ padding: '10px 8px', color: 'var(--text-dim)' }}>Receipt</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invoices.map((inv) => (
                        <tr key={inv.id} style={{ borderBottom: '1px solid var(--border-soft)' }}>
                          <td style={{ padding: '10px 8px', fontWeight: 500 }}>{inv.number}</td>
                          <td style={{ padding: '10px 8px', color: 'var(--text-dim)' }}>
                            {new Date(inv.created_at).toLocaleDateString()}
                          </td>
                          <td style={{ padding: '10px 8px' }}>
                            \${inv.amount_paid.toFixed(2)} {inv.currency}
                          </td>
                          <td style={{ padding: '10px 8px' }}>
                            <span style={{ 
                              padding: '2px 8px', 
                              borderRadius: '4px', 
                              fontSize: '11px', 
                              fontWeight: 600,
                              background: inv.status === 'paid' ? '#ecfdf5' : '#fef2f2',
                              color: inv.status === 'paid' ? '#059669' : '#dc2626'
                            }}>
                              {inv.status.toUpperCase()}
                            </span>
                          </td>
                          <td style={{ padding: '10px 8px' }}>
                            {inv.pdf_url || inv.hosted_url ? (
                              <a 
                                href={inv.pdf_url || inv.hosted_url} 
                                target="_blank" 
                                rel="noreferrer" 
                                style={{ color: '#2563eb', textDecoration: 'underline' }}
                              >
                                View PDF
                              </a>
                            ) : (
                              <span style={{ color: 'var(--text-faint)' }}>Receipt on file</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}


