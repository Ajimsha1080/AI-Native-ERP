"use client";

import { useState, useRef, useEffect } from "react";
import { apiClient } from "../lib/api-client";

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  branch?: string;
  intent_description?: string;
  citations?: Array<{
    source_index?: number;
    document_title: string;
    chunk_index?: number;
    department?: string;
    relevance_score?: number;
    excerpt?: string;
  }>;
}

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      role: "assistant",
      content: "Hello! I am your AI Copilot. Ask me anything about inventory, sales orders, finances, or enterprise policy documents.",
      intent_description: "Enterprise Copilot Ingress"
    }
  ]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || loading) return;

    const userText = input.trim();
    setInput("");
    const newMsgs: ChatMsg[] = [...messages, { role: "user", content: userText }];
    setMessages(newMsgs);
    setLoading(true);

    try {
      const history = newMsgs.map((m) => ({ role: m.role, content: m.content }));
      const res = await apiClient.post("/api/v1/chat", {
        messages: history,
        session_id: "global-copilot-widget"
      });

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.response || "Task processed.",
          branch: res.branch,
          intent_description: res.intent_description,
          citations: res.citations || []
        }
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "⚠️ Error communicating with the 6-Layer Agent & RAG Runtime. Please check backend service status.",
          branch: "error"
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Floating Launcher Button */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        style={{
          position: "fixed",
          bottom: "24px",
          right: "24px",
          width: "52px",
          height: "52px",
          borderRadius: "50%",
          background: "var(--accent, #6366f1)",
          color: "#ffffff",
          border: "none",
          boxShadow: "0 8px 24px rgba(0, 0, 0, 0.25)",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 9999,
          fontSize: "22px",
          transition: "transform 0.2s ease, box-shadow 0.2s ease",
        }}
        title="AI Copilot & RAG Assistant"
      >
        {isOpen ? "✕" : "✨"}
      </button>

      {/* Slide-over / Modal Chat Window */}
      {isOpen && (
        <div
          style={{
            position: "fixed",
            bottom: "86px",
            right: "24px",
            width: "380px",
            height: "520px",
            background: "var(--surface, #1e293b)",
            border: "1px solid var(--border, #334155)",
            borderRadius: "16px",
            boxShadow: "0 16px 40px rgba(0, 0, 0, 0.35)",
            display: "flex",
            flexDirection: "column",
            zIndex: 9999,
            overflow: "hidden",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "14px 16px",
              background: "var(--surface-2, #0f172a)",
              borderBottom: "1px solid var(--border, #334155)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div
                style={{
                  width: "10px",
                  height: "10px",
                  borderRadius: "50%",
                  background: "#10b981",
                }}
              />
              <span style={{ fontWeight: 600, fontSize: "13px", color: "var(--text, #f8fafc)" }}>
                AI-Native ERP Copilot
              </span>
            </div>
            <span style={{ fontSize: "11px", color: "var(--text-dim, #94a3b8)", background: "rgba(99, 102, 241, 0.15)", padding: "2px 6px", borderRadius: "4px" }}>
              6-Layer RAG
            </span>
          </div>

          {/* Messages Feed */}
          <div
            style={{
              flex: 1,
              padding: "16px",
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              fontSize: "13px",
            }}
          >
            {messages.map((m, idx) => (
              <div
                key={idx}
                style={{
                  alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                }}
              >
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: m.role === "user" ? "14px 14px 2px 14px" : "14px 14px 14px 2px",
                    background: m.role === "user" ? "var(--accent, #6366f1)" : "var(--surface-2, #334155)",
                    color: m.role === "user" ? "#ffffff" : "var(--text, #f8fafc)",
                    lineHeight: "1.5",
                    wordBreak: "break-word",
                  }}
                >
                  {m.content}
                </div>

                {/* Branch / Intent Tag */}
                {m.intent_description && (
                  <div style={{ fontSize: "10px", color: "var(--text-dim, #94a3b8)", marginLeft: "4px" }}>
                    ↳ {m.intent_description}
                  </div>
                )}

                {/* Citations View */}
                {m.citations && m.citations.length > 0 && (
                  <div
                    style={{
                      marginTop: "4px",
                      padding: "6px 8px",
                      background: "rgba(0, 0, 0, 0.2)",
                      borderRadius: "6px",
                      fontSize: "11px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "4px",
                      borderLeft: "2px solid var(--accent, #6366f1)",
                    }}
                  >
                    <div style={{ fontWeight: 600, color: "var(--text-dim, #94a3b8)" }}>Sources &amp; Citations:</div>
                    {m.citations.slice(0, 2).map((c, cIdx) => (
                      <div key={cIdx} style={{ color: "var(--text, #cbd5e1)" }}>
                        • <strong>{c.document_title}</strong> (Chunk #{c.chunk_index || 0})
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div style={{ alignSelf: "flex-start", color: "var(--text-dim, #94a3b8)", fontSize: "12px", fontStyle: "italic" }}>
                Thinking &amp; retrieving through 6-Layer Engine...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Bar */}
          <form
            onSubmit={handleSend}
            style={{
              padding: "12px",
              background: "var(--surface-2, #0f172a)",
              borderTop: "1px solid var(--border, #334155)",
              display: "flex",
              gap: "8px",
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask Copilot (e.g., check stock, PO policy)..."
              style={{
                flex: 1,
                padding: "8px 12px",
                background: "var(--bg, #020617)",
                border: "1px solid var(--border, #334155)",
                borderRadius: "8px",
                color: "var(--text, #f8fafc)",
                fontSize: "12px",
                outline: "none",
              }}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              style={{
                padding: "8px 14px",
                background: "var(--accent, #6366f1)",
                color: "#ffffff",
                border: "none",
                borderRadius: "8px",
                fontSize: "12px",
                fontWeight: 600,
                cursor: loading || !input.trim() ? "not-allowed" : "pointer",
                opacity: loading || !input.trim() ? 0.6 : 1,
              }}
            >
              Send
            </button>
          </form>
        </div>
      )}
    </>
  );
}
