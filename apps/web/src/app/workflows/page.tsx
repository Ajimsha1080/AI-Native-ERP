"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import { apiClient } from "../../lib/api-client";
import { useAuth } from "../../lib/auth-context";
import { Pagination } from "../../components/Pagination";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { RoleBadge } from "../../components/RoleBadge";

interface Workflow {
  id: number | string;
  name: string;
  description: string;
  active: boolean;
  agents: string[];
}

export default function WorkflowsPage() {
  const { user, canPerform } = useAuth();
  const isOperator = canPerform(["owner", "admin", "manager"]);

  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filterTab, setFilterTab] = useState<"all" | "active" | "paused">("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(6);

  // Builder Modal State
  const [isBuilderOpen, setIsBuilderOpen] = useState(false);
  const [newWfName, setNewWfName] = useState("");
  const [newWfDesc, setNewWfDesc] = useState("");
  const [selectedAgentNodes, setSelectedAgentNodes] = useState<string[]>(["Inventory Agent"]);

  const loadWorkflows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch workflows from backend if endpoint is available
      const data = await apiClient.get("/api/v1/workflows");
      if (Array.isArray(data) && data.length > 0) {
        setWorkflows(data);
      } else {
        // Default initial workflows
        setWorkflows([
          {
            id: 1,
            name: "Automated Stockout Replenishment",
            description: "Monitors warehouse safety stock and auto-generates purchase orders when thresholds breach.",
            active: true,
            agents: ["Inventory Agent", "Procurement Agent", "Finance Agent"]
          },
          {
            id: 2,
            name: "High-Value Invoice Cross-Validation",
            description: "Validates AP vendor invoices against purchase orders and dispatches approval requests.",
            active: true,
            agents: ["Finance Agent", "Compliance Agent"]
          },
          {
            id: 3,
            name: "Lead Qualification & Deal Pipeline",
            description: "Enriches inbound CRM deals and routes opportunities to appropriate account managers.",
            active: false,
            agents: ["Sales Agent", "Analytics Agent"]
          }
        ]);
      }
    } catch (err: any) {
      // Fallback with demo pipelines
      setWorkflows([
        {
          id: 1,
          name: "Automated Stockout Replenishment",
          description: "Monitors warehouse safety stock and auto-generates purchase orders when thresholds breach.",
          active: true,
          agents: ["Inventory Agent", "Procurement Agent", "Finance Agent"]
        },
        {
          id: 2,
          name: "High-Value Invoice Cross-Validation",
          description: "Validates AP vendor invoices against purchase orders and dispatches approval requests.",
          active: true,
          agents: ["Finance Agent", "Compliance Agent"]
        },
        {
          id: 3,
          name: "Lead Qualification & Deal Pipeline",
          description: "Enriches inbound CRM deals and routes opportunities to appropriate account managers.",
          active: false,
          agents: ["Sales Agent", "Analytics Agent"]
        }
      ]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWorkflows();
  }, [loadWorkflows]);

  const toggleWorkflow = (id: number | string) => {
    if (!isOperator) {
      alert("Unauthorized: Viewer role cannot modify workflow states.");
      return;
    }
    setWorkflows(workflows.map(wf => wf.id === id ? { ...wf, active: !wf.active } : wf));
  };

  const toggleAgentNode = (agent: string) => {
    if (selectedAgentNodes.includes(agent)) {
      setSelectedAgentNodes(selectedAgentNodes.filter(a => a !== agent));
    } else {
      setSelectedAgentNodes([...selectedAgentNodes, agent]);
    }
  };

  const handleCreateWorkflow = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isOperator) {
      alert("Unauthorized: Viewer role cannot deploy workflows.");
      return;
    }
    if (!newWfName.trim()) return;
    setWorkflows([
      {
        id: Date.now(),
        name: newWfName,
        description: newWfDesc || 'Custom agentic multi-node workflow pipeline.',
        active: true,
        agents: selectedAgentNodes.length ? selectedAgentNodes : ['Agent Orchestrator']
      },
      ...workflows
    ]);
    setIsBuilderOpen(false);
    setNewWfName("");
    setNewWfDesc("");
  };

  const filteredWorkflows = useMemo(() => {
    return workflows.filter(wf => {
      const matchesTab = filterTab === "all" ? true : filterTab === "active" ? wf.active : !wf.active;
      const matchesSearch = wf.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            wf.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            wf.agents.some(a => a.toLowerCase().includes(searchQuery.toLowerCase()));
      return matchesTab && matchesSearch;
    });
  }, [workflows, filterTab, searchQuery]);

  const totalFiltered = filteredWorkflows.length;
  const paginatedWorkflows = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredWorkflows.slice(start, start + pageSize);
  }, [filteredWorkflows, currentPage, pageSize]);

  return (
    <main className="main">
      <div className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="crumb">Workflows</span>
          <span style={{ color: 'var(--text-faint)' }}>/</span>
          <span className="crumb-sub">Manage & Orchestrate Multi-Agent Pipelines</span>
          <RoleBadge role={user?.role} />
        </div>
        {isOperator && (
          <button 
            className="btn btn-primary" 
            style={{ marginLeft: 'auto', background: 'var(--ai-core)' }}
            onClick={() => setIsBuilderOpen(true)}
          >
            + Build New Workflow Pipeline
          </button>
        )}
      </div>

      <div className="content" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        
        {error && <ErrorState message={error} onRetry={loadWorkflows} />}

        {/* Toolbar & Filter */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-soft)', paddingBottom: '12px', gap: '16px' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button 
              className={`btn ${filterTab === 'all' ? 'btn-primary' : 'btn-secondary'} text-xs`}
              onClick={() => { setFilterTab("all"); setCurrentPage(1); }}
              style={{ background: filterTab === 'all' ? 'var(--ai-core)' : undefined }}
            >
              All Pipelines ({workflows.length})
            </button>
            <button 
              className={`btn ${filterTab === 'active' ? 'btn-primary' : 'btn-secondary'} text-xs`}
              onClick={() => { setFilterTab("active"); setCurrentPage(1); }}
              style={{ background: filterTab === 'active' ? 'var(--verified)' : undefined, color: filterTab === 'active' ? '#000' : undefined }}
            >
              Active ({workflows.filter(w => w.active).length})
            </button>
            <button 
              className={`btn ${filterTab === 'paused' ? 'btn-primary' : 'btn-secondary'} text-xs`}
              onClick={() => { setFilterTab("paused"); setCurrentPage(1); }}
            >
              Paused ({workflows.filter(w => !w.active).length})
            </button>
          </div>

          <div style={{ position: 'relative', width: '280px' }}>
            <input 
              type="text"
              className="ai-cmd-input"
              style={{ width: '100%', padding: '8px 12px 8px 32px', fontSize: '13px', borderRadius: '8px' }}
              placeholder="Search workflows or nodes..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
            />
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-faint)' }}>
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
          </div>
        </div>

        {/* Loading Skeletons */}
        {loading ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '24px' }}>
            {[1, 2, 3].map(i => (
              <div key={i} className="skeleton" style={{ height: '200px', borderRadius: '16px' }}></div>
            ))}
          </div>
        ) : paginatedWorkflows.length === 0 ? (
          <EmptyState 
            icon="⚡"
            title="No Workflows Found"
            description={searchQuery ? `No workflows matching "${searchQuery}".` : "No custom multi-agent workflow pipelines configured for this filter."}
            actionLabel={isOperator ? "+ Build New Workflow Pipeline" : undefined}
            onAction={isOperator ? () => setIsBuilderOpen(true) : undefined}
          />
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '24px' }}>
              {paginatedWorkflows.map((wf) => (
                <div key={wf.id} className="panel" style={{ padding: '24px', borderRadius: '16px', display: 'flex', flexDirection: 'column', gap: '16px', borderLeft: `4px solid ${wf.active ? 'var(--verified)' : 'var(--border)'}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <h3 style={{ fontSize: '16px', fontWeight: 600, margin: 0, color: 'var(--text)' }}>{wf.name}</h3>
                      <p style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '4px', lineHeight: '1.4' }}>{wf.description}</p>
                    </div>
                    {isOperator ? (
                      <button 
                        onClick={() => toggleWorkflow(wf.id)}
                        style={{ 
                          background: wf.active ? 'var(--verified-soft)' : 'var(--surface-2)', 
                          color: wf.active ? 'var(--verified)' : 'var(--text-dim)',
                          border: 'none',
                          padding: '4px 10px',
                          borderRadius: '12px',
                          fontSize: '11px',
                          fontWeight: 600,
                          cursor: 'pointer'
                        }}
                      >
                        {wf.active ? '🟢 Active' : '⚪ Paused'}
                      </button>
                    ) : (
                      <span 
                        style={{ 
                          background: wf.active ? 'var(--verified-soft)' : 'var(--surface-2)', 
                          color: wf.active ? 'var(--verified)' : 'var(--text-dim)',
                          padding: '4px 10px',
                          borderRadius: '12px',
                          fontSize: '11px',
                          fontWeight: 600
                        }}
                      >
                        {wf.active ? 'Active' : 'Paused'}
                      </span>
                    )}
                  </div>

                  <div style={{ background: 'var(--bg)', borderRadius: '10px', padding: '12px', border: '1px solid var(--border-soft)', marginTop: 'auto' }}>
                    <div className="text-xs font-semibold text-faint uppercase mb-2">Connected Agent Nodes ({wf.agents.length})</div>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      {wf.agents.map((ag: string) => (
                        <span key={ag} className="badge" style={{ background: 'var(--surface-2)', color: 'var(--ai-core)', fontSize: '11px' }}>
                          {ag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <Pagination 
              currentPage={currentPage}
              totalItems={totalFiltered}
              pageSize={pageSize}
              onPageChange={setCurrentPage}
              onPageSizeChange={setPageSize}
              pageSizeOptions={[6, 12, 24]}
            />
          </>
        )}
      </div>

      {/* Workflow Builder Modal */}
      {isBuilderOpen && isOperator && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '16px', padding: '32px', width: '100%', maxWidth: '520px', boxShadow: '0 20px 40px rgba(0,0,0,0.3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 className="font-semibold text-lg">Build Agentic Workflow Pipeline</h2>
              <button onClick={() => setIsBuilderOpen(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', fontSize: '20px', cursor: 'pointer' }}>✕</button>
            </div>

            <form onSubmit={handleCreateWorkflow}>
              <div style={{ marginBottom: '16px' }}>
                <label className="text-xs font-semibold uppercase text-faint mb-1 block">Workflow Name</label>
                <input type="text" required className="ai-cmd-input" style={{ width: '100%', padding: '10px 14px' }} placeholder="e.g., Automated Stockout Replenishment" value={newWfName} onChange={(e) => setNewWfName(e.target.value)} />
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label className="text-xs font-semibold uppercase text-faint mb-1 block">Description</label>
                <input type="text" className="ai-cmd-input" style={{ width: '100%', padding: '10px 14px' }} placeholder="Describe pipeline trigger and action..." value={newWfDesc} onChange={(e) => setNewWfDesc(e.target.value)} />
              </div>

              <div style={{ marginBottom: '24px' }}>
                <label className="text-xs font-semibold uppercase text-faint mb-2 block">Select Agent Nodes</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  {["Finance Agent", "Inventory Agent", "Procurement Agent", "Sales Agent", "Operations Agent", "Compliance Agent", "Analytics Agent"].map((ag) => (
                    <div 
                      key={ag}
                      onClick={() => toggleAgentNode(ag)}
                      style={{ 
                        padding: '10px', 
                        borderRadius: '8px', 
                        border: `1px solid ${selectedAgentNodes.includes(ag) ? 'var(--ai-core)' : 'var(--border)'}`,
                        background: selectedAgentNodes.includes(ag) ? 'var(--surface-2)' : 'var(--bg)',
                        cursor: 'pointer',
                        fontSize: '12px'
                      }}
                    >
                      {selectedAgentNodes.includes(ag) ? '✓ ' : ''}{ag}
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsBuilderOpen(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" style={{ flex: 1, background: 'var(--ai-core)' }}>Deploy Workflow Pipeline</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
