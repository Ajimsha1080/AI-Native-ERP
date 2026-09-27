"use client";

import { useState } from "react";
import { useAuth } from "../../lib/auth-context";
import { Pagination } from "../../components/Pagination";
import { EmptyState } from "../../components/EmptyState";
import { RoleBadge } from "../../components/RoleBadge";

export default function SettingsPage() {
  const { user, canPerform } = useAuth();
  const isAdmin = canPerform(["owner", "admin"]);

  const [activeTab, setActiveTab] = useState<"general" | "organization" | "team" | "apikeys" | "notifications">("general");

  // General settings state
  const [workspaceName, setWorkspaceName] = useState("Acme Industrial Corp");
  const [supportEmail, setSupportEmail] = useState("operations@acmeindustrial.com");
  const [strictMode, setStrictMode] = useState(false);
  const [autoSummarize, setAutoSummarize] = useState(true);
  const [savedSuccess, setSavedSuccess] = useState(false);

  // Team members state
  const [teamMembers, setTeamMembers] = useState([
    { id: 1, name: "Sarah Connor", email: "sarah@acmeindustrial.com", role: "owner", status: "active", joined: "2026-01-10" },
    { id: 2, name: "David Miller", email: "david@acmeindustrial.com", role: "admin", status: "active", joined: "2026-02-14" },
    { id: 3, name: "Elena Rostova", email: "elena@acmeindustrial.com", role: "manager", status: "active", joined: "2026-03-01" },
    { id: 4, name: "Marcus Chen", email: "marcus@acmeindustrial.com", role: "member", status: "active", joined: "2026-05-18" },
    { id: 5, name: "Sophia Taylor", email: "sophia@acmeindustrial.com", role: "viewer", status: "active", joined: "2026-07-22" },
    { id: 6, name: "James Wilson", email: "james@acmeindustrial.com", role: "member", status: "invited", joined: "2026-09-20" }
  ]);
  const [teamPage, setTeamPage] = useState(1);
  const [teamPageSize, setTeamPageSize] = useState(5);

  // API Keys state
  const [apiKeys, setApiKeys] = useState([
    { id: "key-prod-01", name: "Production ERP Pipeline", prefix: "erp_live_99a...", created: "2026-08-01", lastUsed: "Just now" },
    { id: "key-dev-02", name: "Staging Webhook Ingest", prefix: "erp_test_12b...", created: "2026-09-12", lastUsed: "2 hours ago" }
  ]);
  const [keyPage, setKeyPage] = useState(1);
  const [keyPageSize, setKeyPageSize] = useState(5);

  const handleSave = () => {
    if (!isAdmin) {
      alert("Unauthorized: Only Admins or Owners can modify workspace settings.");
      return;
    }
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  return (
    <main className="main">
      <div className="topbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="crumb">Settings</span>
          <span style={{ color: 'var(--text-faint)' }}>/</span>
          <span className="crumb-sub">Workspace preferences, RBAC team &amp; API keys</span>
          <RoleBadge role={user?.role} />
        </div>
        {isAdmin && (
          <button 
            onClick={handleSave}
            className="btn btn-primary" 
            style={{ marginLeft: 'auto', background: 'var(--ai-core)' }}
          >
            {savedSuccess ? "✓ Changes Saved!" : "Save Changes"}
          </button>
        )}
      </div>

      <div className="content" style={{ display: 'flex', gap: '32px' }}>
        {/* Navigation Sidebar */}
        <div style={{ width: '220px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {[
            { id: "general", label: "General" },
            { id: "organization", label: "Organization" },
            { id: "team", label: `Team Members (${teamMembers.length})` },
            { id: "apikeys", label: `API Keys (${apiKeys.length})` },
            { id: "notifications", label: "Notifications" }
          ].map(tab => (
            <button 
              key={tab.id}
              className="btn btn-secondary text-xs" 
              onClick={() => setActiveTab(tab.id as any)}
              style={{ 
                justifyContent: 'flex-start',
                padding: '10px 14px',
                background: activeTab === tab.id ? 'var(--surface-2)' : 'transparent',
                borderColor: activeTab === tab.id ? 'var(--border)' : 'transparent',
                color: activeTab === tab.id ? 'var(--text)' : 'var(--text-dim)',
                fontWeight: activeTab === tab.id ? 600 : 400
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Panels */}
        <div className="panel" style={{ flex: 1, padding: '32px', borderRadius: '12px' }}>
          {activeTab === "general" && (
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '24px' }}>General Settings</h2>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-dim)', marginBottom: '8px' }}>Workspace Name</label>
                  <input 
                    type="text" 
                    value={workspaceName}
                    disabled={!isAdmin}
                    onChange={(e) => setWorkspaceName(e.target.value)}
                    className="ai-cmd-input"
                    style={{ width: '100%', maxWidth: '400px', padding: '10px 12px' }} 
                  />
                </div>
                
                <div>
                  <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-dim)', marginBottom: '8px' }}>Support Email</label>
                  <input 
                    type="email" 
                    value={supportEmail}
                    disabled={!isAdmin}
                    onChange={(e) => setSupportEmail(e.target.value)}
                    className="ai-cmd-input"
                    style={{ width: '100%', maxWidth: '400px', padding: '10px 12px' }} 
                  />
                </div>

                <div style={{ borderTop: '1px solid var(--border-soft)', paddingTop: '24px', marginTop: '8px' }}>
                  <h3 style={{ fontSize: '15px', fontWeight: 500, marginBottom: '16px' }}>AI Agent Preferences</h3>
                  
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', maxWidth: '400px', marginBottom: '16px' }}>
                    <div>
                      <div style={{ fontSize: '14px', fontWeight: 500 }}>Strict Approval Mode</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>Require human approval for all agent write actions.</div>
                    </div>
                    <div 
                      onClick={() => isAdmin && setStrictMode(!strictMode)} 
                      style={{ width: '40px', height: '24px', borderRadius: '12px', background: strictMode ? 'var(--accent)' : 'var(--surface-2)', position: 'relative', cursor: isAdmin ? 'pointer' : 'not-allowed', transition: 'background 0.3s' }}
                    >
                      <div style={{ width: '18px', height: '18px', borderRadius: '9px', background: '#fff', position: 'absolute', top: '3px', left: strictMode ? '19px' : '3px', transition: 'left 0.3s' }}></div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', maxWidth: '400px' }}>
                    <div>
                      <div style={{ fontSize: '14px', fontWeight: 500 }}>Auto-Summarize Workflows</div>
                      <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>Generate end-of-day LangGraph summary reports.</div>
                    </div>
                    <div 
                      onClick={() => isAdmin && setAutoSummarize(!autoSummarize)} 
                      style={{ width: '40px', height: '24px', borderRadius: '12px', background: autoSummarize ? 'var(--accent)' : 'var(--surface-2)', position: 'relative', cursor: isAdmin ? 'pointer' : 'not-allowed', transition: 'background 0.3s' }}
                    >
                      <div style={{ width: '18px', height: '18px', borderRadius: '9px', background: '#fff', position: 'absolute', top: '3px', left: autoSummarize ? '19px' : '3px', transition: 'left 0.3s' }}></div>
                    </div>
                  </div>
                </div>
                
                {isAdmin && (
                  <div style={{ borderTop: '1px solid var(--border-soft)', paddingTop: '24px', marginTop: '8px' }}>
                    <button 
                      onClick={() => { if (confirm("Are you sure you want to permanently delete this workspace and all associated data?")) alert("Deletion canceled in demo mode."); }}
                      className="btn btn-secondary text-xs" 
                      style={{ color: 'var(--danger)', borderColor: 'var(--danger)', background: 'rgba(240,85,91,0.1)' }}
                    >
                      Delete Workspace
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "organization" && (
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>Organization Details</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '450px' }}>
                <div>
                  <label className="text-xs text-dim block mb-1">Company Legal Entity</label>
                  <input type="text" defaultValue="Acme Industrial Global, Inc." disabled={!isAdmin} className="ai-cmd-input" style={{ width: '100%', padding: '10px 12px' }} />
                </div>
                <div>
                  <label className="text-xs text-dim block mb-1">Primary Currency</label>
                  <select disabled={!isAdmin} className="ai-cmd-input" style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', color: 'var(--text)' }}>
                    <option value="USD">USD ($) - US Dollar</option>
                    <option value="EUR">EUR (€) - Euro</option>
                    <option value="GBP">GBP (£) - British Pound</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-dim block mb-1">Tenant Partition ID</label>
                  <div className="mono text-xs" style={{ padding: '10px 12px', background: 'var(--surface-2)', borderRadius: '6px' }}>
                    tenant_acme_corp_prod_099a
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "team" && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>Team Members &amp; RBAC Access</h2>
                  <p style={{ fontSize: '13px', color: 'var(--text-dim)', marginTop: '4px' }}>Manage user seats, invite team members, and configure role authorizations.</p>
                </div>
                {isAdmin && (
                  <button className="btn btn-primary text-xs" style={{ background: 'var(--ai-core)' }} onClick={() => alert("Invite member modal")}>
                    + Invite Member
                  </button>
                )}
              </div>

              {teamMembers.length === 0 ? (
                <EmptyState icon="👥" title="No Members" description="No members in this workspace." />
              ) : (
                <>
                  <div className="table-wrapper">
                    <table>
                      <thead>
                        <tr>
                          <th>User</th>
                          <th>Role</th>
                          <th>Status</th>
                          <th>Joined</th>
                          {isAdmin && <th style={{ textAlign: 'right' }}>Actions</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {teamMembers.slice((teamPage - 1) * teamPageSize, teamPage * teamPageSize).map((m) => (
                          <tr key={m.id}>
                            <td>
                              <div className="font-medium">{m.name}</div>
                              <div className="text-xs text-dim">{m.email}</div>
                            </td>
                            <td><RoleBadge role={m.role as any} /></td>
                            <td>
                              <span className={`badge ${m.status === 'active' ? 'active' : 'warning'}`}>
                                {m.status}
                              </span>
                            </td>
                            <td className="text-faint text-xs">{m.joined}</td>
                            {isAdmin && (
                              <td style={{ textAlign: 'right' }}>
                                <button className="btn btn-secondary text-xs" style={{ padding: '2px 8px' }}>
                                  Edit Role
                                </button>
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <Pagination 
                    currentPage={teamPage}
                    totalItems={teamMembers.length}
                    pageSize={teamPageSize}
                    onPageChange={setTeamPage}
                    onPageSizeChange={setTeamPageSize}
                    pageSizeOptions={[5, 10, 20]}
                  />
                </>
              )}
            </div>
          )}

          {activeTab === "apikeys" && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>API &amp; Webhook Keys</h2>
                  <p style={{ fontSize: '13px', color: 'var(--text-dim)', marginTop: '4px' }}>Secret tokens used to authenticate automated ERP integrations and CLI syncs.</p>
                </div>
                {isAdmin && (
                  <button className="btn btn-primary text-xs" style={{ background: 'var(--ai-core)' }} onClick={() => alert("Generate key")}>
                    + Generate New Key
                  </button>
                )}
              </div>

              {apiKeys.length === 0 ? (
                <EmptyState icon="🔑" title="No API Keys" description="No active API keys created." />
              ) : (
                <>
                  <div className="table-wrapper">
                    <table>
                      <thead>
                        <tr>
                          <th>Key Name</th>
                          <th>Token Prefix</th>
                          <th>Created</th>
                          <th>Last Used</th>
                          {isAdmin && <th style={{ textAlign: 'right' }}>Revoke</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {apiKeys.slice((keyPage - 1) * keyPageSize, keyPage * keyPageSize).map((k) => (
                          <tr key={k.id}>
                            <td className="font-medium">{k.name}</td>
                            <td className="mono text-xs">{k.prefix}</td>
                            <td className="text-faint text-xs">{k.created}</td>
                            <td className="text-dim text-xs">{k.lastUsed}</td>
                            {isAdmin && (
                              <td style={{ textAlign: 'right' }}>
                                <button className="btn btn-secondary text-xs" style={{ padding: '2px 8px', color: 'var(--danger)' }}>
                                  Revoke
                                </button>
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <Pagination 
                    currentPage={keyPage}
                    totalItems={apiKeys.length}
                    pageSize={keyPageSize}
                    onPageChange={setKeyPage}
                    onPageSizeChange={setKeyPageSize}
                    pageSizeOptions={[5, 10]}
                  />
                </>
              )}
            </div>
          )}

          {activeTab === "notifications" && (
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>Notification Channels</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '480px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div className="font-medium text-sm">Email Alerts for Approval Escalations</div>
                    <div className="text-xs text-dim">Receive emails when transactions &gt; $1,000 need approval.</div>
                  </div>
                  <input type="checkbox" defaultChecked disabled={!isAdmin} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div className="font-medium text-sm">Low Stock &amp; Inventory Alerts</div>
                    <div className="text-xs text-dim">Receive alerts when inventory drops below safety stock.</div>
                  </div>
                  <input type="checkbox" defaultChecked disabled={!isAdmin} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div className="font-medium text-sm">Daily Executive Summary Email</div>
                    <div className="text-xs text-dim">Daily digest of tasks completed and financial ledger entries.</div>
                  </div>
                  <input type="checkbox" defaultChecked disabled={!isAdmin} />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
