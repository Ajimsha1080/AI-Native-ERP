"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";
import { apiClient } from "../../lib/api-client";
import { useAuth } from "../../lib/auth-context";
import { Pagination } from "../../components/Pagination";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { RoleBadge } from "../../components/RoleBadge";

interface OpportunityItem {
  id?: string;
  name: string;
  account: string;
  value: string;
  stage: string;
  probability: string;
  expected_close?: string;
}

interface SalesDashboardData {
  insight?: { title: string; description: string };
  kpis?: Array<{ label: string; value: string; delta: string; trend: string }>;
  opportunities?: OpportunityItem[];
}

export default function SalesPage() {
  const { user, canPerform } = useAuth();
  const [data, setData] = useState<SalesDashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);

  const canManageSales = canPerform(["owner", "admin", "manager"]);

  const fetchData = useCallback(() => {
    setIsLoading(true);
    setError(null);
    apiClient
      .get("/api/v1/dashboard/sales")
      .then((res) => {
        setData(res);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load sales pipeline");
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Filter opportunities
  const filteredOpportunities = useMemo(() => {
    const list = data?.opportunities || [];
    return list.filter((opp) => {
      const matchSearch =
        opp.name.toLowerCase().includes(search.toLowerCase()) ||
        opp.account.toLowerCase().includes(search.toLowerCase());
      const matchStage =
        stageFilter === "all" || opp.stage.toLowerCase().includes(stageFilter.toLowerCase());
      return matchSearch && matchStage;
    });
  }, [data, search, stageFilter]);

  // Paginated opportunities
  const paginatedOpportunities = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredOpportunities.slice(start, start + pageSize);
  }, [filteredOpportunities, page, pageSize]);

  return (
    <main className="main">
      <div className="topbar">
        <div className="flex items-center gap-3">
          <div className="breadcrumb">Sales</div>
          <RoleBadge />
        </div>
        <div className="search-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search accounts, deals..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
          <span className="cmd-k">⌘K</span>
        </div>
      </div>

      <div className="content">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
          <div>
            <h1 className="display" style={{ fontSize: "24px" }}>Sales Pipeline</h1>
            <p className="text-sm text-dim">Active deal conversions, pipeline velocity, and revenue forecasting</p>
          </div>
          <div className="flex items-center gap-2">
            {canManageSales && (
              <button
                className="btn btn-secondary"
                onClick={() => alert("New deal creation dialog opened.")}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 5v14M5 12h14" />
                </svg>
                New Opportunity
              </button>
            )}
            <Link href="/?context=Sales" className="btn btn-primary" style={{ background: "var(--ai-core)" }}>
              Ask Sales Agent
            </Link>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            <div className="skeleton" style={{ height: "64px", borderRadius: "8px" }} />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "16px" }}>
              <div className="skeleton" style={{ height: "110px", borderRadius: "8px" }} />
              <div className="skeleton" style={{ height: "110px", borderRadius: "8px" }} />
              <div className="skeleton" style={{ height: "110px", borderRadius: "8px" }} />
              <div className="skeleton" style={{ height: "110px", borderRadius: "8px" }} />
            </div>
            <div className="skeleton" style={{ height: "320px", borderRadius: "8px" }} />
          </div>
        )}

        {/* Error State */}
        {!isLoading && error && (
          <ErrorState
            title="Failed to load sales pipeline"
            message={error}
            onRetry={fetchData}
          />
        )}

        {/* Loaded Content */}
        {!isLoading && !error && data && (
          <>
            {/* AI Insight Card */}
            {data.insight && (
              <div className="ai-insight" style={{ marginBottom: "24px" }}>
                <div className="ai-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83" />
                  </svg>
                </div>
                <div>
                  <h4 className="font-semibold text-sm mb-1" style={{ color: "var(--ai-core)" }}>
                    {data.insight.title || "Sales Stream Active"}
                  </h4>
                  <p className="text-sm text-dim">
                    {data.insight.description || "Omnichannel sales pipeline connected."}{" "}
                    <Link href="/?context=Sales" style={{ color: "var(--ai-core)", textDecoration: "underline" }}>
                      Run Win Probability Prediction
                    </Link>
                  </p>
                </div>
              </div>
            )}

            {/* KPI Cards */}
            <div className="kpi-grid" style={{ marginBottom: "32px" }}>
              {(data.kpis || []).map((kpi, i) => (
                <div key={i} className="kpi-card">
                  <div className="kpi-label">{kpi.label}</div>
                  <div className="kpi-val">{kpi.value}</div>
                  <div className={`kpi-delta ${kpi.trend}`}>{kpi.delta}</div>
                </div>
              ))}
            </div>

            {/* Filter Toolbar */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div style={{ display: "flex", gap: "8px" }}>
                {["all", "discovery", "proposal", "negotiation", "closed-won"].map((st) => (
                  <button
                    key={st}
                    onClick={() => {
                      setStageFilter(st);
                      setPage(1);
                    }}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: 500,
                      border: "1px solid " + (stageFilter === st ? "var(--accent)" : "var(--border)"),
                      background: stageFilter === st ? "var(--accent)" : "var(--surface)",
                      color: stageFilter === st ? "#ffffff" : "var(--text)",
                      cursor: "pointer",
                      textTransform: "capitalize",
                    }}
                  >
                    {st.replace("-", " ")}
                  </button>
                ))}
              </div>
              <span className="text-xs text-dim">
                {filteredOpportunities.length} deals in pipeline
              </span>
            </div>

            {/* Empty State vs Opportunities Table */}
            {filteredOpportunities.length === 0 ? (
              <EmptyState
                title="No sales opportunities found"
                description={
                  search || stageFilter !== "all"
                    ? "No opportunities match your current filter criteria."
                    : "Your sales pipeline is empty. Create a deal or sync with CRM connectors."
                }
                actionLabel={search || stageFilter !== "all" ? "Reset Filters" : "Create Opportunity"}
                onAction={() => {
                  setSearch("");
                  setStageFilter("all");
                }}
                canPerformAction={true}
              />
            ) : (
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Opportunity</th>
                      <th>Account</th>
                      <th>Deal Value</th>
                      <th>Pipeline Stage</th>
                      <th>Win Probability</th>
                      {canManageSales && <th style={{ textAlign: "right" }}>Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedOpportunities.map((opp, i) => (
                      <tr key={i}>
                        <td className="font-medium">{opp.name}</td>
                        <td className="text-dim">{opp.account}</td>
                        <td className="mono" style={{ fontWeight: 600 }}>{opp.value}</td>
                        <td>
                          <span
                            className={`badge ${
                              opp.stage.toLowerCase().includes("won")
                                ? "active"
                                : opp.stage.toLowerCase().includes("discovery")
                                ? "warning"
                                : "ai"
                            }`}
                          >
                            {opp.stage}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <div style={{ width: "48px", height: "6px", background: "var(--surface-2)", borderRadius: "3px", overflow: "hidden" }}>
                              <div
                                style={{
                                  width: opp.probability,
                                  height: "100%",
                                  background: opp.stage.toLowerCase().includes("won") ? "var(--verified)" : "var(--ai-core)",
                                }}
                              />
                            </div>
                            <span className="mono text-xs">{opp.probability}</span>
                          </div>
                        </td>
                        {canManageSales && (
                          <td style={{ textAlign: "right" }}>
                            <button
                              className="btn btn-secondary"
                              style={{ padding: "4px 8px", fontSize: "11px" }}
                              onClick={() => alert(`Update stage for ${opp.name}`)}
                            >
                              Advance
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Pagination Controls */}
                <Pagination
                  currentPage={page}
                  totalItems={filteredOpportunities.length}
                  pageSize={pageSize}
                  onPageChange={setPage}
                  onPageSizeChange={(newSize) => {
                    setPageSize(newSize);
                    setPage(1);
                  }}
                />
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
