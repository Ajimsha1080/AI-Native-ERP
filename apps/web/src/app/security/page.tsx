"use client";

import { apiClient } from "../../lib/api-client";

import { useState, useEffect } from "react";

export default function SecurityPage() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    apiClient.get("/api/v1/dashboard/security")
      .then(setData)
      .catch(console.error);
  }, []);

  return (
    <main className="main">
      <div className="topbar">
        <div className="breadcrumb">Security Center</div>
        <div className="search-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          <input type="text" placeholder="Search roles, users..." />
          <span className="cmd-k">⌘K</span>
        </div>
      </div>
      <div className="content">
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div>
            <h1 className="display" style={{ fontSize: '24px' }}>Security & Permissions</h1>
            <p className="text-dim text-sm" style={{ marginTop: '4px' }}>Manage human and AI agent access controls across the organization.</p>
          </div>
          <button className="btn btn-primary">Create Role</button>
        </div>

        {!data ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div className="skeleton" style={{ height: '120px', borderRadius: '8px' }}></div>
            <div className="skeleton" style={{ height: '400px', borderRadius: '8px' }}></div>
          </div>
        ) : (
          <>
            <div className="kpi-grid" style={{ marginBottom: '32px' }}>
              {(data?.kpis || []).map((kpi: any, i: number) => (
                <div key={i} className="kpi-card">
                  <div className="kpi-label">{kpi.label}</div>
                  <div className="kpi-val">{kpi.value}</div>
                  <div className={`kpi-delta ${kpi.trend}`}>{kpi.delta}</div>
                </div>
              ))}
            </div>

            <h3 className="font-semibold text-lg mb-4">Agent Permission Matrix</h3>
            <div className="table-wrapper" style={{ marginBottom: '40px' }}>
              <table>
                <thead>
                  <tr>
                    <th>Agent</th>
                    <th>Read Data</th>
                    <th>Create Records</th>
                    <th>Update Records</th>
                    <th>Delete Records</th>
                    <th>Auto-Approve Limit</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.permissions || []).map((perm: any, i: number) => (
                    <tr key={i}>
                      <td className="font-medium"><span className="badge ai">{perm.agent}</span></td>
                      <td><span className={`badge ${perm.read === 'Allowed' ? 'active' : 'error'}`}>{perm.read}</span></td>
                      <td><span className={`badge ${perm.create === 'Allowed' ? 'active' : 'error'}`}>{perm.create}</span></td>
                      <td><span className={`badge ${perm.update === 'Allowed' ? 'active' : 'error'}`}>{perm.update}</span></td>
                      <td><span className={`badge ${perm.delete === 'Allowed' ? 'active' : 'error'}`}>{perm.delete}</span></td>
                      <td className="mono">{perm.limit}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

      </div>
    </main>
  );
}
