"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { apiClient } from "../../lib/api-client";
import { useAuth } from "../../lib/auth-context";
import { Pagination } from "../../components/Pagination";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { RoleBadge } from "../../components/RoleBadge";

interface AuditLogItem {
  id?: string;
  time: string;
  actor: string;
  action: string;
  system: string;
  risk: string;
  status: string;
  is_ai?: boolean;
}

interface AuditDashboardData {
  logs?: AuditLogItem[];
}

export default function AuditPage() {
  const { user, canPerform } = useAuth();
  const [data, setData] = useState<AuditDashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const canExportLogs = canPerform(["owner", "admin", "manager"]);

  const fetchLogs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.get("/api/v1/dashboard/audit");
      setData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load audit logs");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  // Filter logs
  const filteredLogs = useMemo(() => {
    const list = data?.logs || [];
    return list.filter((log) => {
      const matchSearch =
        log.actor.toLowerCase().includes(search.toLowerCase()) ||
        log.action.toLowerCase().includes(search.toLowerCase()) ||
        log.system.toLowerCase().includes(search.toLowerCase());
      const matchRisk =
        riskFilter === "all" || log.risk.toLowerCase() === riskFilter.toLowerCase();
      return matchSearch && matchRisk;
    });
  }, [data, search, riskFilter]);

  // Paginated logs
  const paginatedLogs = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredLogs.slice(start, start + pageSize);
  }, [filteredLogs, page, pageSize]);

  return (
    <main className="main">
      <div className="topbar">
        <div className="flex items-center gap-3">
          <div className="breadcrumb">Audit Logs</div>
          <RoleBadge />
        </div>
        <div className="search-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search events, Trace IDs..."
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
            <h1 className="display" style={{ fontSize: "24px" }}>System Audit Trail</h1>
            <p className="text-dim text-sm" style={{ marginTop: "4px" }}>
              Immutable ledger of all human and AI actions across connected systems.
            </p>
          </div>
          {canExportLogs && (
            <button
              className="btn btn-secondary"
              onClick={() => alert("Audit log export generated (CSV format).")}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Export Logs (CSV)
            </button>
          )}
        </div>

        {/* Loading State */}
        {isLoading && (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div className="skeleton" style={{ height: "48px", borderRadius: "8px" }} />
            <div className="skeleton" style={{ height: "350px", borderRadius: "8px" }} />
          </div>
        )}

        {/* Error State */}
        {!isLoading && error && (
          <ErrorState
            title="Failed to load system audit trail"
            message={error}
            onRetry={fetchLogs}
          />
        )}

        {/* Loaded Logs */}
        {!isLoading && !error && data && (
          <>
            {/* Filter Toolbar */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <div style={{ display: "flex", gap: "8px" }}>
                {["all", "High", "Medium", "Low"].map((rf) => (
                  <button
                    key={rf}
                    onClick={() => {
                      setRiskFilter(rf);
                      setPage(1);
                    }}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: 500,
                      border: "1px solid " + (riskFilter === rf ? "var(--accent)" : "var(--border)"),
                      background: riskFilter === rf ? "var(--accent)" : "var(--surface)",
                      color: riskFilter === rf ? "#ffffff" : "var(--text)",
                      cursor: "pointer",
                    }}
                  >
                    {rf === "all" ? "All Risk Levels" : `${rf} Risk`}
                  </button>
                ))}
              </div>
              <span className="text-xs text-dim">{filteredLogs.length} events logged</span>
            </div>

            {/* Empty State vs Table */}
            {filteredLogs.length === 0 ? (
              <EmptyState
                title="No audit events found"
                description={
                  search || riskFilter !== "all"
                    ? "No audit events match your search or filter."
                    : "The system audit trail is currently empty."
                }
                actionLabel={search || riskFilter !== "all" ? "Reset Filters" : undefined}
                onAction={() => {
                  setSearch("");
                  setRiskFilter("all");
                }}
              />
            ) : (
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Actor</th>
                      <th>Action</th>
                      <th>Target System</th>
                      <th>Risk Level</th>
                      <th>Execution Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedLogs.map((log, i) => (
                      <tr key={i}>
                        <td className="mono text-faint">{log.time}</td>
                        <td>
                          {log.is_ai ? (
                            <span className="badge ai">{log.actor}</span>
                          ) : (
                            <span className="font-medium">{log.actor}</span>
                          )}
                        </td>
                        <td className="font-medium">{log.action}</td>
                        <td className="text-dim">{log.system}</td>
                        <td>
                          <span
                            className={`badge ${
                              log.risk.toLowerCase() === "high"
                                ? "error"
                                : log.risk.toLowerCase() === "medium"
                                ? "warning"
                                : "active"
                            }`}
                          >
                            {log.risk}
                          </span>
                        </td>
                        <td>
                          <span
                            className={`badge ${
                              log.status.toLowerCase() === "verified" || log.status.toLowerCase() === "success"
                                ? "active"
                                : "error"
                            }`}
                          >
                            {log.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Pagination Controls */}
                <Pagination
                  currentPage={page}
                  totalItems={filteredLogs.length}
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
