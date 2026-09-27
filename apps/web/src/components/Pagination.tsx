"use client";

import React from "react";

export interface PaginationProps {
  currentPage: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  pageSizeOptions?: number[];
}

export function Pagination({
  currentPage,
  totalItems,
  pageSize,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [5, 10, 25, 50],
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const startItem = totalItems === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(totalItems, currentPage * pageSize);

  if (totalItems <= 0) return null;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "16px 20px",
        borderTop: "1px solid var(--border-soft)",
        background: "var(--surface)",
        fontSize: "13px",
      }}
    >
      <div style={{ color: "var(--text-dim)" }}>
        Showing <span style={{ fontWeight: 600, color: "var(--text)" }}>{startItem}</span> to{" "}
        <span style={{ fontWeight: 600, color: "var(--text)" }}>{endItem}</span> of{" "}
        <span style={{ fontWeight: 600, color: "var(--text)" }}>{totalItems}</span> results
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        {onPageSizeChange && (
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <span style={{ color: "var(--text-faint)", fontSize: "12px" }}>Per page:</span>
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--border)",
                borderRadius: "4px",
                padding: "4px 8px",
                fontSize: "12px",
                color: "var(--text)",
                cursor: "pointer",
                outline: "none",
              }}
            >
              {pageSizeOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        )}

        <div style={{ display: "flex", gap: "6px" }}>
          <button
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage <= 1}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: "1px solid var(--border)",
              background: currentPage <= 1 ? "var(--surface-2)" : "var(--surface)",
              color: currentPage <= 1 ? "var(--text-faint)" : "var(--text)",
              cursor: currentPage <= 1 ? "not-allowed" : "pointer",
              fontSize: "12px",
              fontWeight: 500,
            }}
          >
            Previous
          </button>

          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter((p) => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 1)
            .map((p, idx, arr) => {
              const prev = arr[idx - 1];
              return (
                <React.Fragment key={p}>
                  {prev && p - prev > 1 && (
                    <span style={{ padding: "6px 4px", color: "var(--text-faint)" }}>...</span>
                  )}
                  <button
                    onClick={() => onPageChange(p)}
                    style={{
                      padding: "6px 12px",
                      borderRadius: "6px",
                      border: "1px solid",
                      borderColor: p === currentPage ? "var(--ai-core)" : "var(--border)",
                      background: p === currentPage ? "var(--ai-core)" : "var(--surface)",
                      color: p === currentPage ? "#fff" : "var(--text)",
                      cursor: "pointer",
                      fontSize: "12px",
                      fontWeight: p === currentPage ? 600 : 400,
                    }}
                  >
                    {p}
                  </button>
                </React.Fragment>
              );
            })}

          <button
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage >= totalPages}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: "1px solid var(--border)",
              background: currentPage >= totalPages ? "var(--surface-2)" : "var(--surface)",
              color: currentPage >= totalPages ? "var(--text-faint)" : "var(--text)",
              cursor: currentPage >= totalPages ? "not-allowed" : "pointer",
              fontSize: "12px",
              fontWeight: 500,
            }}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
export default Pagination;
