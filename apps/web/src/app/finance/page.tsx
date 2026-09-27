"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";
import { apiClient } from "../../lib/api-client";
import { useAuth } from "../../lib/auth-context";
import { Pagination } from "../../components/Pagination";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { RoleBadge } from "../../components/RoleBadge";

interface InvoiceItem {
  id: string;
  customer: string;
  amount: string;
  status: string;
  date: string;
  due_date?: string;
}

interface FinanceDashboardData {
  insight?: { title: string; description: string };
  kpis?: Array<{ label: string; value: string; delta: string; trend: string }>;
  invoices?: InvoiceItem[];
}

export default function FinancePage() {
  const { user, canPerform } = useAuth();
  const [data, setData] = useState<FinanceDashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);

  const canManageFinance = canPerform(["owner", "admin", "manager"]);

  const fetchData = useCallback(() => {
    setIsLoading(true);
    setError(null);
    apiClient
      .get("/api/v1/dashboard/finance")
      .then((res) => {
        setData(res);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load financial records");
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Filter invoices
  const filteredInvoices = useMemo(() => {
    const list = data?.invoices || [];
    return list.filter((inv) => {
      const matchSearch =
        inv.id.toLowerCase().includes(search.toLowerCase()) ||
        inv.customer.toLowerCase().includes(search.toLowerCase());
      const matchStatus =
        statusFilter === "all" || inv.status.toLowerCase().includes(statusFilter.toLowerCase());
      return matchSearch && matchStatus;
    });
  }, [data, search, statusFilter]);

  // Paginated invoices
  const paginatedInvoices = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredInvoices.slice(start, start + pageSize);
  }, [filteredInvoices, page, pageSize]);

  return (
    <main className="main">
      <div className="topbar">
        <div className="flex items-center gap-3">
          <div className="breadcrumb">Finance</div>
          <RoleBadge />
        </div>
        <div className="search-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search invoices, clients..."
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
            <h1 className="display" style={{ fontSize: "24px" }}>Financial Overview</h1>
            <p className="text-sm text-dim">Real-time ledger entries, cash flow, accounts receivable, and automated reconciliation</p>
          </div>
          <div className="flex items-center gap-2">
            {canManageFinance && (
              <button
                className="btn btn-secondary"
                onClick={() => alert("Invoice generation dialog opened.")}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 5v14M5 12h14" />
                </svg>
                New Invoice
              </button>
            )}
            <Link href="/?context=Finance" className="btn btn-primary" style={{ background: "var(--ai-core)" }}>
              Ask Finance Agent
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
            title="Failed to retrieve financial ledger"
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
                    {data.insight.title || "Financial Insight Engine"}
                  </h4>
                  <p className="text-sm text-dim">
                    {data.insight.description || "Real-time financial ledgers synced."}{" "}
                    <Link href="/?context=Finance" style={{ color: "var(--ai-core)", textDecoration: "underline" }}>
                      Run Cash Flow Forecast
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
                {["all", "paid", "pending", "overdue"].map((st) => (
                  <button
                    key={st}
                    onClick={() => {
                      setStatusFilter(st);
                      setPage(1);
                    }}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "6px",
                      fontSize: "12px",
                      fontWeight: 500,
                      border: "1px solid " + (statusFilter === st ? "var(--accent)" : "var(--border)"),
                      background: statusFilter === st ? "var(--accent)" : "var(--surface)",
                      color: statusFilter === st ? "#ffffff" : "var(--text)",
                      cursor: "pointer",
                      textTransform: "capitalize",
                    }}
                  >
                    {st}
                  </button>
                ))}
              </div>
              <span className="text-xs text-dim">
                {filteredInvoices.length} invoices found
              </span>
            </div>

            {/* Empty State vs Invoices Table */}
            {filteredInvoices.length === 0 ? (
              <EmptyState
                title="No invoices or transactions found"
                description={
                  search || statusFilter !== "all"
                    ? "No invoices match your current filter criteria."
                    : "Your financial ledger currently has no invoices. Issue an invoice or connect QuickBooks."
                }
                actionLabel={search || statusFilter !== "all" ? "Reset Filters" : "Create Invoice"}
                onAction={() => {
                  setSearch("");
                  setStatusFilter("all");
                }}
                canPerformAction={true}
              />
            ) : (
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Invoice ID</th>
                      <th>Customer / Account</th>
                      <th>Amount</th>
                      <th>Payment Status</th>
                      <th>Issued Date</th>
                      {canManageFinance && <th style={{ textAlign: "right" }}>Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedInvoices.map((inv, i) => (
                      <tr key={i}>
                        <td className="mono" style={{ fontWeight: 600 }}>{inv.id}</td>
                        <td className="font-medium">{inv.customer}</td>
                        <td className="mono" style={{ fontWeight: 600 }}>{inv.amount}</td>
                        <td>
                          <span
                            className={`badge ${
                              inv.status.toLowerCase() === "paid"
                                ? "active"
                                : inv.status.toLowerCase() === "pending"
                                ? "warning"
                                : "error"
                            }`}
                          >
                            {inv.status}
                          </span>
                        </td>
                        <td className="text-dim">{inv.date}</td>
                        {canManageFinance && (
                          <td style={{ textAlign: "right" }}>
                            <button
                              className="btn btn-secondary"
                              style={{ padding: "4px 8px", fontSize: "11px" }}
                              onClick={() => alert(`Review invoice ${inv.id}`)}
                            >
                              Review
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
                  totalItems={filteredInvoices.length}
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
