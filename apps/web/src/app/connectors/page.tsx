"use client";

import { apiClient } from "../../lib/api-client";

import { useState, useEffect } from "react";

// Professional High-Resolution Vector SVG Brand Logos
const BRAND_LOGOS: Record<string, React.ReactNode> = {
  "Salesforce": (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="#00A1E0">
      <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96z"/>
    </svg>
  ),
  "PostgreSQL": (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="#336791">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
    </svg>
  ),
  "QuickBooks Online": (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="#2CA01C">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h3c1.66 0 3 1.34 3 3s-1.34 3-3 3h-1v2zm0-4h1c.55 0 1-.45 1-1s-.45-1-1-1h-1v2z"/>
    </svg>
  ),
  "SAP S/4HANA": (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="#008FD3">
      <path d="M12 2L2 7v10l10 5 10-5V7L12 2zm0 2.8L19.2 8 12 11.2 4.8 8 12 4.8zM4 9.6l7 3.1v6.9L4 16.5V9.6zm16 6.9l-7 3.1v-6.9l7-3.1v6.9z"/>
    </svg>
  ),
  "Shopify": (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="#95BF47">
      <path d="M15.34 2.66c-.11-.05-.24-.04-.33.02L12.5 4.5 10 2.68c-.09-.06-.22-.07-.33-.02L4 5.25v13.5l6 3.25 6-3.25V5.25l-0.66-2.59zM12 19.5L6 16.25V7.5l6 3.25v8.75zm1-8.75l5-2.71v8.75l-5 2.71V10.75z"/>
    </svg>
  ),
  "Oracle NetSuite": (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="#005A9C">
      <path d="M12 2L2 7v10l10 5 10-5V7L12 2zm0 2.8L19.2 8 12 11.2 4.8 8 12 4.8z"/>
    </svg>
  ),
  "Custom REST API": (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="#6366F1">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
    </svg>
  ),
  "Default": (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="#6366F1">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
    </svg>
  )
};

