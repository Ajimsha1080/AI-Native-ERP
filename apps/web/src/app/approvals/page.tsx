"use client";

import { apiClient } from "../../lib/api-client";

import { useState, useEffect } from "react";

export default function ApprovalsPage() {
  const [activeTab, setActiveTab] = useState<"pending" | "approved" | "rejected">("pending");
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [editAmount, setEditAmount] = useState("");
  const [editNotes, setEditNotes] = useState("");

  const fetchApprovals = async () => {
    try {
      const data = await apiClient.get("/api/v1/actions/approvals-queue");
      setItems(data);
    } catch (err) {
      console.error("Failed to fetch approvals queue:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApprovals();
  }, []);

  const handleApprove = async (id: string) => {
    setItems(prev => prev.map(item => item.id === id ? { ...item, status: "approved" } : item));
    if (selectedItem?.id === id) setSelectedItem(null);

    try {
      await apiClient.post(`/api/v1/actions/${id}/approve`, { action_on_action: "approve", comments: "Approved via Approvals Gate" });
    } catch (err) {
      console.error("Approval error:", err);
    }
  };

  const handleReject = async (id: string) => {
    setItems(prev => prev.map(item => item.id === id ? { ...item, status: "rejected" } : item));
    if (selectedItem?.id === id) setSelectedItem(null);

    try {
      await apiClient.post(`/api/v1/actions/${id}/reject`, { rejection_reason: "Declined by Executive via Approvals Gate" });
    } catch (err) {
      console.error("Rejection error:", err);
    }
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedItem) return;

    const newAmount = editAmount || selectedItem.amount;
    setItems(prev => prev.map(item => item.id === selectedItem.id ? { 
      ...item, 
      amount: newAmount,
      details: [...(item.details || []), `Modified by Executive: ${editNotes || 'Adjusted parameter'}`]
    } : item));

    try {
      await apiClient.put(`/api/v1/actions/${selectedItem.id}`, { amount: newAmount, description: editNotes ? `${selectedItem.subtitle} (Note: ${editNotes})` : selectedItem.subtitle });
    } catch (err) {
      console.error("Edit error:", err);
    }

    setSelectedItem(null);
  };

  const filteredItems = items.filter(item => item.status === activeTab);
  const pendingCount = items.filter(i => i.status === "pending").length;

  return (
    <main className="main">
      <div className="topbar">
        <div>
          <span className="crumb">Approvals</span>
          <span className="crumb-sub">Human-in-the-Loop Executive Decision Gate</span>
        </div>
      </div>

      <div className="content">
        {/* KPI Metrics */}
        <div className="kpi-grid mb-6">
          <div className="kpi-card">
            <div className="kpi-label">Pending Approval Queue</div>
            <div className="kpi-val">{pendingCount} Items</div>
            <div className="kpi-delta flat">{pendingCount > 0 ? 'Requires Action' : 'Queue Clear'}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Financial Threshold</div>
            <div className="kpi-val">$1,000.00</div>
            <div className="kpi-delta active">AI Safety Guardrail Active</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Decision Policy</div>
            <div className="kpi-val">Strict Multi-Tenant</div>
            <div className="kpi-delta up">Immutable Audit Trail</div>
          </div>
        </div>

        {/* Tab Filters */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '1px solid var(--border-soft)', paddingBottom: '12px' }}>
          <button 
            className={`btn ${activeTab === 'pending' ? 'btn-primary' : 'btn-secondary'} text-xs`}
            onClick={() => setActiveTab("pending")}
          >
            Pending ({pendingCount})
          </button>
          <button 
            className={`btn ${activeTab === 'approved' ? 'btn-primary' : 'btn-secondary'} text-xs`}
            onClick={() => setActiveTab("approved")}
          >
            Approved ({items.filter(i => i.status === "approved").length})
          </button>
          <button 
            className={`btn ${activeTab === 'rejected' ? 'btn-primary' : 'btn-secondary'} text-xs`}
            onClick={() => setActiveTab("rejected")}
          >
            Rejected ({items.filter(i => i.status === "rejected").length})
          </button>
        </div>

        {/* List / Empty State */}
        {loading ? (
          <div className="skeleton" style={{ height: '200px', borderRadius: '16px' }}></div>
        ) : filteredItems.length === 0 ? (
          <div className="panel" style={{ padding: '60px 24px', textAlign: 'center', color: 'var(--text-dim)', borderRadius: '16px' }}>
            <div style={{ fontSize: '42px', marginBottom: '16px' }}>✅</div>
            <h3 className="font-semibold text-base mb-1" style={{ color: 'var(--text)' }}>No {activeTab.toUpperCase()} Approvals in Queue</h3>
            <p className="text-sm text-dim" style={{ maxWidth: '440px', margin: '0 auto' }}>
              Your {activeTab} queue is clear. When an automated agent action exceeds your $1,000 threshold, it will appear here for executive authorization.
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {filteredItems.map((item) => (
              <div key={item.id} className="panel" style={{ padding: '24px', borderRadius: '16px', borderLeft: `4px solid ${item.urgent ? 'var(--danger)' : 'var(--ai-core)'}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: 600, margin: 0, color: 'var(--text)' }}>{item.title}</h3>
                    <p style={{ fontSize: '13px', color: 'var(--text-dim)', margin: '4px 0 0 0' }}>{item.subtitle}</p>
                  </div>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text)' }}>{item.amount}</div>
                </div>

                <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', fontSize: '12px' }}>
                  <span className="badge" style={{ background: 'var(--surface-2)', color: 'var(--text)' }}>{item.agent}</span>
                  <span className="badge" style={{ background: 'var(--surface-2)', color: 'var(--text-dim)' }}>{item.system}</span>
                  <span style={{ marginLeft: 'auto', color: 'var(--text-faint)' }}>{item.time}</span>
                </div>

                {item.status === 'pending' && (
                  <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
                    <button className="btn btn-secondary text-xs" style={{ color: 'var(--danger)' }} onClick={() => handleReject(item.id)}>✕ Reject</button>
                    <button className="btn btn-secondary text-xs" onClick={() => { setSelectedItem(item); setEditAmount(item.amount); }}>✎ Modify</button>
                    <button className="btn btn-primary text-xs" style={{ background: 'var(--verified)', color: '#000', marginLeft: 'auto' }} onClick={() => handleApprove(item.id)}>✓ Approve & Execute</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modify Modal */}
      {selectedItem && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '16px', padding: '32px', width: '100%', maxWidth: '480px' }}>
            <h2 className="font-semibold text-lg mb-4">Modify Action Parameters</h2>
            <form onSubmit={handleSaveEdit}>
              <div style={{ marginBottom: '16px' }}>
                <label className="text-xs font-semibold uppercase text-faint mb-1 block">Adjusted Amount</label>
                <input type="text" className="ai-cmd-input" style={{ width: '100%', padding: '10px 14px' }} value={editAmount} onChange={(e) => setEditAmount(e.target.value)} />
              </div>
              <div style={{ marginBottom: '20px' }}>
                <label className="text-xs font-semibold uppercase text-faint mb-1 block">Executive Notes</label>
                <textarea className="ai-cmd-input" style={{ width: '100%', padding: '10px 14px', height: '80px' }} placeholder="Add note for agent execution..." value={editNotes} onChange={(e) => setEditNotes(e.target.value)} />
              </div>
              <div style={{ display: 'flex', gap: '12px' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setSelectedItem(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary" style={{ flex: 1 }}>Save Adjustments</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
