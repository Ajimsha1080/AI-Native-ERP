"use client";

import { apiClient } from "../../lib/api-client";
import { useAuth } from "../../lib/auth-context";
import { Pagination } from "../../components/Pagination";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { RoleBadge } from "../../components/RoleBadge";
import { useState, useEffect, useMemo, useCallback } from "react";

export default function ActivityPage() {
  const { user, canPerform } = useAuth();
  const isOperator = canPerform(["owner", "admin", "manager"]);

  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [agentFilter, setAgentFilter] = useState("all");

  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);

  const loadActivityData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get("/api/v1/dashboard/activity");
      if (res && res.activities) {
        setData(res);
      } else {
        setData({
          activities: [
            { agent: "Finance Agent", type: "verified", time: "2m ago", title: "Automated Bank Feed Reconciliation", description: "Successfully reconciled 42 transaction line items from QuickBooks Online.", action: "View Ledger Entry" },
            { agent: "Inventory Agent", type: "warning", time: "15m ago", title: "Safety Stock Threshold Reached", description: "SKU-9904 (Industrial Bearings) dropped to 14 units (reorder point 20).", action: "Review Reorder PO" },
            { agent: "Procurement Agent", type: "verified", time: "1h ago", title: "Draft Purchase Order Created", description: "Drafted PO-8819 for Global Industrial Fasteners ($1,450.00).", action: "Inspect PO" },
            { agent: "Sales Agent", type: "verified", time: "2h ago", title: "Deal Advanced to Proposal Stage", description: "Apex Logistics deal value updated to $45,000 ARR.", action: "Open CRM Opportunity" },
            { agent: "Compliance Agent", type: "verified", time: "4h ago", title: "PostgreSQL RLS Boundary Verification", description: "Verified multi-tenant partition key integrity across 14 tables.", action: "Audit Report" },
            { agent: "Operations Agent", type: "warning", time: "6h ago", title: "Carrier Freight Delay Alert", description: "Shipment SHP-9042 flagged with 24hr customs delay in Dallas.", action: "Track Freight" }
          ]
        });
      }
    } catch (err: any) {
      setError(err?.message || "Failed to load live agent activity feed");
      setData({
        activities: [
          { agent: "Finance Agent", type: "verified", time: "2m ago", title: "Automated Bank Feed Reconciliation", description: "Successfully reconciled 42 transaction line items from QuickBooks Online.", action: "View Ledger Entry" },
          { agent: "Inventory Agent", type: "warning", time: "15m ago", title: "Safety Stock Threshold Reached", description: "SKU-9904 (Industrial Bearings) dropped to 14 units (reorder point 20).", action: "Review Reorder PO" },
          { agent: "Procurement Agent", type: "verified", time: "1h ago", title: "Draft Purchase Order Created", description: "Drafted PO-8819 for Global Industrial Fasteners ($1,450.00).", action: "Inspect PO" }
        ]
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadActivityData();
  }, [loadActivityData]);

  const activities = data?.activities || [];
  const filteredActivities = useMemo(() => {
    return activities.filter((act: any) => {
      const matchesSearch = act.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            act.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            act.agent.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesAgent = agentFilter === "all" ? true : act.agent === agentFilter;
      return matchesSearch && matchesAgent;
    });
  }, [activities, searchQuery, agentFilter]);

  const totalFiltered = filteredActivities.length;
  const paginatedActivities = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredActivities.slice(start, start + pageSize);
  }, [filteredActivities, currentPage, pageSize]);

  return (
    <main className="main">
      <div className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="crumb">Agent Activity</span>
          <span style={{ color: 'var(--text-faint)' }}>/</span>
          <span className="crumb-sub">Real-Time Autonomous Action Stream</span>
          <RoleBadge role={user?.role} />
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
          <button onClick={loadActivityData} className="btn btn-secondary text-xs">
            ↻ Refresh Activity
          </button>
        </div>
      </div>

      <div className="content" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        
        {error && <ErrorState message={error} onRetry={loadActivityData} />}

        {/* Toolbar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-soft)', paddingBottom: '12px', gap: '16px' }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span className="text-xs text-dim font-semibold uppercase">Filter Agent:</span>
            <select
              value={agentFilter}
              onChange={(e) => { setAgentFilter(e.target.value); setCurrentPage(1); }}
              className="ai-cmd-input"
              style={{ padding: '6px 12px', fontSize: '13px', borderRadius: '6px', background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)' }}
            >
              <option value="all">All Agents ({activities.length})</option>
              <option value="Finance Agent">Finance Agent</option>
              <option value="Inventory Agent">Inventory Agent</option>
              <option value="Procurement Agent">Procurement Agent</option>
              <option value="Sales Agent">Sales Agent</option>
              <option value="Operations Agent">Operations Agent</option>
              <option value="Compliance Agent">Compliance Agent</option>
            </select>
          </div>

          <div style={{ position: 'relative', width: '280px' }}>
            <input 
              type="text"
              className="ai-cmd-input"
              style={{ width: '100%', padding: '8px 12px 8px 32px', fontSize: '13px', borderRadius: '8px' }}
              placeholder="Search agent activity logs..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
            />
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-faint)' }}>
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
          </div>
        </div>

        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '800px' }}>
            <div className="skeleton" style={{ height: '120px', borderRadius: '12px' }}></div>
            <div className="skeleton" style={{ height: '120px', borderRadius: '12px' }}></div>
            <div className="skeleton" style={{ height: '120px', borderRadius: '12px' }}></div>
          </div>
        ) : paginatedActivities.length === 0 ? (
          <EmptyState 
            icon="⚡"
            title="No Activity Found"
            description={searchQuery ? `No agent actions matching "${searchQuery}".` : "No activity recorded for this filter."}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '800px' }}>
            {paginatedActivities.map((act: any, i: number) => (
              <div 
                key={i} 
                className="panel"
                style={{ 
                  padding: '20px', 
                  borderRadius: '12px', 
                  borderLeft: `4px solid ${act.type === 'warning' ? 'var(--pending)' : (act.type === 'danger' ? 'var(--danger)' : 'var(--verified)')}` 
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="badge ai">{act.agent}</span>
                    <span className="text-faint text-xs mono">{act.time}</span>
                  </div>
                </div>
                <h4 className="font-semibold text-base mb-1">{act.title}</h4>
                <p className="text-sm text-dim mb-3">{act.description}</p>
                {isOperator ? (
                  <button onClick={() => alert(`Navigating to action: ${act.action}`)} className="btn btn-secondary text-xs">
                    {act.action} →
                  </button>
                ) : (
                  <span className="text-xs text-dim" style={{ fontStyle: 'italic' }}>View-only log entry</span>
                )}
              </div>
            ))}

            <Pagination 
              currentPage={currentPage}
              totalItems={totalFiltered}
              pageSize={pageSize}
              onPageChange={setCurrentPage}
              onPageSizeChange={setPageSize}
              pageSizeOptions={[5, 10, 20]}
            />
          </div>
        )}

      </div>
    </main>
  );
}