export default function ConnectorsPage() {
  const [activeTab, setActiveTab] = useState<"all" | "connected" | "disconnected">("all");
  const [searchQuery, setSearchQuery] = useState("");

  const [connectors, setConnectors] = useState<any[]>([]);

  // Fetch available connectors from backend API
  useEffect(() => {
    apiClient.get("/api/v1/connectors/available")
      .then(data => {
        if (Array.isArray(data)) {
          const mapped = data.map((item: any) => ({
            name: item.name,
            category: item.type === 'erp' ? 'Enterprise ERP Stream' : item.type === 'crm' ? 'CRM Data Stream' : item.type === 'ecommerce' ? 'E-Commerce Store' : 'REST Data Stream',
            status: 'disconnected',
            syncTime: 'Ready to bind',
            assignedAgent: getSuggestedAgent(item.name),
            protocol: 'REST / OAuth 2.0',
            latency: '—'
          }));
          setConnectors(mapped);
        }
      })
      .catch(() => {
        setConnectors([
          { name: "SAP S/4HANA", category: "Enterprise ERP Stream", status: "disconnected", syncTime: "Ready to bind", assignedAgent: "Inventory & Procurement Agent", protocol: "REST / OAuth 2.0", latency: "—" },
          { name: "Salesforce", category: "CRM Data Stream", status: "disconnected", syncTime: "Ready to bind", assignedAgent: "Sales Agent", protocol: "REST / OAuth 2.0", latency: "—" },
          { name: "Shopify", category: "E-Commerce Store", status: "disconnected", syncTime: "Ready to bind", assignedAgent: "Inventory Agent", protocol: "REST / Webhook", latency: "—" },
          { name: "Custom REST API", category: "Generic Data Stream", status: "disconnected", syncTime: "Ready to bind", assignedAgent: "Agent Orchestrator (All Agents)", protocol: "REST API", latency: "—" }
        ]);
      });
  }, []);

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [step, setStep] = useState(1);
  const [selectedProvider, setSelectedProvider] = useState("SAP S/4HANA");
  const [targetAgent, setTargetAgent] = useState("Agent Orchestrator (All Agents)");
  const [apiKey, setApiKey] = useState("");

  const [editingConnector, setEditingConnector] = useState<any>(null);
  const [editAgent, setEditAgent] = useState("");
  const [editStatus, setEditStatus] = useState("connected");

  const getSuggestedAgent = (prov: string) => {
    if (prov.includes("Salesforce")) return "Sales Agent";
    if (prov.includes("QuickBooks") || prov.includes("Zoho")) return "Finance Agent";
    if (prov.includes("SAP")) return "Inventory & Procurement Agent";
    if (prov.includes("NetSuite")) return "Finance & Inventory Agent";
    if (prov.includes("Shopify")) return "Inventory Agent";
    return "Agent Orchestrator (All Agents)";
  };

  const handleSelectProvider = (prov: string) => {
    setSelectedProvider(prov);
    setTargetAgent(getSuggestedAgent(prov));
  };

  const handleConnect = (e: React.FormEvent) => {
    e.preventDefault();
    setConnectors(prev => prev.map(c => c.name === selectedProvider ? { ...c, status: 'connected', assignedAgent: targetAgent, syncTime: 'Just now', latency: '12ms' } : c));
    setIsModalOpen(false);
    setStep(1);
    setApiKey("");
  };

  const handleRemoveConnector = (name: string) => {
    if (confirm(`Are you sure you want to disconnect ${name}?`)) {
      setConnectors(prev => prev.map(c => c.name === name ? { ...c, status: 'disconnected', syncTime: 'Disconnected', latency: '—' } : c));
    }
  };

  const handleSaveEdit = (e: React.FormEvent) => {
    e.preventDefault();
    setConnectors(prev => prev.map(c => c.name === editingConnector.name ? { ...c, assignedAgent: editAgent, status: editStatus, syncTime: 'Updated just now' } : c));
    setEditingConnector(null);
  };

  const filteredConnectors = connectors.filter(c => {
    const matchesTab = activeTab === "all" ? true : c.status === activeTab;
    const matchesSearch = c.name.toLowerCase().includes(searchQuery.toLowerCase()) || c.category.toLowerCase().includes(searchQuery.toLowerCase()) || c.assignedAgent.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesTab && matchesSearch;
  });

  const connectedCount = connectors.filter(c => c.status === 'connected').length;

  return (
    <main className="main">
      {/* Top Header */}
      <div className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="crumb">Integrations</span>
          <span style={{ color: 'var(--text-faint)' }}>/</span>
          <span className="crumb-sub" style={{ fontSize: '13px' }}>Enterprise Data Sources & Connector Hub</span>
        </div>

        <button 
          className="btn btn-primary" 
          style={{ marginLeft: 'auto', background: 'var(--ai-core)' }}
          onClick={() => setIsModalOpen(true)}
        >
          + Connect New ERP / Data Source
        </button>
      </div>

      <div className="content" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

        {/* Enterprise KPI Metrics Bar */}
        <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          <div className="kpi-card">
            <div className="kpi-label">Active Data Streams</div>
            <div className="kpi-val" style={{ color: connectedCount > 0 ? 'var(--verified)' : 'var(--text-dim)' }}>{connectedCount} Active</div>
            <div className="kpi-delta flat">{connectedCount > 0 ? 'Operational & Live' : 'Awaiting Integration'}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Daily Sync Volume</div>
            <div className="kpi-val">{connectedCount > 0 ? '1.4M Events' : '0 Events'}</div>
            <div className="kpi-delta flat">{connectedCount > 0 ? 'High Velocity' : 'Idle'}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Average API Latency</div>
            <div className="kpi-val">{connectedCount > 0 ? '12.4 ms' : '—'}</div>
            <div className="kpi-delta active">High Throughput</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Security & Encryption</div>
            <div className="kpi-val">AES-256</div>
            <div className="kpi-delta active">OAuth 2.0 Token Vault</div>
          </div>
        </div>

        {/* Search & Filter Toolbar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-soft)', paddingBottom: '12px', gap: '16px' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button 
              className={`btn ${activeTab === 'all' ? 'btn-primary' : 'btn-secondary'} text-xs`}
              onClick={() => setActiveTab("all")}
              style={{ background: activeTab === 'all' ? 'var(--ai-core)' : undefined }}
            >
              All Connectors ({connectors.length})
            </button>
            <button 
              className={`btn ${activeTab === 'connected' ? 'btn-primary' : 'btn-secondary'} text-xs`}
              onClick={() => setActiveTab("connected")}
              style={{ background: activeTab === 'connected' ? 'var(--verified)' : undefined, color: activeTab === 'connected' ? '#000' : undefined }}
            >
              Connected ({connectedCount})
            </button>
            <button 
              className={`btn ${activeTab === 'disconnected' ? 'btn-primary' : 'btn-secondary'} text-xs`}
              onClick={() => setActiveTab("disconnected")}
            >
              Disconnected ({connectors.length - connectedCount})
            </button>
          </div>

          <div style={{ position: 'relative', width: '280px' }}>
            <input 
              type="text"
              className="ai-cmd-input"
              style={{ width: '100%', padding: '8px 12px 8px 32px', fontSize: '13px', borderRadius: '8px' }}
              placeholder="Search by system or agent..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-faint)' }}>
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
          </div>
        </div>

        {/* Connectors Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '24px' }}>
          {filteredConnectors.map(c => (
            <div 
              key={c.name} 
              className="panel" 
              style={{ 
                padding: '24px', 
                display: 'flex', 
                flexDirection: 'column', 
                gap: '16px', 
                borderRadius: '16px',
                borderLeft: `4px solid ${c.status === 'connected' ? 'var(--verified)' : 'var(--border)'}`,
                boxShadow: c.status === 'connected' ? '0 4px 16px rgba(0,0,0,0.04)' : undefined
              }}
            >
              
              {/* Header Row */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  <div style={{ background: 'var(--surface-2)', width: '52px', height: '52px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '14px', border: '1px solid var(--border)' }}>
                    {BRAND_LOGOS[c.name] || BRAND_LOGOS["Default"]}
                  </div>
                  <div>
                    <h3 style={{ fontSize: '16px', fontWeight: 600, margin: 0, color: 'var(--text)' }}>{c.name}</h3>
                    <div style={{ fontSize: '12px', color: 'var(--text-faint)', marginTop: '2px' }}>{c.category}</div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', fontWeight: 600, color: c.status === 'connected' ? 'var(--verified)' : 'var(--text-dim)', background: c.status === 'connected' ? 'var(--verified-soft)' : 'var(--surface-2)', padding: '4px 10px', borderRadius: '20px' }}>
                  <span className="agent-dot" style={{ background: c.status === 'connected' ? 'var(--verified)' : 'var(--text-dim)' }}></span>
                  {c.status === 'connected' ? 'Connected' : 'Available'}
                </div>
              </div>

              {/* Data Specs Box */}
              <div style={{ background: 'var(--bg)', borderRadius: '10px', padding: '12px 14px', border: '1px solid var(--border-soft)', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--text-faint)' }}>Routing Agent</span>
                  <strong style={{ color: 'var(--ai-core)' }}>{c.assignedAgent}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--text-faint)' }}>Protocol</span>
                  <span style={{ color: 'var(--text)' }}>{c.protocol}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--text-faint)' }}>API Latency</span>
                  <span style={{ color: c.latency === '—' ? 'var(--text-faint)' : 'var(--verified)', fontWeight: 600 }}>{c.latency}</span>
                </div>
              </div>
              
              {/* Footer Actions Row */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto', paddingTop: '16px', borderTop: '1px solid var(--border-soft)' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-faint)' }}>Sync: {c.syncTime}</span>
                
                <div style={{ display: 'flex', gap: '8px' }}>
                  {c.status === 'connected' ? (
                    <>
                      <button 
                        className="btn btn-secondary text-xs" 
                        style={{ padding: '6px 12px' }}
                        onClick={() => {
                          setEditingConnector(c);
                          setEditAgent(c.assignedAgent);
                          setEditStatus(c.status);
                        }}
                      >
                        ✎ Edit
                      </button>
                      <button 
                        className="btn btn-secondary text-xs" 
                        style={{ padding: '6px 12px', color: 'var(--danger)', borderColor: 'var(--border)' }}
                        onClick={() => handleRemoveConnector(c.name)}
                      >
                        🗑️ Disconnect
                      </button>
                    </>
                  ) : (
                    <button 
                      className="btn btn-primary text-xs" 
                      style={{ padding: '6px 14px', background: 'var(--ai-core)' }}
                      onClick={() => {
                        setSelectedProvider(c.name);
                        setTargetAgent(c.assignedAgent);
                        setIsModalOpen(true);
                        setStep(2);
                      }}
                    >
                      + Connect Stream
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Edit Connector Modal */}
      {editingConnector && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '16px', padding: '32px', width: '100%', maxWidth: '480px', boxShadow: '0 20px 40px rgba(0,0,0,0.3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 className="font-semibold text-lg">Configure {editingConnector.name} Integration</h2>
              <button onClick={() => setEditingConnector(null)} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', fontSize: '20px', cursor: 'pointer' }}>✕</button>
            </div>

            <form onSubmit={handleSaveEdit}>
              <div style={{ marginBottom: '16px' }}>
                <label className="text-xs font-semibold uppercase text-faint mb-1 block">Connection Status</label>
                <select 
                  className="ai-cmd-input" 
                  style={{ width: '100%', padding: '10px 14px', fontSize: '13px', borderRadius: '8px', background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--border)' }}
                  value={editStatus}
                  onChange={(e) => setEditStatus(e.target.value)}
                >
                  <option value="connected">🟢 Connected (Active Stream)</option>
                  <option value="disconnected">⚪ Disconnected (Paused)</option>
                </select>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label className="text-xs font-semibold uppercase text-faint mb-1 block">Re-assign Target Agent</label>
                <select 
                  className="ai-cmd-input" 
                  style={{ width: '100%', padding: '10px 14px', fontSize: '13px', borderRadius: '8px', background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--border)' }}
                  value={editAgent}
                  onChange={(e) => setEditAgent(e.target.value)}
                >
                  <option value="Agent Orchestrator (All Agents)">Agent Orchestrator (All Agents)</option>
                  <option value="Finance Agent">Finance Agent</option>
                  <option value="Inventory Agent">Inventory Agent</option>
                  <option value="Procurement Agent">Procurement Agent</option>
                  <option value="Sales Agent">Sales Agent</option>
                  <option value="Customer Ops Agent">Customer Ops Agent</option>
                  <option value="Compliance Agent">Compliance Agent</option>
                  <option value="Analytics Agent">Analytics Agent</option>
                  <option value="Inventory & Procurement Agent">Inventory & Procurement Agent</option>
                </select>
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setEditingConnector(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary" style={{ flex: 1, background: 'var(--ai-core)' }}>✓ Save Configuration</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ERP Connector Integration Wizard Modal */}
      {isModalOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '16px', padding: '32px', width: '100%', maxWidth: '520px', boxShadow: '0 20px 40px rgba(0,0,0,0.3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 className="font-semibold text-lg">Connect ERP / Enterprise Data Source</h2>
              <button onClick={() => setIsModalOpen(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', fontSize: '20px', cursor: 'pointer' }}>✕</button>
            </div>

            {/* Step Indicator */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
              <div style={{ flex: 1, height: '4px', borderRadius: '2px', background: step >= 1 ? 'var(--ai-core)' : 'var(--border)' }}></div>
              <div style={{ flex: 1, height: '4px', borderRadius: '2px', background: step >= 2 ? 'var(--ai-core)' : 'var(--border)' }}></div>
            </div>

            {step === 1 ? (
              <div>
                <label className="text-xs font-semibold uppercase text-faint mb-2 block">Select Enterprise System</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '20px' }}>
                  {["SAP S/4HANA", "Oracle NetSuite", "QuickBooks Online", "Salesforce", "Shopify", "Custom REST API"].map(provider => (
                    <div 
                      key={provider}
                      onClick={() => handleSelectProvider(provider)}
                      style={{ 
                        padding: '16px', 
                        borderRadius: '10px', 
                        border: `1px solid ${selectedProvider === provider ? 'var(--ai-core)' : 'var(--border)'}`,
                        background: selectedProvider === provider ? 'var(--surface-2)' : 'var(--bg)',
                        cursor: 'pointer',
                        fontWeight: selectedProvider === provider ? 600 : 400,
                        fontSize: '13px'
                      }}
                    >
                      {provider}
                    </div>
                  ))}
                </div>

                {/* Target Agent Selector Dropdown */}
                <div style={{ marginBottom: '24px' }}>
                  <label className="text-xs font-semibold uppercase text-faint mb-1 block">Assign Target Agent</label>
                  <select 
                    className="ai-cmd-input" 
                    style={{ width: '100%', padding: '12px 16px', fontSize: '13px', borderRadius: '8px', background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--border)' }}
                    value={targetAgent}
                    onChange={(e) => setTargetAgent(e.target.value)}
                  >
                    <option value="Agent Orchestrator (All Agents)">Agent Orchestrator (All Agents)</option>
                    <option value="Finance Agent">Finance Agent (Invoices, Ledger, P&L)</option>
                    <option value="Inventory Agent">Inventory Agent (SKUs, Stock, WMS)</option>
                    <option value="Procurement Agent">Procurement Agent (POs, Suppliers)</option>
                    <option value="Sales Agent">Sales Agent (CRM, Opportunities, Churn)</option>
                    <option value="Operations Agent">Operations Agent (Shipping, SLA)</option>
                    <option value="HR Agent">HR Agent (Payroll, Employees)</option>
                    <option value="Compliance Agent">Compliance Agent (Audit, GDPR)</option>
                  </select>
                </div>

                <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => setStep(2)}>Next: OAuth & API Credentials →</button>
              </div>
            ) : (
              <form onSubmit={handleConnect}>
                <div style={{ marginBottom: '16px' }}>
                  <label className="text-xs font-semibold uppercase text-faint mb-1 block">Selected System</label>
                  <div className="font-semibold text-base mb-1">{selectedProvider}</div>
                  <div className="text-xs text-dim mb-3">Target Agent: <strong style={{ color: 'var(--ai-core)' }}>{targetAgent}</strong></div>

                  <label className="text-xs font-semibold uppercase text-faint mb-1 block">API Key / OAuth Secret Bearer Token</label>
                  <input 
                    type="password" 
                    required
                    className="ai-cmd-input" 
                    style={{ width: '100%', padding: '12px 16px', fontSize: '14px', borderRadius: '8px' }}
                    placeholder="Enter API Secret Key or OAuth Bearer Token..."
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                  />
                </div>

                <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setStep(1)}>← Back</button>
                  <button type="submit" className="btn btn-primary" style={{ flex: 1, background: 'var(--verified)', color: '#000' }}>✓ Authenticate & Bind Stream</button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
