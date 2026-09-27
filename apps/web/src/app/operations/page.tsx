"use client";

import { apiClient } from "../../lib/api-client";
import { useAuth } from "../../lib/auth-context";
import { Pagination } from "../../components/Pagination";
import { EmptyState } from "../../components/EmptyState";
import { ErrorState } from "../../components/ErrorState";
import { RoleBadge } from "../../components/RoleBadge";
import { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";

interface Shipment {
  id: string;
  trackingNumber: string;
  carrier: string;
  destination: string;
  status: "in_transit" | "delivered" | "delayed" | "customs_hold";
  eta: string;
  itemsCount: number;
}

export default function OperationsPage() {
  const { user, canPerform } = useAuth();
  const isOperator = canPerform(["owner", "admin", "manager"]);

  const [kpis, setKpis] = useState<{ activeShipments: number; delayedShipments: number; onTimeDeliveryRate: string; avgTransitDays: number }>({
    activeShipments: 0,
    delayedShipments: 0,
    onTimeDeliveryRate: "98.5%",
    avgTransitDays: 3.2
  });

  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);

  const loadOperationsData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await apiClient.get("/api/v1/dashboard/operations");
      if (d) {
        setKpis({
          activeShipments: d.activeShipments ?? 4,
          delayedShipments: d.delayedShipments ?? 1,
          onTimeDeliveryRate: "98.5%",
          avgTransitDays: 3.2
        });
      }
      // Demo shipments
      setShipments([
        { id: "SHP-9041", trackingNumber: "1Z9999999999999991", carrier: "UPS Freight", destination: "Chicago Central Hub", status: "in_transit", eta: "Tomorrow 2:00 PM", itemsCount: 450 },
        { id: "SHP-9042", trackingNumber: "FDX-8842109283", carrier: "FedEx Express", destination: "Dallas Fulfillment Center", status: "delayed", eta: "Sep 30, 2026", itemsCount: 120 },
        { id: "SHP-9043", trackingNumber: "DHL-440291884", carrier: "DHL Global", destination: "Rotterdam Port Terminal", status: "in_transit", eta: "Oct 02, 2026", itemsCount: 1800 },
        { id: "SHP-9044", trackingNumber: "MAERSK-990123", carrier: "Maersk Line", destination: "Singapore Logistics Bay", status: "delivered", eta: "Delivered Today", itemsCount: 3200 },
        { id: "SHP-9045", trackingNumber: "1Z9999999999999995", carrier: "UPS Ground", destination: "New York Metro WMS", status: "in_transit", eta: "Oct 01, 2026", itemsCount: 80 }
      ]);
    } catch (err: any) {
      setError(err?.message || "Failed to load operations stream");
      setShipments([
        { id: "SHP-9041", trackingNumber: "1Z9999999999999991", carrier: "UPS Freight", destination: "Chicago Central Hub", status: "in_transit", eta: "Tomorrow 2:00 PM", itemsCount: 450 },
        { id: "SHP-9042", trackingNumber: "FDX-8842109283", carrier: "FedEx Express", destination: "Dallas Fulfillment Center", status: "delayed", eta: "Sep 30, 2026", itemsCount: 120 },
        { id: "SHP-9043", trackingNumber: "DHL-440291884", carrier: "DHL Global", destination: "Rotterdam Port Terminal", status: "in_transit", eta: "Oct 02, 2026", itemsCount: 1800 },
        { id: "SHP-9044", trackingNumber: "MAERSK-990123", carrier: "Maersk Line", destination: "Singapore Logistics Bay", status: "delivered", eta: "Delivered Today", itemsCount: 3200 }
      ]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOperationsData();
  }, [loadOperationsData]);

  const filteredShipments = useMemo(() => {
    return shipments.filter(s => {
      const matchesSearch = s.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            s.carrier.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            s.destination.toLowerCase().includes(searchQuery.toLowerCase()) ||
                            s.trackingNumber.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesStatus = statusFilter === "all" ? true : s.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [shipments, searchQuery, statusFilter]);

  const totalFiltered = filteredShipments.length;
  const paginatedShipments = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredShipments.slice(start, start + pageSize);
  }, [filteredShipments, currentPage, pageSize]);

  return (
    <main className="main">
      <div className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="crumb">Operations</span>
          <span style={{ color: 'var(--text-faint)' }}>/</span>
          <span className="crumb-sub">Logistics, Fulfillment & Supply Chain Control</span>
          <RoleBadge role={user?.role} />
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
          <Link href="/?context=Operations" className="btn btn-primary" style={{ background: 'var(--ai-core)' }}>
            Ask Operations Agent
          </Link>
        </div>
      </div>

      <div className="content" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        
        {error && <ErrorState message={error} onRetry={loadOperationsData} />}

        {/* KPI Grid */}
        <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          <div className="kpi-card">
            <div className="kpi-label">Active Shipments</div>
            <div className="kpi-val">{kpis.activeShipments}</div>
            <div className="kpi-delta flat">{kpis.activeShipments > 0 ? "Tracking Live" : "Idle"}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Delayed Shipments</div>
            <div className="kpi-val" style={{ color: kpis.delayedShipments > 0 ? 'var(--danger)' : 'var(--verified)' }}>{kpis.delayedShipments}</div>
            <div className={`kpi-delta ${kpis.delayedShipments > 0 ? 'active' : 'flat'}`}>{kpis.delayedShipments > 0 ? "Attention Required" : "Queue Clear"}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">On-Time Delivery Rate</div>
            <div className="kpi-val" style={{ color: 'var(--verified)' }}>{kpis.onTimeDeliveryRate}</div>
            <div className="kpi-delta active">Exceeds 95% SLA Target</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Avg Transit Duration</div>
            <div className="kpi-val">{kpis.avgTransitDays} Days</div>
            <div className="kpi-delta flat">Standard Freight</div>
          </div>
        </div>

        {/* Toolbar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-soft)', paddingBottom: '12px', gap: '16px' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            {["all", "in_transit", "delayed", "delivered"].map(st => (
              <button
                key={st}
                className={`btn ${statusFilter === st ? 'btn-primary' : 'btn-secondary'} text-xs`}
                onClick={() => { setStatusFilter(st); setCurrentPage(1); }}
                style={{ background: statusFilter === st ? 'var(--ai-core)' : undefined }}
              >
                {st === "all" ? "All Shipments" : st.replace("_", " ").toUpperCase()} ({st === "all" ? shipments.length : shipments.filter(s => s.status === st).length})
              </button>
            ))}
          </div>

          <div style={{ position: 'relative', width: '280px' }}>
            <input 
              type="text"
              className="ai-cmd-input"
              style={{ width: '100%', padding: '8px 12px 8px 32px', fontSize: '13px', borderRadius: '8px' }}
              placeholder="Search carrier, destination, tracking..."
              value={searchQuery}
              onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
            />
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-faint)' }}>
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
          </div>
        </div>

        {/* Shipments Table */}
        <div className="panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Active Freight &amp; Logistics Tracking</h2>
              <p style={{ fontSize: '13px', color: 'var(--text-dim)' }}>
                Real-time tracking of outbound shipments, vendor freight, and 3PL courier integrations.
              </p>
            </div>
            {isOperator && (
              <Link href="/connectors" className="btn btn-secondary text-xs">
                + Connect 3PL / Carrier API
              </Link>
            )}
          </div>

          {loading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="skeleton" style={{ height: '50px', borderRadius: '8px' }}></div>
              ))}
            </div>
          ) : paginatedShipments.length === 0 ? (
            <EmptyState 
              icon="🚢"
              title="No Shipments Found"
              description={searchQuery ? `No active shipments matching "${searchQuery}".` : "No shipments found matching the selected filter."}
              actionLabel={isOperator ? "Manage Logistics Connectors" : undefined}
              onAction={isOperator ? () => window.location.href = "/connectors" : undefined}
            />
          ) : (
            <>
              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Shipment ID</th>
                      <th>Carrier</th>
                      <th>Tracking Number</th>
                      <th>Destination</th>
                      <th>Cargo Units</th>
                      <th>Status</th>
                      <th>Estimated Delivery</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedShipments.map((s) => (
                      <tr key={s.id}>
                        <td className="mono font-medium">{s.id}</td>
                        <td className="font-medium">{s.carrier}</td>
                        <td className="mono text-xs text-faint">{s.trackingNumber}</td>
                        <td>{s.destination}</td>
                        <td className="mono">{s.itemsCount.toLocaleString()} units</td>
                        <td>
                          <span
                            className={`badge ${
                              s.status === 'delivered' ? 'active' :
                              s.status === 'delayed' ? 'error' : 'warning'
                            }`}
                          >
                            {s.status.replace('_', ' ').toUpperCase()}
                          </span>
                        </td>
                        <td className="text-faint">{s.eta}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <Pagination 
                currentPage={currentPage}
                totalItems={totalFiltered}
                pageSize={pageSize}
                onPageChange={setCurrentPage}
                onPageSizeChange={setPageSize}
                pageSizeOptions={[5, 10, 20]}
              />
            </>
          )}
        </div>

      </div>
    </main>
  );
}
