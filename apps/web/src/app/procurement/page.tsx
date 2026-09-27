"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";
import { apiClient } from "../../lib/api-client";
import { useAuth } from "../../lib/auth-context";
import { Pagination } from "../../components/Pagination";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { RoleBadge } from "../../components/RoleBadge";

interface PurchaseOrderItem {
  po: string;
  supplier: string;
  amount: string;
  status: string;
  author: string;
  is_ai?: boolean;
}

interface ProcurementDashboardData {
  insight?: { title: string; description: string };
  kpis?: Array<{ label: string; value: string; delta: string; trend: string }>;
  orders?: PurchaseOrderItem[];
}

export default function ProcurementPage() {
  const { user, canPerform } = useAuth();
  const [data, setData] = useState<ProcurementDashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);

  const canManageProcurement = canPerform(["owner", "admin", "manager"]);

  const fetchData = useCallback(() => {
    setIsLoading(true);
    setError(null);
    apiClient
      .get("/api/v1/dashboard/procurement")
      .then((res) => {
        setData(res);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load procurement records");
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Filter purchase orders
  const filteredOrders = useMemo(() => {
    const list = data?.orders || [];
    return list.filter((po) => {
      const matchSearch =
        po.po.toLowerCase().includes(search.toLowerCase()) ||
        po.supplier.toLowerCase().includes(search.toLowerCase());
      const matchStatus =
        statusFilter === "all" || po.status.toLowerCase().includes(statusFilter.toLowerCase());
      return matchSearch && matchStatus;
    });
  }, [data, search, statusFilter]);

  // Paginated purchase orders
  const paginatedOrders = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredOrders.slice(start, start + pageSize);
  }, [filteredOrders, page, pageSize]);

  return (
    <main className="main">
      <div className="topbar">
        <div className="flex items-center gap-3">
          <div className="breadcrumb">Procurement</div>
          <RoleBadge />
        </div>
        <div className="search-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search POs, vendors..."
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
            <h1 className="display" style={{ fontSize: "24px" }}>Procurement & Purchase Orders</h1>
            <p className="text-sm text-dim">Supplier catalog, purchase orders, autonomous RFP dispatch, and approval gates</p>
          </div>
          <div className="flex items-center gap-2">
            {canManageProcurement && (
              <button
                className="btn btn-secondary"
                onClick={() => alert("Create Purchase Order form opened.")}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 5v14M5 12h14" />
                </svg>
                New Purchase Order
              </button>
            )}
            <Link href="/?context=Procurement" className="btn btn-primary" style={{ background: "var(--ai-core)" }}>
              Ask Procurement Agent
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
            title="Failed to load procurement data"
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
                    {data.insight.title || "Procurement Stream Active"}
                  </h4>
                  <p className="text-sm text-dim">
                    {data.insight.description || "Supplier portal connected."}{" "}
                    <Link href="/?context=Procurement" style={{ color: "var(--ai-core)", textDecoration: "underline" }}>
                      Run Vendor RFQ Optimization
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
                {["all", "approved", "pending", "draft"].map((st) => (
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
                {filteredOrders.length} purchase orders
              </span>
            </div>

            {/* Empty State vs Orders Table */}
            {filteredOrders.length === 0 ? (
              <EmptyState
                title="No purchase orders found"
                description={
                  search || statusFilter !== "all"
                    ? "No purchase orders match your filter criteria."
                    : "There are currently no active purchase orders. Issue a new purchase order or approve low-stock items."
                }
                actionLabel={search || statusFilter !== "all" ? "Clear Filters" : "Create Purchase Order"}
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
                      <th>PO Number</th>
                      <th>Supplier / Vendor</th>
                      <th>Order Amount</th>
                      <th>Approval Status</th>
                      <th>Author</th>
                      {canManageProcurement && <th style={{ textAlign: "right" }}>Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedOrders.map((po, i) => (
                      <tr key={i}>
                        <td className="mono" style={{ fontWeight: 600 }}>{po.po}</td>
                        <td className="font-medium">{po.supplier}</td>
                        <td className="mono" style={{ fontWeight: 600 }}>{po.amount}</td>
                        <td>
                          <span
                            className={`badge ${
                              po.status.toLowerCase().includes("pending")
                                ? "warning"
                                : po.status.toLowerCase().includes("approved") || po.status.toLowerCase().includes("active")
                                ? "active"
                                : "error"
                            }`}
                          >
                            {po.status}
                          </span>
                        </td>
                        <td>
                          {po.is_ai ? (
                            <span className="badge ai">{po.author}</span>
                          ) : (
                            <span className="text-dim">{po.author}</span>
                          )}
                        </td>
                        {canManageProcurement && (
                          <td style={{ textAlign: "right" }}>
                            <button
                              className="btn btn-secondary"
                              style={{ padding: "4px 8px", fontSize: "11px" }}
                              onClick={() => alert(`View details for ${po.po}`)}
                            >
                              Details
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
                  totalItems={filteredOrders.length}
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
