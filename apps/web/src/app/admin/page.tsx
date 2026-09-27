"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { apiClient } from "../../lib/api-client";
import { useAuth } from "../../lib/auth-context";
import { Pagination } from "../../components/Pagination";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { RoleBadge } from "../../components/RoleBadge";

interface TenantSummary {
  id: string;
  name: string;
  plan: string;
  status: string;
  created_at: string;
  member_count: number;
  active_agents: number;
  storage_mb: number;
}

export default function SuperAdminPage() {
  const { user, canPerform } = useAuth();
  const isAdmin = canPerform(["owner", "admin"]);

  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [planFilter, setPlanFilter] = useState<string>("all");

  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);

  const [selectedTenant, setSelectedTenant] = useState<TenantSummary | null>(null);
  const [overridePlan, setOverridePlan] = useState("growth");
  const [systemMetrics, setSystemMetrics] = useState({
    apiStatus: "Healthy",
    dbPool: "18 / 50 Active",
    redisStatus: "Connected",
    celeryWorkers: "4 Running",
    uptime: "99.98%",
  });

  const loadAdminData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // In a live cluster, this queries super-admin multi-tenant telemetry
      setTenants([
        {
          id: "tenant-001",
          name: "Acme Industrial Corp",
          plan: "enterprise",
          status: "active",
          created_at: "2026-01-10",
          member_count: 42,
          active_agents: 6,
          storage_mb: 2450,
        },
        {
          id: "tenant-002",
          name: "Northbeam Global Labs",
          plan: "growth",
          status: "active",
          created_at: "2026-03-14",
          member_count: 15,
          active_agents: 4,
          storage_mb: 890,
        },
        {
          id: "tenant-003",
          name: "Apex Logistics & Supply",
          plan: "starter",
          status: "past_due",
          created_at: "2026-06-01",
          member_count: 8,
          active_agents: 2,
          storage_mb: 410,
        },
        {
          id: "tenant-004",
          name: "OmniTech Dynamics",
          plan: "free",
          status: "active",
          created_at: "2026-08-20",
          member_count: 3,
          active_agents: 1,
          storage_mb: 85,
        },
        {
          id: "tenant-005",
          name: "Helios Energy Systems",
          plan: "enterprise",
          status: "active",
          created_at: "2026-09-02",
          member_count: 85,
          active_agents: 8,
          storage_mb: 5120,
        },
        {
          id: "tenant-006",
          name: "Vanguard Retail Ventures",
          plan: "growth",
          status: "active",
          created_at: "2026-09-15",
          member_count: 22,
          active_agents: 5,
          storage_mb: 1200,
        }
      ]);
    } catch (err: any) {
      setError(err?.message || "Failed to load tenant telemetry");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAdminData();
  }, [loadAdminData]);

  const handleUpdatePlan = (tenantId: string) => {
    if (!isAdmin) {
      alert("Unauthorized: Only Admins and Owners can override tenant subscriptions.");
      return;
    }
    setTenants((prev) =>
      prev.map((t) => (t.id === tenantId ? { ...t, plan: overridePlan } : t))
    );
    setSelectedTenant(null);
    alert(`Tenant ${tenantId} subscription tier successfully updated to ${overridePlan.toUpperCase()}.`);
  };

  const filteredTenants = useMemo(() => {
    return tenants.filter(t => {
      const matchesSearch = t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            t.id.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesPlan = planFilter === "all" ? true : t.plan === planFilter;
      return matchesSearch && matchesPlan;
    });
  }, [tenants, searchQuery, planFilter]);

  const totalFiltered = filteredTenants.length;
  const paginatedTenants = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredTenants.slice(start, start + pageSize);
  }, [filteredTenants, currentPage, pageSize]);

  return (
    <main className="main">
      <div className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="crumb">Super-Admin Console</span>
          <span style={{ color: 'var(--text-faint)' }}>/</span>
          <span className="crumb-sub">Multi-tenant management &amp; system health telemetry</span>
          <RoleBadge role={user?.role} />
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: "12px" }}>
          <button onClick={loadAdminData} className="panel-action">
            ↻ Refresh Metrics
          </button>
        </div>
      </div>

      <div className="content" style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
        {error && <ErrorState message={error} onRetry={loadAdminData} />}

        {/* System Health Dashboard */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px" }}>
          <div className="kpi-card">
            <div className="kpi-label">API Status</div>
            <div className="kpi-val" style={{ color: "var(--verified)" }}>{systemMetrics.apiStatus}</div>
            <div className="kpi-delta active">Prometheus /metrics live</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Database Pool</div>
            <div className="kpi-val">{systemMetrics.dbPool}</div>
            <div className="kpi-delta flat">PostgreSQL RLS Active</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Worker Tasks</div>
            <div className="kpi-val" style={{ color: "var(--ai-core)" }}>{systemMetrics.celeryWorkers}</div>
            <div className="kpi-delta active">LangGraph &amp; Connectors</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Platform Uptime</div>
            <div className="kpi-val">{systemMetrics.uptime}</div>
            <div className="kpi-delta flat">30-Day SLA Window</div>
          </div>
        </div>

        {/* Search & Filter Toolbar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-soft)", paddingBottom: "12px", gap: "16px" }}>
          <div style={{ display: "flex", gap: "8px" }}>
            {["all", "enterprise", "growth", "starter", "free"].map(p => (
              <button
                key={p}
                className={`btn ${planFilter === p ? "btn-primary" : "btn-secondary"} text-xs`}
                onClick={() => { setPlanFilter(p); setCurrentPage(1); }}
                style={{ background: planFilter === p ? "var(--ai-core)" : undefined }}
              >
                {p.charAt(0).toUpperCase() + p.slice(1)} {p !== "all" ? `(${tenants.filter(t => t.plan === p).length})` : `(${tenants.length})`}
              </button>
            ))}
          </div>

          <div style={{ position: "relative", width: "280px" }}>
            <input 
              type="text"
              className="ai-cmd-input"
              style={{ width: "100%", padding: "8px 12px 8px 32px", fontSize: "13px", borderRadius: "8px" }}
              placeholder="Search by tenant name or ID..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
            />
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)", color: "var(--text-faint)" }}>
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
          </div>
        </div>

        {/* Tenant Management Table */}
        <div className="panel" style={{ padding: "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
            <div>
              <h2 style={{ fontSize: "18px", fontWeight: 600 }}>Active Enterprise Tenants</h2>
              <p style={{ fontSize: "13px", color: "var(--text-dim)" }}>
                Inspect tenant usage metrics, override subscription entitlements, and monitor RLS boundary health.
              </p>
            </div>
          </div>

          {loading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="skeleton" style={{ height: "50px", borderRadius: "8px" }}></div>
              ))}
            </div>
          ) : paginatedTenants.length === 0 ? (
            <EmptyState 
              icon="🏢"
              title="No Tenants Found"
              description={searchQuery ? `No organizations matching "${searchQuery}".` : "No enterprise tenants matching this filter."}
            />
          ) : (
            <>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Organization</th>
                      <th>Plan Tier</th>
                      <th>Billing Status</th>
                      <th>Seats</th>
                      <th>Active Agents</th>
                      <th>Storage</th>
                      <th style={{ textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedTenants.map((t) => (
                      <tr key={t.id}>
                        <td>
                          <div style={{ fontWeight: 600, color: "var(--text)" }}>{t.name}</div>
                          <div className="mono text-xs text-faint">{t.id}</div>
                        </td>
                        <td>
                          <span
                            className="badge"
                            style={{
                              background:
                                t.plan === "enterprise"
                                  ? "rgba(99, 102, 241, 0.15)"
                                  : t.plan === "growth"
                                  ? "rgba(16, 185, 129, 0.15)"
                                  : "var(--surface-2)",
                              color:
                                t.plan === "enterprise"
                                  ? "#818cf8"
                                  : t.plan === "growth"
                                  ? "#34d399"
                                  : "var(--text-dim)",
                            }}
                          >
                            {t.plan}
                          </span>
                        </td>
                        <td>
                          <span
                            style={{
                              color:
                                t.status === "active"
                                  ? "var(--verified)"
                                  : t.status === "past_due"
                                  ? "var(--danger)"
                                  : "var(--text-dim)",
                              fontWeight: 500,
                              fontSize: "12px"
                            }}
                          >
                            ● {t.status}
                          </span>
                        </td>
                        <td>{t.member_count} users</td>
                        <td>{t.active_agents} agents</td>
                        <td className="mono text-xs">{t.storage_mb} MB</td>
                        <td style={{ textAlign: "right" }}>
                          {isAdmin ? (
                            <button
                              onClick={() => {
                                setSelectedTenant(t);
                                setOverridePlan(t.plan);
                              }}
                              className="btn btn-secondary text-xs"
                              style={{ padding: "4px 10px" }}
                            >
                              Edit Entitlements
                            </button>
                          ) : (
                            <span className="text-xs text-dim" style={{ fontStyle: "italic" }}>View only</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <Pagination 
                currentPage={currentPage}
                totalItems={totalFiltered}
                pageSize={pageSize}
                onPageChange={setCurrentPage}
                onPageSizeChange={setPageSize}
                pageSizeOptions={[5, 10, 20]}
              />
            </>
          )}
        </div>

        {/* Plan Override Modal */}
        {selectedTenant && isAdmin && (
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: "rgba(0, 0, 0, 0.7)",
              backdropFilter: "blur(4px)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
            }}
          >
            <div
              className="panel"
              style={{
                width: "100%",
                maxWidth: "480px",
                padding: "24px",
                background: "var(--surface)",
                borderRadius: "12px",
              }}
            >
              <h3 style={{ fontSize: "18px", fontWeight: 600, marginBottom: "8px" }}>
                Modify Tenant Entitlement: {selectedTenant.name}
              </h3>
              <p style={{ fontSize: "13px", color: "var(--text-dim)", marginBottom: "20px" }}>
                Admin override manually adjusts quotas without going through Stripe webhook synchronization.
              </p>

              <div style={{ marginBottom: "20px" }}>
                <label style={{ display: "block", fontSize: "12px", color: "var(--text-dim)", marginBottom: "6px" }}>
                  Select Subscription Plan
                </label>
                <select
                  value={overridePlan}
                  onChange={(e) => setOverridePlan(e.target.value)}
                  className="ai-cmd-input"
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    background: "var(--bg)",
                    border: "1px solid var(--border)",
                    color: "var(--text)",
                    borderRadius: "6px",
                  }}
                >
                  <option value="free">Free Tier</option>
                  <option value="starter">Starter Plan ($49/mo)</option>
                  <option value="growth">Growth Plan ($199/mo)</option>
                  <option value="enterprise">Enterprise Plan ($599/mo)</option>
                </select>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px" }}>
                <button
                  onClick={() => setSelectedTenant(null)}
                  className="btn btn-secondary"
                  style={{ padding: "6px 14px" }}
                >
                  Cancel
                </button>
                <button
                  onClick={() => handleUpdatePlan(selectedTenant.id)}
                  className="btn btn-primary"
                  style={{ padding: "6px 14px", background: "var(--ai-core)", color: "#fff" }}
                >
                  Save Override
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
