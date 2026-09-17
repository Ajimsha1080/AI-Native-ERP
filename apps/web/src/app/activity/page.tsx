"use client";

import { apiClient } from "../../lib/api-client";

import { useState, useEffect } from "react";

export default function ActivityPage() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    apiClient.get("/api/v1/dashboard/activity")
      .then(setData)
      .catch(console.error);
  }, []);

  return (
    <main className="main">
      <div className="topbar">
        <div className="breadcrumb">Agent Activity</div>
        <div className="search-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          <input type="text" placeholder="Search agent logs..." />
          <span className="cmd-k">⌘K</span>
        </div>
      </div>
      <div className="content">
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div>
            <h1 className="display" style={{ fontSize: '24px' }}>Real-time Agent Activity</h1>
            <p className="text-dim text-sm" style={{ marginTop: '4px' }}>Monitor the autonomous actions executed by your AI workforce.</p>
          </div>
          <button className="btn btn-secondary">Filter by Agent</button>
        </div>

        {!data ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '800px' }}>
            <div className="skeleton" style={{ height: '140px', borderRadius: '12px' }}></div>
            <div className="skeleton" style={{ height: '140px', borderRadius: '12px' }}></div>
            <div className="skeleton" style={{ height: '140px', borderRadius: '12px' }}></div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '800px' }}>
            {(data?.activities || []).map((act: any, i: number) => (
              <div key={i} style={{ padding: '20px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '12px', borderLeft: `4px solid var(--${act.type === 'warning' ? 'pending' : (act.type === 'danger' ? 'danger' : 'verified')})` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="badge ai">{act.agent}</span>
                    <span className="text-faint text-xs mono">{act.time}</span>
                  </div>
                </div>
                <h4 className="font-semibold text-base mb-1">{act.title}</h4>
                <p className="text-sm text-dim mb-3">{act.description}</p>
                <button className="btn btn-secondary text-xs">{act.action}</button>
              </div>
            ))}
          </div>
        )}

      </div>
    </main>
  );
}
