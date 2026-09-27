"use client";

import { useState, useEffect, useCallback } from "react";
import { apiClient } from "../../lib/api-client";
import { useAuth } from "../../lib/auth-context";
import { ErrorState } from "../../components/ErrorState";
import { RoleBadge } from "../../components/RoleBadge";

export default function AnalyticsPage() {
  const { user, canPerform } = useAuth();
  const isOperator = canPerform(["owner", "admin", "manager"]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState("30d");

  const [metrics, setMetrics] = useState({
    tokensUsed: "142.5k",
    hoursSaved: "86.4",
    actionsExecuted: "1,240",
    interventions: "12"
  });

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // In production, fetch telemetry metrics
      setMetrics({
        tokensUsed: timeRange === "7d" ? "38.2k" : timeRange === "90d" ? "420.8k" : "142.5k",
        hoursSaved: timeRange === "7d" ? "21.5" : timeRange === "90d" ? "265.0" : "86.4",
        actionsExecuted: timeRange === "7d" ? "310" : timeRange === "90d" ? "3,890" : "1,240",
        interventions: timeRange === "7d" ? "3" : timeRange === "90d" ? "34" : "12"
      });
    } catch (err: any) {
      setError(err?.message || "Failed to load analytics metrics");
    } finally {
      setLoading(false);
    }
  }, [timeRange]);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  const handleExport = () => {
    if (!isOperator) {
      alert("Unauthorized: Viewer role cannot export executive analytics reports.");
      return;
    }
    const csvContent = "Metric,Value\n" +
      `Total Tokens Used,${metrics.tokensUsed}\n` +
      `Hours Saved,${metrics.hoursSaved}\n` +
      `Actions Executed,${metrics.actionsExecuted}\n` +
      `Human Interventions,${metrics.interventions}\n`;
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `erp_analytics_${timeRange}_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <main className="main">
      <div className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="crumb">Analytics</span>
          <span style={{ color: 'var(--text-faint)' }}>/</span>
          <span className="crumb-sub">Platform metrics, token consumption &amp; AI ROI</span>
          <RoleBadge role={user?.role} />
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '12px' }}>
          <select 
            value={timeRange} 
            onChange={(e) => setTimeRange(e.target.value)}
            className="ai-cmd-input"
            style={{ padding: '6px 12px', fontSize: '13px', borderRadius: '6px', background: 'var(--surface-2)', border: '1px solid var(--border)' }}
          >
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
            <option value="90d">Last 90 Days</option>
          </select>
          {isOperator && (
            <button onClick={handleExport} className="panel-action">
              ⬇ Export Report
            </button>
          )}
        </div>
      </div>

      <div className="content" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {error && <ErrorState message={error} onRetry={loadAnalytics} />}

        {loading ? (
          <div className="kpi-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '24px' }}>
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="skeleton" style={{ height: '110px', borderRadius: '12px' }}></div>
            ))}
          </div>
        ) : (
          <div className="kpi-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '24px' }}>
            {[
              { label: 'Total Tokens Used', value: metrics.tokensUsed, delta: 'LangGraph LLM Context', color: 'var(--accent)' },
              { label: 'Hours Saved', value: `${metrics.hoursSaved} hrs`, delta: 'Automated Operations', color: 'var(--verified)' },
              { label: 'Actions Executed', value: metrics.actionsExecuted, delta: 'Tool Invocations', color: 'var(--executing)' },
              { label: 'Human Interventions', value: metrics.interventions, delta: 'HITL Gate Validations', color: 'var(--pending)' }
            ].map(kpi => (
              <div key={kpi.label} className="panel" style={{ padding: '24px', borderRadius: '12px' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '8px' }}>{kpi.label}</div>
                <div style={{ fontSize: '28px', fontFamily: "'Space Grotesk', sans-serif", fontWeight: 600, marginBottom: '8px' }}>{kpi.value}</div>
                <div style={{ fontSize: '11px', color: kpi.color }}>{kpi.delta}</div>
              </div>
            ))}
          </div>
        )}

        <div className="panel" style={{ flex: 1, minHeight: '380px', display: 'flex', flexDirection: 'column', borderRadius: '12px' }}>
          <div className="panel-head" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 24px', borderBottom: '1px solid var(--border-soft)' }}>
            <h2 className="panel-title" style={{ margin: 0, fontSize: '16px' }}>Token Usage &amp; API Load Over Time</h2>
            <span className="badge active" style={{ fontSize: '11px' }}>Sub-second Telemetry</span>
          </div>
          <div style={{ flex: 1, padding: '24px', display: 'flex', alignItems: 'flex-end', position: 'relative' }}>
            <svg viewBox="0 0 1000 300" width="100%" height="100%" preserveAspectRatio="none" style={{ overflow: 'visible' }}>
              <defs>
                <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
                </linearGradient>
              </defs>
              {/* Grid Lines */}
              {[0, 75, 150, 225, 300].map(y => (
                <line key={y} x1="0" y1={y} x2="1000" y2={y} stroke="var(--border-soft)" strokeWidth="1" />
              ))}
              <path d="M0,250 L100,220 L200,240 L300,150 L400,180 L500,90 L600,120 L700,50 L800,80 L900,20 L1000,40 L1000,300 L0,300 Z" fill="url(#chartGradient)" />
              <path d="M0,250 L100,220 L200,240 L300,150 L400,180 L500,90 L600,120 L700,50 L800,80 L900,20 L1000,40" fill="none" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>
      </div>
    </main>
  );
}
