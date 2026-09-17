"use client";

import { apiClient } from "../../lib/api-client";

import { useState, useEffect } from "react";

export default function AuditPage() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    apiClient.get("/api/v1/dashboard/audit")
      .then(setData)
      .catch(console.error);
  }, []);

  return (
    <main className="main">
      <div className="topbar">
        <div className="breadcrumb">Audit Logs</div>
        <div className="search-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          <input type="text" placeholder="Search events, Trace IDs..." />
          <span className="cmd-k">⌘K</span>
        </div>
      </div>
      <div className="content">
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div>
            <h1 className="display" style={{ fontSize: '24px' }}>System Audit Trail</h1>
            <p className="text-dim text-sm" style={{ marginTop: '4px' }}>Immutable ledger of all human and AI actions across connected systems.</p>
          </div>
          <button className="btn btn-secondary">Export Logs (CSV)</button>
        </div>

        {!data ? (
          <div className="skeleton" style={{ height: '400px', borderRadius: '8px' }}></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Actor</th>
                  <th>Action</th>
                  <th>Target System</th>
                  <th>Risk Level</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {(data?.logs || []).map((log: any, i: number) => (
                  <tr key={i}>
                    <td className="mono text-faint">{log.time}</td>
                    <td>
                      {log.is_ai ? (
                        <span className="badge ai">{log.actor}</span>
                      ) : (
                        log.actor
                      )}
                    </td>
                    <td className="font-medium">{log.action}</td>
                    <td>{log.system}</td>
                    <td>
                      <span className={`badge ${log.risk === 'High' ? 'error' : (log.risk === 'Medium' ? 'warning' : 'active')}`}>
                        {log.risk}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${log.status === 'Verified' || log.status === 'Success' ? 'active' : 'error'}`}>
                        {log.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

      </div>
    </main>
  );
}
