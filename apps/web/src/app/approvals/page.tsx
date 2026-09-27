"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { apiClient } from "../../lib/api-client";
import { useAuth } from "../../lib/auth-context";
import { Pagination } from "../../components/Pagination";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { RoleBadge } from "../../components/RoleBadge";

interface ApprovalItem {
  id: string;
  title: string;
  subtitle: string;
  amount: string;
  agent: string;
  system: string;
  time: string;
  status: "pending" | "approved" | "rejected";
  urgent?: boolean;
  details?: string[];
}

export default function ApprovalsPage() {
  const { user, canPerform } = useAuth();
  const [activeTab, setActiveTab] = useState<"pending" | "approved" | "rejected">("pending");
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedItem, setSelectedItem] = useState<ApprovalItem | null>(null);
  const [editAmount, setEditAmount] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);

  const canAuthorize = canPerform(["owner", "admin", "manager"]);

  const fetchApprovals = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.get("/api/v1/actions/approvals-queue");
      setItems(Array.isArray(data) ? data : []);
    } catch (err: any) {
      setError(err.message || "Failed to fetch approvals queue");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApprovals();
  }, [fetchApprovals]);

  const handleApprove = async (id: string) => {
    if (!canAuthorize) return;
    setItems((prev) => prev.map((item) => (item.id === id ? { ...item, status: "approved" } : item)));
    if (selectedItem?.id === id) setSelectedItem(null);

    try {
      await apiClient.post(`/api/v1/actions/${id}/approve`, {
        action_on_action: "approve",
        comments: "Approved via Approvals Gate",
      });
    } catch (err) {
      console.error("Approval error:", err);
    }
  };

  const handleReject = async (id: string) => {
    if (!canAuthorize) return;
    setItems((prev) => prev.map((item) => (item.id === id ? { ...item, status: "rejected" } : item)));
    if (selectedItem?.id === id) setSelectedItem(null);

    try {
      await apiClient.post(`/api/v1/actions/${id}/reject`, {
        rejection_reason: "Declined by Executive via Approvals Gate",
      });
    } catch (err) {
      console.error("Rejection error:", err);
    }
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedItem || !canAuthorize) return;

    const newAmount = editAmount || selectedItem.amount;
    setItems((prev) =>
      prev.map((item) =>
        item.id === selectedItem.id
          ? {
              ...item,
              amount: newAmount,
              details: [...(item.details || []), `Modified by Executive: ${editNotes || "Adjusted parameter"}`],
            }
          : item
      )
    );

    try {
      await apiClient.put(`/api/v1/actions/${selectedItem.id}`, {
        amount: newAmount,
        description: editNotes ? `${selectedItem.subtitle} (Note: ${editNotes})` : selectedItem.subtitle,
      });
    } catch (err) {
      console.error("Edit error:", err);
    }

    setSelectedItem(null);
  };

  const filteredItems = useMemo(() => {
    return items.filter((item) => item.status === activeTab);
  }, [items, activeTab]);

  const paginatedItems = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredItems.slice(start, start + pageSize);
  }, [filteredItems, page, pageSize]);

  const pendingCount = items.filter((i) => i.status === "pending").length;
  const approvedCount = items.filter((i) => i.status === "approved").length;
  const rejectedCount = items.filter((i) => i.status === "rejected").length;

  return (
    <main className="main">
      <div className="topbar">
        <div className="flex items-center gap-3">
          <span className="breadcrumb">Approvals</span>
          <RoleBadge />
        </div>
      </div>

      <div className="content">
        {/* KPI Metrics */}
        <div className="kpi-grid" style={{ marginBottom: "24px" }}>
          <div className="kpi-card">
            <div className="kpi-label">Pending Approval Queue</div>
            <div className="kpi-val">{pendingCount} Items</div>
            <div className={`kpi-delta ${pendingCount > 0 ? "down" : "up"}`}>
              {pendingCount > 0 ? "Requires Action" : "Queue Clear"}
            </div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">AI Safety Threshold</div>
            <div className="kpi-val">$1,000.00</div>
            <div className="kpi-delta up">Human-in-the-Loop Active</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Authorization Gate</div>
            <div className="kpi-val">{canAuthorize ? "Authorized" : "Read-Only"}</div>
            <div className="kpi-delta up">Multi-Tenant Isolation</div>
          </div>
        </div>

        {/* Tab Filters */}
        <div
          style={{
            display: "flex",
            gap: "8px",
            marginBottom: "24px",
            borderBottom: "1px solid var(--border-soft)",
            paddingBottom: "12px",
          }}
        >
          <button
            className={`btn ${activeTab === "pending" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => {
              setActiveTab("pending");
              setPage(1);
            }}
          >
            Pending ({pendingCount})
          </button>
          <button
            className={`btn ${activeTab === "approved" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => {
              setActiveTab("approved");
              setPage(1);
            }}
          >
            Approved ({approvedCount})
          </button>
          <button
            className={`btn ${activeTab === "rejected" ? "btn-primary" : "btn-secondary"}`}
            onClick={() => {
              setActiveTab("rejected");
              setPage(1);
            }}
          >
            Rejected ({rejectedCount})
          </button>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div className="skeleton" style={{ height: "140px", borderRadius: "12px" }} />
            <div className="skeleton" style={{ height: "140px", borderRadius: "12px" }} />
          </div>
        )}

        {/* Error State */}
        {!isLoading && error && (
          <ErrorState
            title="Failed to load approvals queue"
            message={error}
            onRetry={fetchApprovals}
          />
        )}

        {/* Loaded List / Empty State */}
        {!isLoading && !error && (
          <>
            {filteredItems.length === 0 ? (
              <EmptyState
                title={`No ${activeTab.toUpperCase()} approvals in queue`}
                description={
                  activeTab === "pending"
                    ? "Your approval queue is clear. When an automated agent action exceeds the safety threshold ($1,000), it will appear here for authorization."
                    : `No items are currently marked as ${activeTab}.`
                }
                actionLabel={activeTab !== "pending" ? "View Pending Queue" : undefined}
                onAction={() => setActiveTab("pending")}
              />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                {paginatedItems.map((item) => (
                  <div
                    key={item.id}
                    className="kpi-card"
                    style={{
                      borderLeft: `4px solid ${item.urgent ? "var(--danger)" : "var(--ai-core)"}`,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                      <div>
                        <h3 style={{ fontSize: "16px", fontWeight: 600, color: "var(--text)" }}>{item.title}</h3>
                        <p style={{ fontSize: "13px", color: "var(--text-dim)", marginTop: "2px" }}>{item.subtitle}</p>
                      </div>
                      <div className="mono" style={{ fontSize: "18px", fontWeight: 700, color: "var(--text)" }}>
                        {item.amount}
                      </div>
                    </div>

                    <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "16px", fontSize: "12px" }}>
                      <span className="badge ai">{item.agent}</span>
                      <span className="badge" style={{ background: "var(--surface-2)", color: "var(--text-dim)" }}>
                        {item.system}
                      </span>
                      <span style={{ marginLeft: "auto", color: "var(--text-faint)", fontSize: "11px" }}>{item.time}</span>
                    </div>

                    {item.status === "pending" && (
                      <div style={{ display: "flex", gap: "8px", marginTop: "12px", borderTop: "1px solid var(--border-soft)", paddingTop: "12px" }}>
                        {canAuthorize ? (
                          <>
                            <button
                              className="btn btn-secondary"
                              style={{ color: "var(--danger)", fontSize: "12px" }}
                              onClick={() => handleReject(item.id)}
                            >
                              ✕ Reject
                            </button>
                            <button
                              className="btn btn-secondary"
                              style={{ fontSize: "12px" }}
                              onClick={() => {
                                setSelectedItem(item);
                                setEditAmount(item.amount);
                              }}
                            >
                              ✎ Modify
                            </button>
                            <button
                              className="btn btn-primary"
                              style={{ background: "var(--verified)", color: "#ffffff", marginLeft: "auto", fontSize: "12px" }}
                              onClick={() => handleApprove(item.id)}
                            >
                              ✓ Approve & Execute
                            </button>
                          </>
                        ) : (
                          <span className="text-xs text-dim" style={{ fontStyle: "italic" }}>
                            Executive or Manager permissions required to approve/reject actions.
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                ))}

                <Pagination
                  currentPage={page}
                  totalItems={filteredItems.length}
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

      {/* Modify Modal */}
      {selectedItem && canAuthorize && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "12px",
              padding: "28px",
              width: "100%",
              maxWidth: "480px",
            }}
          >
            <h2 className="font-semibold text-lg" style={{ marginBottom: "16px" }}>Modify Action Parameters</h2>
            <form onSubmit={handleSaveEdit}>
              <div style={{ marginBottom: "16px" }}>
                <label className="text-xs font-semibold uppercase text-faint" style={{ display: "block", marginBottom: "6px" }}>
                  Adjusted Amount
                </label>
                <input
                  type="text"
                  className="ai-cmd-input"
                  style={{ width: "100%", padding: "10px 14px", fontSize: "14px" }}
                  value={editAmount}
                  onChange={(e) => setEditAmount(e.target.value)}
                />
              </div>
              <div style={{ marginBottom: "20px" }}>
                <label className="text-xs font-semibold uppercase text-faint" style={{ display: "block", marginBottom: "6px" }}>
                  Executive Notes
                </label>
                <textarea
                  className="ai-cmd-input"
                  style={{ width: "100%", padding: "10px 14px", height: "80px", fontSize: "13px" }}
                  placeholder="Add note for audit log..."
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                />
              </div>
              <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
                <button type="button" className="btn btn-secondary" onClick={() => setSelectedItem(null)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Adjustments
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
