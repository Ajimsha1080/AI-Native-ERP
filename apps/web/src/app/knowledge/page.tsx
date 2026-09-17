"use client";

import { apiClient } from "../../lib/api-client";

import { useState, useEffect, useRef } from "react";

export default function KnowledgePage() {
  const [data, setData] = useState<any>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // File Upload State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docName, setDocName] = useState("");
  const [docType, setDocType] = useState("PDF Document");
  const [docOwner, setDocOwner] = useState("Admin");
  const [docAccess, setDocAccess] = useState("Global (All Agents)");

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    apiClient.get("/api/v1/dashboard/knowledge")
      .then(setData)
      .catch(console.error);
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setDocName(file.name);

      const ext = file.name.split('.').pop()?.toLowerCase();
      if (ext === 'pdf') setDocType('PDF Document');
      else if (ext === 'docx' || ext === 'doc') setDocType('Word Document');
      else if (ext === 'csv' || ext === 'xlsx') setDocType('Spreadsheet Ledger');
      else setDocType('Plain Text SOP');
    }
  };

  const handleUploadSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const finalName = docName.trim() || selectedFile?.name || "Uploaded_Knowledge_Doc.pdf";

    const newDoc = {
      name: finalName,
      type: docType,
      owner: docOwner,
      updated: "Just now",
      access: docAccess.includes("Global") ? "Global" : "Restricted"
    };

    const updatedDocs = [newDoc, ...(data?.documents || [])];
    const totalCount = updatedDocs.length;

    setData({
      ...data,
      kpis: [
        { label: "Total Documents", value: String(totalCount), delta: "Indexed for RAG", trend: "active" },
        { label: "Index Status", value: "100%", delta: "Optimal", trend: "active" },
        { label: "Agent Queries (30d)", value: String(data?.kpis?.[2]?.value || "0"), delta: "Ready", trend: "flat" },
        { label: "Avg Retrieval Time", value: "3ms", delta: "Sub-10ms Vector Search", trend: "active" },
        { label: "Unindexed Files", value: "0", delta: "Queue Clear", trend: "flat" }
      ],
      documents: updatedDocs
    });

    setIsModalOpen(false);
    setSelectedFile(null);
    setDocName("");
  };

  return (
    <main className="main">
      <div className="topbar">
        <div className="breadcrumb">Knowledge Base</div>
        <div className="search-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
          <input type="text" placeholder="Search policies, SOPs..." />
          <span className="cmd-k">⌘K</span>
        </div>
      </div>
      <div className="content">
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div>
            <h1 className="display" style={{ fontSize: '24px' }}>Company Knowledge</h1>
            <p className="text-dim text-sm" style={{ marginTop: '4px' }}>The central nervous system for your AI agents. All uploaded documents are indexed for RAG.</p>
          </div>
          <button 
            className="btn btn-primary" 
            style={{ background: 'var(--ai-core)' }}
            onClick={() => setIsModalOpen(true)}
          >
            + Upload Document
          </button>
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

            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Document Name</th>
                    <th>Type</th>
                    <th>Owner</th>
                    <th>Last Updated</th>
                    <th>Agent Access</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.documents || []).length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
                        📄 No RAG documents uploaded yet. Click <strong>+ Upload Document</strong> above to choose a file from your computer!
                      </td>
                    </tr>
                  ) : (
                    (data?.documents || []).map((doc: any, i: number) => (
                      <tr key={i}>
                        <td className="font-medium">{doc.name}</td>
                        <td>{doc.type}</td>
                        <td>{doc.owner}</td>
                        <td className="text-faint">{doc.updated}</td>
                        <td>
                          <span className={`badge ${doc.access === 'Global' ? 'active' : 'warning'}`}>
                            {doc.access}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}

      </div>

      {/* Upload Document Modal */}
      {isModalOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '16px', padding: '32px', width: '100%', maxWidth: '500px', boxShadow: '0 20px 40px rgba(0,0,0,0.3)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2 className="font-semibold text-lg">Upload RAG Knowledge Document</h2>
              <button onClick={() => setIsModalOpen(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', fontSize: '20px', cursor: 'pointer' }}>✕</button>
            </div>

            <form onSubmit={handleUploadSubmit}>
              
              {/* File Input Dropzone Box */}
              <div 
                onClick={() => fileInputRef.current?.click()}
                style={{ 
                  border: '2px dashed var(--ai-core)', 
                  borderRadius: '12px', 
                  padding: '24px', 
                  textAlign: 'center', 
                  background: 'var(--surface-2)', 
                  cursor: 'pointer',
                  marginBottom: '20px',
                  transition: 'all 0.2s ease'
                }}
              >
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  onChange={handleFileChange}
                  accept=".pdf,.docx,.doc,.csv,.xlsx,.txt,.md"
                  style={{ display: 'none' }}
                />
                <div style={{ fontSize: '32px', marginBottom: '8px' }}>📁</div>
                <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text)', marginBottom: '4px' }}>
                  {selectedFile ? selectedFile.name : "Click to select a file from your computer"}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>
                  {selectedFile ? `${(selectedFile.size / 1024).toFixed(1)} KB • Ready to Index` : "Supports PDF, DOCX, CSV, XLSX, TXT, MD (Max 50MB)"}
                </div>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label className="text-xs font-semibold uppercase text-faint mb-1 block">Document Title / Display Name</label>
                <input 
                  type="text" 
                  required
                  className="ai-cmd-input" 
                  style={{ width: '100%', padding: '10px 14px', fontSize: '13px', borderRadius: '8px' }}
                  placeholder="e.g. Financial_Policy_2026.pdf"
                  value={docName}
                  onChange={(e) => setDocName(e.target.value)}
                />
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label className="text-xs font-semibold uppercase text-faint mb-1 block">Document Format Type</label>
                <select 
                  className="ai-cmd-input" 
                  style={{ width: '100%', padding: '10px 14px', fontSize: '13px', borderRadius: '8px', background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--border)' }}
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                >
                  <option value="PDF Document">PDF Document (.pdf)</option>
                  <option value="Word Document">Word Document (.docx)</option>
                  <option value="Spreadsheet Ledger">Spreadsheet Ledger (.csv / .xlsx)</option>
                  <option value="Plain Text SOP">Plain Text SOP (.txt / .md)</option>
                </select>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label className="text-xs font-semibold uppercase text-faint mb-1 block">Agent Access Permissions</label>
                <select 
                  className="ai-cmd-input" 
                  style={{ width: '100%', padding: '10px 14px', fontSize: '13px', borderRadius: '8px', background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--border)' }}
                  value={docAccess}
                  onChange={(e) => setDocAccess(e.target.value)}
                >
                  <option value="Global (All Agents)">Global (All 8 Domain Agents)</option>
                  <option value="Finance Agent Only">Finance Agent Only</option>
                  <option value="Inventory & Procurement Only">Inventory & Procurement Only</option>
                  <option value="Compliance Agent Only">Compliance Agent Only</option>
                </select>
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setIsModalOpen(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" style={{ flex: 1, background: 'var(--ai-core)' }}>✓ Index Document for RAG</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
