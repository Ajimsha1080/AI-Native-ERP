"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

const ALL_COMMANDS = [
  { id: "ai", label: "Ask AI", icon: "✨", action: "/", type: "Action" },
  { id: "fin", label: "Open Finance", icon: "💰", action: "/finance", type: "Navigation" },
  { id: "inv", label: "Open Inventory", icon: "📦", action: "/inventory", type: "Navigation" },
  { id: "agt", label: "Open Agents", icon: "⚡", action: "/agents", type: "Navigation" },
  { id: "app", label: "Review Approvals", icon: "✅", action: "/approvals", type: "Navigation" },
  { id: "erp", label: "Connect ERP", icon: "🔗", action: "/connectors", type: "Navigation" },
  { id: "wf", label: "Create Workflow", icon: "⚡", action: "/workflows", type: "Action" },
  { id: "cust", label: "Search customer", icon: "👤", action: "/sales", type: "Search" },
  { id: "invc", label: "Search invoice", icon: "📄", action: "/finance", type: "Search" },
  { id: "prod", label: "Search product", icon: "🏷️", action: "/inventory", type: "Search" }
];

export default function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Toggle on Cmd+K or Ctrl+K
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      }
      
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const filteredCommands = query
    ? ALL_COMMANDS.filter((cmd) =>
        cmd.label.toLowerCase().includes(query.toLowerCase())
      )
    : ALL_COMMANDS;

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const executeCommand = (cmd: typeof ALL_COMMANDS[0]) => {
    setIsOpen(false);
    router.push(cmd.action);
  };

  const handleModalKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < filteredCommands.length - 1 ? prev + 1 : prev));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : prev));
    } else if (e.key === "Enter" && filteredCommands.length > 0) {
      e.preventDefault();
      executeCommand(filteredCommands[selectedIndex]);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="cmd-backdrop" onClick={() => setIsOpen(false)}>
      <div 
        className="cmd-modal" 
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleModalKeyDown}
      >
        <div className="cmd-header">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: 'var(--text-faint)' }}>
            <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <input
            ref={inputRef}
            type="text"
            className="cmd-input"
            placeholder="Type a command or search..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className="cmd-close" onClick={() => setIsOpen(false)}>
                      </button>
        </div>
        
        <div className="cmd-body">
          {filteredCommands.length > 0 ? (
            <div className="cmd-list">
              {filteredCommands.map((cmd, idx) => (
                <div
                  key={cmd.id}
                  className={`cmd-item ${idx === selectedIndex ? "selected" : ""}`}
                  onClick={() => executeCommand(cmd)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                >
                  <div className="cmd-item-icon">{cmd.icon}</div>
                  <div className="cmd-item-label">{cmd.label}</div>
                  <div className="cmd-item-type">{cmd.type}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="cmd-empty">
              No results found for &quot;{query}&quot;
            </div>
          )}
        </div>
        <div className="cmd-footer">
          <div className="cmd-footer-text">
            <span>↑↓</span> to navigate
            <span style={{ marginLeft: '16px' }}>↵</span> to execute
          </div>
        </div>
      </div>
    </div>
  );
}
