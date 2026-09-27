"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";
import { apiClient } from "../../lib/api-client";
import { useAuth } from "../../lib/auth-context";
import { Pagination } from "../../components/Pagination";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { RoleBadge } from "../../components/RoleBadge";

interface ProductItem {
  sku: string;
  name: string;
  stock: number;
  velocity: string;
  status: string;
  unit_price?: string;
  category?: string;
}

interface InventoryDashboardData {
  insight?: { title: string; description: string };
  kpis?: Array<{ label: string; value: string; delta: string; trend: string }>;
  products?: ProductItem[];
}

export default function InventoryPage() {
  const { user, canPerform } = useAuth();
  const [data, setData] = useState<InventoryDashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);

  const canManageInventory = canPerform(["owner", "admin", "manager"]);

  const fetchData = useCallback(() => {
    setIsLoading(true);
    setError(null);
    apiClient
      .get("/api/v1/dashboard/inventory")
      .then((res) => {
        setData(res);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load inventory data");
        setIsLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Filter products by search and status
  const filteredProducts = useMemo(() => {
    const list = data?.products || [];
    return list.filter((p) => {
      const matchSearch =
        p.name.toLowerCase().includes(search.toLowerCase()) ||
        p.sku.toLowerCase().includes(search.toLowerCase());
      const matchStatus =
        statusFilter === "all" || p.status.toLowerCase().includes(statusFilter.toLowerCase());
      return matchSearch && matchStatus;
    });
  }, [data, search, statusFilter]);

  // Paginated items
  const paginatedProducts = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredProducts.slice(start, start + pageSize);
  }, [filteredProducts, page, pageSize]);

  return (
    <main className="main">
      {/* Topbar with search & user role */}
      <div className="topbar">
        <div className="flex items-center gap-3">
          <div className="breadcrumb">Inventory</div>
          <RoleBadge />
        </div>
        <div className="search-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search products, SKUs..."
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
        {/* Header with Role-Aware Actions */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
          <div>
            <h1 className="display" style={{ fontSize: "24px" }}>Inventory Overview</h1>
            <p className="text-sm text-dim">Real-time stock valuation, inventory health, and reorder levels</p>
          </div>
          <div className="flex items-center gap-2">
            {canManageInventory && (
              <Link
                href="/inventory"
                onClick={(e) => {
                  e.preventDefault();
                  alert("Stock reorder recommendations queued to AI Agent.");
                }}
                className="btn btn-secondary"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 5v14M5 12h14" />
                </svg>
                Restock Orders
              </Link>
            )}
            <Link href="/?context=Inventory" className="btn btn-primary" style={{ background: "var(--ai-core)" }}>
              Ask Inventory Agent
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
            title="Unable to load inventory records"
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
                    {data.insight.title || "Inventory Stream Active"}
                  </h4>
                  <p className="text-sm text-dim">
                    {data.insight.description || "SKU inventory monitoring active."}{" "}
                    <Link href="/?context=Inventory" style={{ color: "var(--ai-core)", textDecoration: "underline" }}>
                      Generate Purchase Recommendations
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
                {["all", "healthy", "risk", "critical"].map((st) => (
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
                {filteredProducts.length} items found
              </span>
            </div>

            {/* Empty State vs Products Table */}
            {filteredProducts.length === 0 ? (
              <EmptyState
                title="No inventory products found"
                description={
                  search || statusFilter !== "all"
                    ? "No products matched your search or status filter. Try clearing filters."
                    : "Your inventory catalog is currently empty. Add your first product or sync with ERP connectors."
                }
                actionLabel={search || statusFilter !== "all" ? "Clear Filters" : "Sync Inventory"}
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
                      <th>SKU</th>
                      <th>Product Name</th>
                      <th>Stock Units</th>
                      <th>Sales Velocity</th>
                      <th>Status</th>
                      {canManageInventory && <th style={{ textAlign: "right" }}>Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedProducts.map((p, i) => (
                      <tr key={i}>
                        <td className="mono" style={{ fontWeight: 600 }}>{p.sku}</td>
                        <td className="font-medium">{p.name}</td>
                        <td>{p.stock}</td>
                        <td>{p.velocity}</td>
                        <td>
                          <span
                            className={`badge ${
                              p.status.toLowerCase().includes("risk") || p.status.toLowerCase().includes("critical")
                                ? "error"
                                : p.status.toLowerCase() === "healthy"
                                ? "active"
                                : "warning"
                            }`}
                          >
                            {p.status}
                          </span>
                        </td>
                        {canManageInventory && (
                          <td style={{ textAlign: "right" }}>
                            <button
                              className="btn btn-secondary"
                              style={{ padding: "4px 8px", fontSize: "11px" }}
                              onClick={() => alert(`Adjust stock for ${p.sku}`)}
                            >
                              Adjust
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
                  totalItems={filteredProducts.length}
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
