"use client";

import React from "react";
import { useAuth } from "../lib/auth-context";

export function RoleBadge({ role: propRole, customRole }: { role?: string; customRole?: string }) {
  const { user } = useAuth();
  const role = propRole || customRole || user?.role || "viewer";

  const getRoleStyle = (r: string) => {
    switch (r.toLowerCase()) {
      case "owner":
      case "admin":
        return { bg: "var(--accent-soft)", text: "var(--accent)", label: r.toUpperCase() };
      case "manager":
        return { bg: "var(--executing-soft)", text: "var(--executing)", label: "MANAGER" };
      case "member":
        return { bg: "var(--verified-soft)", text: "var(--verified)", label: "MEMBER" };
      case "viewer":
      default:
        return { bg: "var(--surface-2)", text: "var(--text-faint)", label: "READ-ONLY" };
    }
  };

  const style = getRoleStyle(role);

  return (
    <span
      className="badge"
      style={{
        background: style.bg,
        color: style.text,
        border: "1px solid var(--border)",
        fontSize: "10px",
        letterSpacing: "0.5px",
        padding: "2px 8px",
      }}
      title={`Current access level: ${role}`}
    >
      {style.label}
    </span>
  );
}
export default RoleBadge;
