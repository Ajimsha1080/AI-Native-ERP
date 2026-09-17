"use client";

import { apiClient } from "../../lib/api-client";

import { useState, useEffect } from "react";
import Link from "next/link";

export default function ProcurementPage() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    apiClient.get("/api/v1/dashboard/procurement")
      .then(setData)
      .catch(console.error);
  }, []);

  return (
    <main className="main">
      <div className="topbar">
        <div className="breadcrumb">Procurement</div>
        <div className="search-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          <input type="text" placeholder="Search POs, suppliers..." />
          <span className="cmd-k">⌘K</span>
        </div>
      </div>
      <div className="content">
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div>
            <h1 className="display" style={{ fontSize: '24px' }}>Procurement</h1>
          </div>
          <Link href="/?context=Procurement" className="btn btn-primary" style={{ background: 'var(--ai-core)' }}>Ask Procurement Agent</Link>
        </div>

        {!data ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <div className="skeleton" style={{ height: '70px', borderRadius: '8px' }}></div>
            <div className="skeleton" style={{ height: '120px', borderRadius: '8px' }}></div>
            <div className="skeleton" style={{ height: '400px', borderRadius: '8px' }}></div>
          </div>
        ) : (
          <>
            {data?.insight && (
              <div className="ai-insight" style={{ marginBottom: '24px' }}>
                <div className="ai-icon">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"/></svg>
                </div>
                <div>
                  <h4 className="font-semibold text-sm mb-1" style={{ color: 'var(--ai-core)' }}>{data.insight.title || 'Procurement Stream Active'}</h4>
                  <p className="text-sm text-dim">{data.insight.description || 'Supplier portal connected.'} <a href="#" style={{ color: 'var(--ai-core)', textDecoration: 'underline' }}>Review and Approve</a></p>
                </div>
              </div>
            )}

            <div className="kpi-grid" style={{ marginBottom: '32px' }}>
              {(data?.kpis || []).map((kpi: any, i: number) => (
                <div key={i} className="kpi-card">
                  <div className="kpi-label">{kpi.label}</div>
                  <div className="kpi-val">{kpi.value}</div>
                  <div className={`kpi-delta ${kpi.trend}`}>{kpi.delta}</div>
                </div>
              ))}
            </div>

            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>PO Number</th>
                    <th>Supplier</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Created By</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.orders || []).map((po: any, i: number) => (
                    <tr key={i}>
                      <td className="mono">{po.po}</td>
                      <td className="font-medium">{po.supplier}</td>
                      <td className="mono">{po.amount}</td>
                      <td>
                        <span className={`badge ${po.status.toLowerCase().includes('pending') ? 'warning' : 'active'}`}>
                          {po.status}
                        </span>
                      </td>
                      <td>
                        {po.is_ai ? (
                          <span className="badge ai">{po.author}</span>
                        ) : (
                          po.author
                        )}
                      </td>
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
