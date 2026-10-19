"use client";

import { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { AmbientVoiceStudio } from "@/components/AmbientVoiceStudio";

function AICommandCenterContent() {
  const searchParams = useSearchParams();
  const contextParam = searchParams.get("context");

  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [homeData, setHomeData] = useState<any>(null);
  const [contextAgent, setContextAgent] = useState(contextParam || "Auto");
  const [isVoiceStudioOpen, setIsVoiceStudioOpen] = useState(false);
  const [playingIdx, setPlayingIdx] = useState<number | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState<string>("");
  const [micPermission, setMicPermission] = useState<"granted" | "denied" | "prompt" | "unknown">("unknown");
  const [notifPermission, setNotifPermission] = useState<string>("default");
  const [permNotice, setPermNotice] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const recognitionRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Monitor device permissions for microphone and notifications
  useEffect(() => {
    if (typeof window !== "undefined" && "Notification" in window) {
      setNotifPermission(Notification.permission);
    }
    if (typeof navigator !== "undefined" && (navigator as any).permissions?.query) {
      try {
        (navigator as any).permissions.query({ name: "microphone" })
          .then((perm: any) => {
            setMicPermission(perm.state);
            perm.onchange = () => setMicPermission(perm.state);
          })
          .catch(() => {});
      } catch {
        // ignore
      }
    }
  }, []);

  const requestMicPermission = async () => {
    setPermNotice("Requesting microphone permission from your device... Please click 'Allow' on the browser prompt!");
    if (typeof navigator !== "undefined" && navigator.mediaDevices?.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((track) => track.stop());
        setMicPermission("granted");
        setPermNotice("Microphone permission granted by device! You can now dictate queries.");
        setTimeout(() => setPermNotice(null), 3500);
        return true;
      } catch (err: any) {
        console.warn("Microphone permission denied:", err);
        setMicPermission("denied");
        setPermNotice("Microphone access was denied on this device. Click the lock/tune icon in your browser URL bar to change Microphone to 'Allow'.");
        return false;
      }
    } else {
      setPermNotice("Audio input devices are not supported or accessible in this browser context.");
      return false;
    }
  };

  const requestNotifPermission = async () => {
    if (typeof window !== "undefined" && "Notification" in window) {
      try {
        setPermNotice("Requesting device notification permission... Please click 'Allow' on the browser prompt!");
        const res = await Notification.requestPermission();
        setNotifPermission(res);
        if (res === "granted") {
          setPermNotice("Device notifications allowed successfully!");
          try {
            new Notification("AI-Native ERP", {
              body: "Device notifications enabled. You will receive real-time operational alerts.",
              icon: "/favicon.ico"
            });
          } catch {}
          setTimeout(() => setPermNotice(null), 3500);
        } else {
          setPermNotice("Device notification permission was not granted.");
          setTimeout(() => setPermNotice(null), 3500);
        }
      } catch (err) {
        console.warn("Notification permission error:", err);
      }
    } else {
      setPermNotice("Desktop notifications are not supported in this browser.");
    }
  };

  const playTTS = (text: string, idx: number) => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (playingIdx === idx) {
      setPlayingIdx(null);
      return;
    }
    setPlayingIdx(idx);
    const cleanText = text.replace(/\[\^[0-9]+\]/g, "").slice(0, 500);
    const audioUrl = `/api/v1/tts/speak?text=${encodeURIComponent(cleanText)}`;
    const audio = new Audio(audioUrl);
    audioRef.current = audio;
    audio.play().catch(() => setPlayingIdx(null));
    audio.onended = () => setPlayingIdx(null);
    audio.onerror = () => setPlayingIdx(null);
  };

  const handleVoiceInput = async () => {
    if (isListening && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
      setIsListening(false);
      setVoiceStatus("Voice input stopped.");
      setTimeout(() => setVoiceStatus(""), 2500);
      return;
    }

    // Step 1: Ensure hardware device microphone permission is requested & granted
    if (micPermission !== "granted") {
      const allowed = await requestMicPermission();
      if (!allowed) return;
    }

    // Step 2: Initialize Speech Recognition
    const SpeechRecognition = typeof window !== "undefined" ? ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition) : null;
    if (!SpeechRecognition) {
      setPermNotice("Voice input requires Google Chrome, Microsoft Edge, or a browser with SpeechRecognition support.");
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;
      recognition.lang = "en-US";
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      setIsListening(true);
      setVoiceStatus("Microphone activating... Speak now!");

      recognition.onstart = () => {
        setIsListening(true);
        setVoiceStatus("Listening... Speak clearly into your device microphone!");
      };

      recognition.onresult = (event: any) => {
        let transcript = "";
        for (let i = 0; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        if (transcript) {
          setQuery(transcript);
          setVoiceStatus(`Recognized: "${transcript}"`);
        }
      };

      recognition.onerror = (event: any) => {
        console.warn("Speech recognition error:", event.error);
        setIsListening(false);
        if (event.error === "not-allowed" || event.error === "permission-denied") {
          setMicPermission("denied");
          setPermNotice("Microphone permission was blocked on this device. Click the lock/site settings icon in your browser URL bar to allow microphone.");
        } else if (event.error === "no-speech") {
          setVoiceStatus("No speech detected. Click the mic icon again to try.");
          setTimeout(() => setVoiceStatus(""), 3500);
        } else {
          setVoiceStatus(`Speech input error: ${event.error}`);
          setTimeout(() => setVoiceStatus(""), 3500);
        }
      };

      recognition.onend = () => {
        setIsListening(false);
        setTimeout(() => setVoiceStatus(""), 3000);
      };

      recognition.start();
    } catch (err: any) {
      console.error("Speech recognition start failed:", err);
      setIsListening(false);
      setPermNotice("Could not start microphone. Please ensure microphone permissions are allowed.");
    }
  };

  useEffect(() => {
    if (contextParam) {
      setContextAgent(contextParam);
      setQuery(`Analyze ${contextParam} data`);
    }
  }, [contextParam]);

  useEffect(() => {
    let isMounted = true;
    apiClient.get("/api/v1/dashboard/home")
      .then(data => {
        if (isMounted && data) setHomeData(data);
      })
      .catch(() => {
        // Fallback demo data
        if (isMounted) {
          setHomeData({
            total_revenue: "$1.42M",
            active_orders: 142,
            inventory_skus: 388,
            agent_actions_today: 64,
          });
        }
      });
    return () => { isMounted = false; };
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isSearching]);

  const handleSearch = async (e?: React.FormEvent, presetQuery?: string) => {
    if (e) e.preventDefault();
    const q = presetQuery || query;
    if (!q.trim()) return;
    
    const userMsg = { role: "user", content: q };
    setMessages((prev) => [...prev, userMsg]);
    setQuery("");
    setIsSearching(true);
    
    try {
      const data = await apiClient.post("/api/v1/dashboard/command", { query: q });
      setMessages((prev) => [...prev, { role: "ai", data }]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [...prev, { role: "ai", error: "AI analysis temporarily unavailable. Your ERP data is unchanged." }]);
    } finally {
      setIsSearching(false);
    }
  };

  const loadConversation = async (q: string) => {
    setQuery("");
    const userMsg = { role: "user", content: q };
    setMessages([userMsg]);
    setIsSearching(true);
    
    try {
      const data = await apiClient.post("/api/v1/dashboard/command", { query: q });
      setMessages([{ role: "user", content: q }, { role: "ai", data }]);
    } catch (err) {
      console.error(err);
      setMessages([{ role: "user", content: q }, { role: "ai", error: "AI analysis temporarily unavailable." }]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleAction = (actionIdx: number, msgIdx: number, type: string) => {
    const newMessages = [...messages];
    const msg = newMessages[msgIdx];
    if (msg.data && msg.data.actions && msg.data.actions[actionIdx]) {
      msg.data.actions[actionIdx].status = type === 'approve' ? 'Approved → Executing → Completed' : type === 'reject' ? 'Rejected' : 'Modifying...';
    }
    setMessages(newMessages);
  };

  return (
    <main className="main" style={{ display: 'flex', flexDirection: 'row', gap: '0', height: '100vh', overflow: 'hidden' }}>
      
      {/* Left Column: Conversation History */}
      <div style={{ width: '260px', background: 'var(--surface)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto', padding: '24px' }}>
        <button onClick={() => { setMessages([]); setQuery(""); }} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'flex-start', marginBottom: '24px', background: 'var(--bg)' }}>
          <span style={{ marginRight: '8px' }}>+</span> New Conversation
        </button>

        <h3 className="text-xs font-semibold mb-3 text-faint uppercase">Conversations</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '24px' }}>
          <div style={{ padding: '12px', borderRadius: '8px', background: 'var(--bg)', border: '1px solid var(--border-soft)', fontSize: '12px', color: 'var(--text-faint)', textAlign: 'center' }}>
            No active conversation history. Start typing your command below.
          </div>
        </div>
      </div>

      {/* Center Column: Command Center */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div className="topbar" style={{ padding: '24px 32px', borderBottom: 'none' }}>
          <div className="breadcrumb">AI Command Center</div>
        </div>

        <div className="content" style={{ flex: 1, overflowY: 'auto', padding: '0 32px 24px 32px', display: 'flex', flexDirection: 'column' }}>
          
          {messages.length === 0 ? (
            <div style={{ margin: 'auto', width: '100%', maxWidth: '680px', textAlign: 'center' }}>
              <h1 className="display" style={{ fontSize: '32px', marginBottom: '8px' }}>Ask your business anything</h1>
              <p className="text-dim mb-4">Ask, analyze and act across your business with real-time AI and voice synthesis.</p>
              
              {/* Prominent Text-To-Speech (TTS) Showcase Card */}
              <div 
                style={{ 
                  margin: '20px auto 28px', 
                  padding: '12px 20px', 
                  borderRadius: '24px', 
                  background: 'var(--surface)', 
                  border: '1px solid var(--border)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '14px',
                  boxShadow: '0 4px 20px rgba(0,0,0,0.04)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '20px' }}>🔊</span>
                  <div style={{ textAlign: 'left' }}>
                    <div style={{ fontSize: '13px', fontWeight: 600 }}>Neural Text-to-Speech (TTS)</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-faint)' }}>OpenAI HD & Sarvam AI Indic Voice Synthesis</div>
                  </div>
                </div>

                <div style={{ height: '22px', width: '1px', background: 'var(--border)' }} />

                <button
                  type="button"
                  onClick={() => playTTS("Welcome to your Agentic ERP Command Center. High definition neural Text to Speech is active and ready. Click any question below to generate a live business analysis and hear its vocalized summary.", -1)}
                  className="btn text-xs"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '7px 16px',
                    borderRadius: '20px',
                    background: playingIdx === -1 ? 'rgba(16, 185, 129, 0.15)' : 'var(--ai-core)',
                    color: playingIdx === -1 ? '#10b981' : 'white',
                    border: 'none',
                    fontWeight: 600,
                    cursor: 'pointer',
                    boxShadow: '0 2px 10px rgba(99, 102, 241, 0.25)'
                  }}
                  title="Click to hear Text-to-Speech audio demo"
                >
                  <span>{playingIdx === -1 ? "⏹️ Stop Audio" : "▶️ Play TTS Audio Demo"}</span>
                </button>
              </div>

              <div style={{ fontSize: '12px', color: 'var(--text-faint)', marginBottom: '12px' }}>
                💡 Click any question below to see live ERP analysis and hear its <strong>🔊 Listen (TTS)</strong> summary:
              </div>

              <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', flexWrap: 'wrap' }}>
                <button onClick={() => handleSearch(undefined, "Why did revenue change this month?")} className="btn btn-secondary text-xs">Why did revenue change this month?</button>
                <button onClick={() => handleSearch(undefined, "Which products are at risk of stockout?")} className="btn btn-secondary text-xs">Which products are at risk of stockout?</button>
                <button onClick={() => handleSearch(undefined, "Compare raw material supplier quotes")} className="btn btn-secondary text-xs">Compare raw material supplier quotes</button>
                <button onClick={() => handleSearch(undefined, "Show overdue invoices")} className="btn btn-secondary text-xs">Show overdue invoices</button>
                <button onClick={() => handleSearch(undefined, "What requires my attention today?")} className="btn btn-secondary text-xs">What requires my attention today?</button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', maxWidth: '800px', margin: '0 auto', width: '100%', paddingBottom: '40px' }}>
              {messages.map((msg, idx) => (
                <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                  
                  {msg.role === 'user' ? (
                    <div style={{ background: 'var(--text)', color: 'var(--bg)', padding: '16px 20px', borderRadius: '16px', borderBottomRightRadius: '4px', fontSize: '16px', maxWidth: '80%' }}>
                      {msg.content}
                    </div>
                  ) : (
                    <div style={{ width: '100%' }}>
                      {msg.error ? (
                        <div style={{ color: 'var(--danger)', background: 'var(--surface)', padding: '16px', borderRadius: '12px', border: '1px solid var(--danger)' }}>
                          {msg.error}
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                          
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span className="badge" style={{ background: 'var(--verified)', color: '#000', padding: '4px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600 }}>
                              ✓ Handled by {msg.data.agent_name}
                            </span>
                            <button
                              type="button"
                              onClick={() => playTTS(msg.data.summary || msg.data.recommendation || "Analysis completed.", idx)}
                              className="btn btn-secondary text-xs"
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '4px 10px',
                                borderRadius: '6px',
                                background: playingIdx === idx ? 'rgba(16, 185, 129, 0.15)' : 'var(--surface-2)',
                                color: playingIdx === idx ? '#10b981' : 'var(--text)',
                                borderColor: playingIdx === idx ? '#10b981' : 'var(--border)'
                              }}
                              title="Listen to neural voice summary (TTS)"
                            >
                              {playingIdx === idx ? "⏹️ Stop Audio" : "🔊 Listen to Summary (TTS)"}
                            </button>
                          </div>

                          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '12px', padding: '24px', boxShadow: '0 4px 20px rgba(0,0,0,0.02)' }}>
                            
                            {/* Summary */}
                            <div style={{ marginBottom: '24px' }}>
                              <h3 className="text-xs font-semibold" style={{ textTransform: 'uppercase', marginBottom: '8px', color: 'var(--text-faint)' }}>Executive Summary</h3>
                              <p className="text-base">{msg.data.summary}</p>
                            </div>

                            {/* Findings / Evidence */}
                            {msg.data.findings && (
                              <div style={{ marginBottom: '24px' }}>
                                <h3 className="text-xs font-semibold" style={{ textTransform: 'uppercase', marginBottom: '12px', color: 'var(--text-faint)' }}>Evidence</h3>
                                <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
                                  {msg.data.findings.map((f: any, i: number) => (
                                    <div key={i} className="kpi-card" style={{ padding: '12px' }}>
                                      <div className="kpi-label" style={{ fontSize: '11px' }}>{f.label}</div>
                                      <div className="kpi-val" style={{ fontSize: '16px', marginTop: '4px' }}>{f.value}</div>
                                    </div>
                                  ))}
                                </div>
                                {msg.data.evidence && (
                                  <p className="text-sm text-dim mt-3">{msg.data.evidence}</p>
                                )}
                              </div>
                            )}

                            {/* Data Table */}
                            {msg.data.table && (
                              <div style={{ marginBottom: '24px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                  <h3 className="text-xs font-semibold" style={{ textTransform: 'uppercase', color: 'var(--text-faint)' }}>Analysis Table</h3>
                                  <button 
                                    className="btn btn-secondary text-xs" 
                                    onClick={() => {
                                      const csvContent = "data:text/csv;charset=utf-8," 
                                        + [msg.data.table.columns.join(","), ...msg.data.table.rows.map((e: string[]) => e.map(x => `"${x}"`).join(","))].join("\n");
                                      const encodedUri = encodeURI(csvContent);
                                      const link = document.createElement("a");
                                      link.setAttribute("href", encodedUri);
                                      link.setAttribute("download", `${msg.data.agent_name.toLowerCase().replace(/\s+/g, '_')}_analysis.csv`);
                                      document.body.appendChild(link);
                                      link.click();
                                      document.body.removeChild(link);
                                    }}
                                  >
                                    ⬇ Export CSV
                                  </button>
                                </div>
                                <div className="table-wrapper">
                                  <table>
                                    <thead>
                                      <tr>
                                        {msg.data.table.columns.map((c: string, i: number) => (
                                          <th key={i}>{c}</th>
                                        ))}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {msg.data.table.rows.map((r: string[], i: number) => (
                                        <tr key={i}>
                                          {r.map((c: string, j: number) => (
                                            <td key={j}>{c}</td>
                                          ))}
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            )}

                            {/* Sources */}
                            {msg.data.sources && (
                              <div style={{ marginBottom: '24px' }}>
                                <h3 className="text-xs font-semibold" style={{ textTransform: 'uppercase', marginBottom: '8px', color: 'var(--text-faint)' }}>Data Sources</h3>
                                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                  {msg.data.sources.map((src: string, i: number) => (
                                    <span key={i} className="badge" style={{ background: 'var(--surface-2)', color: 'var(--text-dim)', border: '1px solid var(--border)', fontSize: '11px' }}>{src}</span>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Recommendation & Actions */}
                            {msg.data.recommendation && (
                              <div>
                                <h3 className="text-xs font-semibold" style={{ textTransform: 'uppercase', marginBottom: '8px', color: 'var(--text-faint)' }}>Recommendation</h3>
                                <p className="text-base mb-4">{msg.data.recommendation}</p>
                                
                                {msg.data.actions && msg.data.actions.map((act: any, i: number) => (
                                  <div key={i} style={{ border: '1px solid var(--border)', borderRadius: '8px', padding: '16px', background: 'var(--bg)', marginTop: '12px' }}>
                                    <h4 className="font-semibold text-base mb-2">{act.title}</h4>
                                    <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 16px 0', fontSize: '13px', color: 'var(--text-dim)' }}>
                                      {act.details.map((d: string, j: number) => (
                                        <li key={j} style={{ marginBottom: '4px' }}>• {d}</li>
                                      ))}
                                    </ul>
                                    
                                    {act.status ? (
                                      <div style={{ padding: '8px 12px', background: 'var(--surface-2)', borderRadius: '6px', fontSize: '13px', fontWeight: 500, color: act.status.includes('Approved') ? 'var(--verified)' : 'var(--text)' }}>
                                        {act.status}
                                      </div>
                                    ) : (
                                      <div style={{ display: 'flex', gap: '8px' }}>
                                        <button className="btn btn-primary" onClick={() => handleAction(i, idx, 'approve')}>Approve</button>
                                        <button className="btn btn-secondary" onClick={() => handleAction(i, idx, 'modify')}>Modify</button>
                                        <button className="btn btn-secondary" onClick={() => handleAction(i, idx, 'reject')}>Reject</button>
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                          
                          {/* Follow-up actions */}
                          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                            <button className="btn btn-secondary text-xs" onClick={() => handleSearch(undefined, "Show evidence")}>Show Evidence</button>
                            <button className="btn btn-secondary text-xs" onClick={() => handleSearch(undefined, "Create Report")}>Create Report</button>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
              
              {isSearching && (
                <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                  <div className="skeleton" style={{ width: '60%', height: '200px', borderRadius: '12px' }}></div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Advanced Input Area */}
        <div style={{ padding: '24px 32px', borderTop: '1px solid var(--border)', background: 'var(--surface)' }}>
          <form onSubmit={(e) => handleSearch(e)} style={{ position: 'relative', maxWidth: '800px', margin: '0 auto', display: 'flex', flexDirection: 'column' }}>
            
            {/* Smart Context Selector */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
              {["Auto", "Finance", "Inventory", "Procurement", "Sales", "Operations", "HR", "Analytics", "Compliance"].map(agent => (
                <button 
                  key={agent} 
                  type="button"
                  onClick={() => setContextAgent(agent)}
                  style={{ 
                    padding: '4px 12px', 
                    borderRadius: '16px', 
                    fontSize: '11px', 
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: contextAgent === agent ? 'var(--ai-core)' : 'transparent',
                    color: contextAgent === agent ? 'white' : 'var(--text-faint)',
                    border: `1px solid ${contextAgent === agent ? 'var(--ai-core)' : 'var(--border)'}`,
                    transition: 'all 0.2s'
                  }}
                >
                  {agent}
                </button>
              ))}
            </div>

            <div style={{ position: 'relative' }}>
              <input 
                type="text" 
                className="ai-cmd-input" 
                style={{ padding: '16px 125px 16px 20px', fontSize: '16px', borderRadius: '24px' }}
                placeholder="Ask, analyze or take action across your business..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={isSearching}
              />
              
              <div style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button onClick={() => alert("Opening file picker...")} type="button" className="btn" style={{ background: 'transparent', padding: '6px', color: 'var(--text-dim)', border: 'none', cursor: 'pointer' }} title="Attach file">
                  {/* Paperclip */}
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>
                </button>
                
                {/* ChatGPT-Style Blue Circular Waveform Voice Mode Button */}
                <button 
                  onClick={() => setIsVoiceStudioOpen(true)} 
                  type="button" 
                  className="btn" 
                  style={{ 
                    background: '#2563EB', 
                    width: '34px', 
                    height: '34px', 
                    borderRadius: '50%', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center', 
                    border: 'none', 
                    cursor: 'pointer',
                    boxShadow: '0 2px 8px rgba(37, 99, 235, 0.4)',
                    transition: 'all 0.15s ease',
                    flexShrink: 0
                  }} 
                  title="Open Voice Mode"
                >
                  {/* 4 Vertical Audio Waveform Bars (Exact ChatGPT Style) */}
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <rect x="3.5" y="8" width="2.8" height="8" rx="1.4" fill="white" />
                    <rect x="8.7" y="4" width="2.8" height="16" rx="1.4" fill="white" />
                    <rect x="13.9" y="6" width="2.8" height="12" rx="1.4" fill="white" />
                    <rect x="19.1" y="9" width="2.8" height="6" rx="1.4" fill="white" />
                  </svg>
                </button>

                <button type="submit" disabled={isSearching || !query.trim()} style={{ background: query.trim() ? 'var(--ai-core)' : 'transparent', color: query.trim() ? 'white' : 'var(--text-faint)', width: '34px', height: '34px', borderRadius: '17px', display: 'flex', alignItems: 'center', justifyContent: 'center', border: 'none', cursor: query.trim() ? 'pointer' : 'default', opacity: (isSearching || !query.trim()) ? 0.35 : 1, transition: 'all 0.15s' }} title="Send query">
                  {/* Send */}
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13"></line>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                  </svg>
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>

      {/* Right Column: Operational Widgets */}
      <div style={{ width: '320px', background: 'var(--surface)', borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto', padding: '24px' }}>
        <h2 className="text-sm font-semibold mb-4 text-faint uppercase">AI Insights</h2>
        {homeData?.insights ? homeData.insights.map((ins: any, i: number) => (
          <div key={i} style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: '8px', padding: '12px', marginBottom: '12px' }}>
            <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '4px' }}>{ins.title}</div>
            <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>{ins.desc}</div>
          </div>
        )) : (
          <div className="skeleton" style={{ height: '60px', borderRadius: '8px', marginBottom: '12px' }}></div>
        )}

        <h2 className="text-sm font-semibold mb-4 mt-8 text-faint uppercase">Pending Approvals</h2>
        {homeData?.approvals ? homeData.approvals.map((app: any, i: number) => (
          <div key={i} style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: '8px', padding: '12px', marginBottom: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div style={{ fontSize: '13px', fontWeight: 600 }}>{app.title}</div>
              <div style={{ fontSize: '12px', color: 'var(--warning)', background: 'var(--warning-soft)', padding: '2px 6px', borderRadius: '4px' }}>{app.risk}</div>
            </div>
            <div style={{ fontSize: '14px', marginBottom: '12px' }}>{app.amount}</div>
            <button onClick={() => alert("Opening approval modal...")} className="btn btn-secondary text-xs" style={{ width: '100%' }}>Review</button>
          </div>
        )) : (
          <div className="skeleton" style={{ height: '80px', borderRadius: '8px', marginBottom: '12px' }}></div>
        )}

        <h2 className="text-sm font-semibold mb-4 mt-8 text-faint uppercase">Agent Activity</h2>
        {homeData?.activity ? homeData.activity.map((act: any, i: number) => (
          <div key={i} style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--verified)', marginTop: '6px', flexShrink: 0 }}></div>
            <div>
              <div style={{ fontSize: '12px', fontWeight: 600 }}>{act.agent}</div>
              <div style={{ fontSize: '12px', color: 'var(--text)' }}>{act.action}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-faint)' }}>{act.time}</div>
            </div>
          </div>
        )) : (
          <div className="skeleton" style={{ height: '40px', borderRadius: '8px', marginBottom: '12px' }}></div>
        )}
      </div>
      
      {/* Ambient Neural Voice Studio (YC S-Tier Fullscreen Interactive Voice Modal) */}
      <AmbientVoiceStudio 
        isOpen={isVoiceStudioOpen} 
        onClose={() => setIsVoiceStudioOpen(false)} 
        onTranscriptSubmitted={(t) => {
          setQuery(t);
          handleSearch(undefined, t);
        }}
      />

    </main>
  );
}

export default function AICommandCenter() {
  return (
    <Suspense fallback={<div className="skeleton" style={{ height: '100vh', width: '100%' }}></div>}>
      <AICommandCenterContent />
    </Suspense>
  );
}
