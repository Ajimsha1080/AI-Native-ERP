"use client";

import { apiClient } from "../../lib/api-client";

import { useState, useEffect } from "react";

export default function OperationsPage() {
  const [data, setData] = useState<{ activeShipments: number; delayedShipments: number }>({
    activeShipments: 0,
    delayedShipments: 0
  });

  useEffect(() => {
    apiClient.get("/api/v1/dashboard/operations")
      .then(d => {
        if (d) setData(d);
      })
      .catch(() => {
        setData({ activeShipments: 0, delayedShipments: 0 });
      });
  }, []);

  return (
    <main className="main">
      <div className="topbar">
        <div className="breadcrumb">Operations</div>
      </div>
      <div className="content">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div>
            <h1 className="display" style={{ fontSize: '24px' }}>Operations Control</h1>
            <p className="text-dim text-sm" style={{ marginTop: '4px' }}>Manage logistics and operational workflows.</p>
          </div>
          <button className="btn btn-primary" style={{ background: 'var(--ai-core)' }}>Ask Operations Agent</button>
        </div>

        <div className="kpi-grid" style={{ marginBottom: '32px' }}>
          <div className="kpi-card">
            <div className="kpi-label">Active Shipments</div>
            <div className="kpi-val">{data.activeShipments}</div>
            <div className="kpi-delta flat">{data.activeShipments > 0 ? "Tracking Live" : "Awaiting Logistics Stream"}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Delayed Shipments</div>
            <div className="kpi-val">{data.delayedShipments}</div>
            <div className="kpi-delta active">{data.delayedShipments > 0 ? "Attention Needed" : "Queue Clear"}</div>
          </div>
        </div>

        <div className="panel" style={{ padding: '60px 24px', textAlign: 'center', borderRadius: '16px' }}>
          <div style={{ fontSize: '42px', marginBottom: '16px' }}>🚢</div>
          <h3 className="font-semibold text-base mb-1" style={{ color: 'var(--text)' }}>Real-Time Operations Stream Active</h3>
          <p className="text-sm text-dim" style={{ maxWidth: '440px', margin: '0 auto' }}>
            No live shipping or logistics stream connected yet. Connect your 3PL, FedEx, DHL, or SAP Logistics API in /connectors to track live shipments.
          </p>
        </div>
      </div>
    </main>
  );
}
