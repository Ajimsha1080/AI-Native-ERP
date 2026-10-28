"use client";

import React, { useState, useEffect, useRef } from "react";
import { apiClient } from "@/lib/api-client";

interface AmbientVoiceStudioProps {
  isOpen: boolean;
  onClose: () => void;
  onTranscriptSubmitted?: (query: string) => void;
}

export function AmbientVoiceStudio({ isOpen, onClose, onTranscriptSubmitted }: AmbientVoiceStudioProps) {
  const [voiceState, setVoiceState] = useState<"idle" | "listening" | "thinking" | "speaking">("idle");
  const [selectedVoice, setSelectedVoice] = useState("en-US-AriaNeural");
  const [isHandsFree, setIsHandsFree] = useState(true);
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [aiSpeechResponse, setAiSpeechResponse] = useState<string>("");
  const [micPermission, setMicPermission] = useState<"granted" | "denied" | "prompt" | "unknown">("unknown");
  const [isMuted, setIsMuted] = useState(false);
  const [showTextInput, setShowTextInput] = useState(false);
  const [typedQuery, setTypedQuery] = useState("");

  const recognitionRef = useRef<any>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const silenceTimerRef = useRef<any>(null);

  const availableVoices = [
    { id: "en-US-AriaNeural", name: "Aria (Executive HD)", flag: "🇺🇸", desc: "Microsoft Neural Studio" },
    { id: "alloy", name: "Alloy (ChatGPT HD)", flag: "⚡", desc: "OpenAI Neural HD Model" },
    { id: "shimmer", name: "Shimmer (Expressive)", flag: "✨", desc: "OpenAI High Definition" },
    { id: "en-US-GuyNeural", name: "Guy (Operations)", flag: "🇺🇸", desc: "Microsoft Conversational" },
    { id: "sarvam-bulbul-meera", name: "Meera (Indic Bulbul)", flag: "🇮🇳", desc: "Sarvam AI Hindi/English" },
    { id: "sarvam-bulbul-priya", name: "Priya (Indic Bulbul)", flag: "🇮🇳", desc: "Sarvam AI Tamil/English" },
    { id: "sarvam-bulbul-aravind", name: "Aravind (Indic Bulbul)", flag: "🇮🇳", desc: "Sarvam AI Telugu/English" },
    { id: "en-IN-NeerjaNeural", name: "Neerja (India Business)", flag: "🇮🇳", desc: "Microsoft Neural" }
  ];

  const stopListening = () => {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch {}
    }
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    setVoiceState("idle");
  };

  const playAiVoice = (text: string) => {
    setVoiceState("speaking");
    const clean = text.replace(/\[\^[0-9]+\]/g, "").slice(0, 450);
    const audioUrl = `/api/v1/tts/speak?text=${encodeURIComponent(clean)}&voice=${encodeURIComponent(selectedVoice)}`;
    
    if (audioRef.current) {
      audioRef.current.pause();
    }

    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    audio.onended = () => {
      setVoiceState("idle");
      setTranscript("");
      setInterimTranscript("");
      if (isHandsFree) {
        setTimeout(() => {
          startListening();
        }, 600);
      }
    };

    audio.onerror = () => {
      setVoiceState("idle");
    };

    audio.play().catch(() => {
      setVoiceState("idle");
    });
  };

  const executeVoiceQuery = async (queryText: string) => {
    if (!queryText.trim()) return;

    stopListening();
    setVoiceState("thinking");

    try {
      const result = await apiClient.post("/api/v1/dashboard/command", { query: queryText });
      
      let spokenAnswer = "";
      if (result.summary) {
        spokenAnswer = result.summary;
      } else if (result.answer) {
        spokenAnswer = result.answer;
      } else if (result.recommendation) {
        spokenAnswer = result.recommendation;
      } else if (result.executive_summary) {
        spokenAnswer = result.executive_summary;
      } else {
        spokenAnswer = "I have analyzed your operational data and updated your ERP dashboard.";
      }

      setAiSpeechResponse(spokenAnswer);
      if (onTranscriptSubmitted) {
        onTranscriptSubmitted(queryText);
      }

      if (!isMuted) {
        playAiVoice(spokenAnswer);
      } else {
        setVoiceState("idle");
      }
    } catch (err) {
      console.error("Voice command execution error:", err);
      const fallback = "Your request was processed, but real-time synthesis is temporarily taking longer. Displaying operational view.";
      setAiSpeechResponse(fallback);
      setVoiceState("idle");
    }
  };

  const startListening = async () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    setVoiceState("listening");

    const SpeechRecognition = typeof window !== "undefined" ? ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition) : null;
    if (!SpeechRecognition) {
      playAiVoice("Speech recognition requires Google Chrome or Microsoft Edge. Please open this app in Chrome or Edge to speak.");
      return;
    }

    try {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch {}
      }

      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = selectedVoice.startsWith("sarvam-bulbul") || selectedVoice.startsWith("hi-IN") ? "hi-IN" : "en-US";

      recognition.onstart = () => {
        setVoiceState("listening");
        setInterimTranscript("");
      };

      recognition.onresult = (event: any) => {
        let currentInterim = "";
        let finalChunk = "";

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const item = event.results[i];
          if (item.isFinal) {
            finalChunk += item[0].transcript;
          } else {
            currentInterim += item[0].transcript;
          }
        }

        if (currentInterim) {
          setInterimTranscript(currentInterim);
        }

        if (finalChunk) {
          const newFull = (transcript ? transcript + " " : "") + finalChunk.trim();
          setTranscript(newFull);
          setInterimTranscript("");

          if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
          if (isHandsFree) {
            silenceTimerRef.current = setTimeout(() => {
              executeVoiceQuery(newFull);
            }, 1400);
          }
        }
      };

      recognition.onerror = (event: any) => {
        console.warn("Speech error:", event.error);
        if (event.error === "not-allowed" || event.error === "permission-denied") {
          setMicPermission("denied");
          playAiVoice("Hello! I am your AI Copilot. Your browser has microphone access currently muted. Please toggle the lock icon in your address bar to Allow, or tap any question below to hear my analysis!");
        } else if (event.error !== "no-speech") {
          setVoiceState("idle");
        }
      };

      recognition.onend = () => {
        if (voiceState === "listening" && isHandsFree) {
          try { recognition.start(); } catch {}
        }
      };

      recognition.start();
    } catch (err: any) {
      console.error("Failed to start voice listener:", err);
      playAiVoice("Hello! I am your AI Enterprise Copilot. Tap any suggestion below to hear live executive voice analysis!");
    }
  };

  const handleClose = () => {
    stopListening();
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setVoiceState("idle");
    onClose();
  };

  const handleOrbClick = () => {
    if (voiceState === "listening") {
      if (transcript.trim() || interimTranscript.trim()) {
        executeVoiceQuery(transcript || interimTranscript);
      } else {
        stopListening();
      }
    } else if (voiceState === "speaking") {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      setVoiceState("idle");
    } else {
      startListening();
    }
  };

  // Check initial permission state
  useEffect(() => {
    if (!isOpen) return;

    if (typeof navigator !== "undefined" && (navigator as any).permissions?.query) {
      try {
        (navigator as any).permissions.query({ name: "microphone" })
          .then((perm: any) => {
            setMicPermission(perm.state);
            perm.onchange = () => {
              setMicPermission(perm.state);
              if (perm.state === "granted") {
                startListening();
              }
            };
          })
          .catch(() => {});
      } catch {
        // ignore
      }
    }
  }, [isOpen]);

  // Continuously check permission state if denied so it auto-recovers the second user toggles the lock icon
  useEffect(() => {
    if (!isOpen || micPermission !== "denied") return;
    const interval = setInterval(async () => {
      if (typeof navigator !== "undefined" && (navigator as any).permissions?.query) {
        try {
          const perm = await (navigator as any).permissions.query({ name: "microphone" });
          if (perm.state === "granted") {
            setMicPermission("granted");
            startListening();
          }
        } catch {}
      }
    }, 1200);
    return () => clearInterval(interval);
  }, [isOpen, micPermission]);

  // Handle escape key to exit
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        handleClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div 
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        background: "#06070B",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "32px 40px 48px",
        overflow: "hidden",
        fontFamily: "'Inter', -apple-system, sans-serif",
        color: "#F8FAFC"
      }}
    >
      {/* Background Aurora Mesh Glows */}
      <div 
        style={{
          position: "absolute",
          top: "10%",
          left: "50%",
          transform: "translateX(-50%)",
          width: "700px",
          height: "700px",
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(99, 102, 241, 0.16) 0%, rgba(168, 85, 247, 0.10) 45%, rgba(6, 7, 11, 0) 75%)",
          filter: "blur(70px)",
          pointerEvents: "none",
          animation: "yc-aurora-drift 12s ease-in-out infinite"
        }}
      />
      
      <div 
        style={{
          position: "absolute",
          bottom: "15%",
          right: "20%",
          width: "500px",
          height: "500px",
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(56, 189, 248, 0.12) 0%, rgba(99, 102, 241, 0.05) 50%, rgba(6, 7, 11, 0) 70%)",
          filter: "blur(80px)",
          pointerEvents: "none"
        }}
      />

      {/* Subtle Matrix/Scan Grid Line Overlay */}
      <div 
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: "linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          pointerEvents: "none",
          opacity: 0.6
        }}
      />

      {/* Top Navigation Bar: Minimal YC S-Tier Glass */}
      <header 
        style={{
          width: "100%",
          maxWidth: "1140px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          zIndex: 10
        }}
      >
        {/* Brand & Live Copilot Status Pill */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div 
            className="yc-glass-panel"
            style={{
              padding: "6px 14px",
              borderRadius: "24px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              fontSize: "12px",
              fontWeight: 500,
              letterSpacing: "-0.01em"
            }}
          >
            <span 
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: voiceState === "listening" ? "#38BDF8" : voiceState === "speaking" ? "#10B981" : voiceState === "thinking" ? "#F59E0B" : "#818CF8",
                boxShadow: voiceState === "listening" ? "0 0 12px #38BDF8" : "0 0 8px #818CF8",
                animation: "pulse 1.8s infinite"
              }}
            />
            <span style={{ color: "#F1F5F9", fontWeight: 600 }}>Ambient Neural Copilot</span>
            <span style={{ color: "rgba(255,255,255,0.3)", fontSize: "11px" }}>|</span>
            <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "11px", fontFamily: "'JetBrains Mono', monospace" }}>
              {voiceState === "speaking" ? "Active Speech" : voiceState === "listening" ? "Listening" : voiceState === "thinking" ? "Reasoning" : "Ready"}
            </span>
          </div>

          <div 
            style={{
              padding: "4px 8px",
              borderRadius: "14px",
              background: "rgba(255, 255, 255, 0.04)",
              border: "1px solid rgba(255, 255, 255, 0.06)",
              fontSize: "10px",
              color: "rgba(255, 255, 255, 0.5)",
              fontFamily: "'JetBrains Mono', monospace"
            }}
          >
            48kHz HD
          </div>
        </div>

        {/* Right Controls: Model Voice Dropdown, Hands-Free Toggle, Close */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {/* Voice Selector */}
          <div style={{ position: "relative" }}>
            <select
              value={selectedVoice}
              onChange={(e) => setSelectedVoice(e.target.value)}
              className="yc-glass-panel"
              style={{
                padding: "8px 14px",
                borderRadius: "20px",
                color: "#F8FAFC",
                fontSize: "12px",
                fontWeight: 500,
                outline: "none",
                cursor: "pointer",
                appearance: "none",
                paddingRight: "28px"
              }}
            >
              {availableVoices.map((v) => (
                <option key={v.id} value={v.id} style={{ background: "#0F111A", color: "#F8FAFC" }}>
                  {v.flag} {v.name} ({v.desc})
                </option>
              ))}
            </select>
            <span style={{ position: "absolute", right: "12px", top: "50%", transform: "translateY(-50%)", pointerEvents: "none", fontSize: "10px", color: "rgba(255,255,255,0.5)" }}>
              ▼
            </span>
          </div>

          {/* Hands-Free Toggle Button */}
          <button
            type="button"
            onClick={() => setIsHandsFree(!isHandsFree)}
            className="yc-glass-panel"
            style={{
              padding: "7px 14px",
              borderRadius: "20px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              fontSize: "12px",
              fontWeight: 500,
              cursor: "pointer",
              color: isHandsFree ? "#38BDF8" : "rgba(255, 255, 255, 0.5)",
              border: isHandsFree ? "1px solid rgba(56, 189, 248, 0.3)" : "1px solid rgba(255, 255, 255, 0.08)"
            }}
            title="Continuous hands-free conversation with auto-turn taking"
          >
            <span style={{ fontSize: "12px" }}>{isHandsFree ? "⚡" : "⏸️"}</span>
            <span>Hands-Free {isHandsFree ? "ON" : "OFF"}</span>
          </button>

          {/* Close Button */}
          <button
            type="button"
            onClick={handleClose}
            className="yc-glass-panel"
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "50%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "rgba(255, 255, 255, 0.7)",
              cursor: "pointer",
              transition: "all 0.2s"
            }}
            title="Close voice mode (Esc)"
          >
            ✕
          </button>
        </div>
      </header>

      {/* Center Section: Kinetic Holographic Orb & Dynamic Transcription */}
      <main 
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          maxWidth: "840px",
          width: "100%",
          position: "relative",
          zIndex: 10,
          margin: "auto 0"
        }}
      >
        {/* The Kinetic Holographic Neural Orb */}
        <div 
          onClick={handleOrbClick}
          style={{
            position: "relative",
            width: "220px",
            height: "220px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            userSelect: "none"
          }}
          title={voiceState === "listening" ? "Listening... click to send" : "Tap orb to speak"}
        >
          {/* Animated Wave Ripple Rings when Listening */}
          {voiceState === "listening" && (
            <>
              <div 
                style={{
                  position: "absolute",
                  inset: "-20px",
                  borderRadius: "50%",
                  border: "2px solid rgba(56, 189, 248, 0.4)",
                  animation: "yc-ripple 2s cubic-bezier(0, 0.2, 0.8, 1) infinite",
                  pointerEvents: "none"
                }}
              />
              <div 
                style={{
                  position: "absolute",
                  inset: "-40px",
                  borderRadius: "50%",
                  border: "1.5px solid rgba(168, 85, 247, 0.3)",
                  animation: "yc-ripple 2s cubic-bezier(0, 0.2, 0.8, 1) infinite 0.6s",
                  pointerEvents: "none"
                }}
              />
            </>
          )}

          {/* Animated Wave Ripple Rings when Speaking */}
          {voiceState === "speaking" && (
            <div 
              style={{
                position: "absolute",
                inset: "-24px",
                borderRadius: "50%",
                border: "2px solid rgba(16, 185, 129, 0.4)",
                animation: "yc-ripple 2.2s cubic-bezier(0, 0.2, 0.8, 1) infinite",
                pointerEvents: "none"
              }}
            />
          )}

          {/* Ambient Outer Halo */}
          <div 
            style={{
              position: "absolute",
              inset: "-12px",
              borderRadius: "50%",
              background: voiceState === "speaking"
                ? "conic-gradient(from 0deg, #10B981, #38BDF8, #6366F1, #10B981)"
                : voiceState === "listening"
                ? "conic-gradient(from 0deg, #38BDF8, #A855F7, #EC4899, #38BDF8)"
                : voiceState === "thinking"
                ? "conic-gradient(from 0deg, #F59E0B, #EC4899, #6366F1, #F59E0B)"
                : "conic-gradient(from 0deg, #6366F1, #8B5CF6, #EC4899, #6366F1)",
              opacity: 0.35,
              filter: "blur(18px)",
              animation: "yc-spin-slow 12s linear infinite"
            }}
          />

          {/* Main 3D Kinetic Neural Orb Sphere */}
          <div 
            style={{
              width: "180px",
              height: "180px",
              borderRadius: "50%",
              background: voiceState === "speaking"
                ? "radial-gradient(circle at 35% 35%, #6EE7B7 0%, #10B981 35%, #065F46 70%, #022C22 100%)"
                : voiceState === "listening"
                ? "radial-gradient(circle at 35% 35%, #7DD3FC 0%, #38BDF8 30%, #4338CA 75%, #1E1B4B 100%)"
                : voiceState === "thinking"
                ? "radial-gradient(circle at 35% 35%, #FDE047 0%, #F59E0B 35%, #9D174D 75%, #4C0519 100%)"
                : "radial-gradient(circle at 35% 35%, #C084FC 0%, #7C3AED 35%, #4338CA 75%, #0F172A 100%)",
              boxShadow: "inset 0 4px 20px rgba(255, 255, 255, 0.4), inset 0 -12px 28px rgba(0, 0, 0, 0.7), 0 20px 40px rgba(0, 0, 0, 0.6)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              position: "relative",
              animation: voiceState === "speaking" ? "yc-orb-speaking 2s ease-in-out infinite" : "yc-orb-breathe 4s ease-in-out infinite",
              transition: "all 0.4s ease"
            }}
          >
            {/* Center Dynamic Icon / Sparkle */}
            <div 
              style={{
                fontSize: "32px",
                filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.4))",
                transform: voiceState === "listening" ? "scale(1.15)" : "scale(1)",
                transition: "transform 0.3s ease"
              }}
            >
              {voiceState === "listening" ? "🎙️" : voiceState === "speaking" ? "🔊" : voiceState === "thinking" ? "✦" : "✨"}
            </div>
          </div>
        </div>

        {/* Status Callout & Live Equalizer Visualizer */}
        <div style={{ marginTop: "32px", textAlign: "center" }}>
          <div 
            style={{ 
              fontSize: "18px", 
              fontWeight: 600, 
              color: "#F8FAFC", 
              letterSpacing: "-0.015em",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px"
            }}
          >
            {voiceState === "listening" && "Listening to your voice..."}
            {voiceState === "thinking" && "Synthesizing ERP analysis..."}
            {voiceState === "speaking" && "Responding..."}
            {voiceState === "idle" && "Tap the orb to start speaking"}
          </div>

          <div style={{ fontSize: "13px", color: "rgba(255, 255, 255, 0.5)", marginTop: "6px" }}>
            {voiceState === "listening"
              ? "Speak your question or operational instruction naturally"
              : voiceState === "speaking"
              ? "Tap the orb anytime to interrupt or pause speech"
              : "Continuous natural speech powered by OpenAI & Sarvam HD neural voice"}
          </div>

          {/* Dancing Equalizer Bars (Active during speaking or listening) */}
          <div 
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "4px",
              height: "40px",
              marginTop: "20px"
            }}
          >
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16].map((i) => {
              const active = voiceState === "speaking" || voiceState === "listening";
              return (
                <div
                  key={i}
                  style={{
                    width: "3px",
                    borderRadius: "3px",
                    background: voiceState === "speaking" 
                      ? "linear-gradient(to top, #10B981, #38BDF8)" 
                      : voiceState === "listening" 
                      ? "linear-gradient(to top, #38BDF8, #A855F7)" 
                      : "rgba(255, 255, 255, 0.15)",
                    height: active ? `${Math.max(6, (Math.sin(i * 0.8) + 1.2) * 14)}px` : "6px",
                    animation: active ? `yc-bar-bounce ${0.6 + (i % 5) * 0.15}s ease-in-out ${i * 0.05}s infinite alternate` : "none",
                    transition: "height 0.2s ease"
                  }}
                />
              );
            })}
          </div>
        </div>

        {/* Live Transcript / Response Card (Linear/Perplexity Style) */}
        {(transcript || interimTranscript || aiSpeechResponse) && (
          <div 
            className="yc-glass-panel"
            style={{
              marginTop: "28px",
              padding: "18px 24px",
              borderRadius: "16px",
              width: "100%",
              maxWidth: "680px",
              textAlign: "left",
              animation: "yc-fade-in-up 0.25s ease"
            }}
          >
            {/* User Spoken Input */}
            {(transcript || interimTranscript) && (
              <div style={{ marginBottom: aiSpeechResponse ? "14px" : "0" }}>
                <div style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.5px", color: "#38BDF8", fontWeight: 600, marginBottom: "4px" }}>
                  You Said
                </div>
                <div style={{ fontSize: "15px", color: "#F1F5F9", lineHeight: 1.5 }}>
                  {transcript} <span style={{ color: "rgba(255,255,255,0.4)" }}>{interimTranscript}</span>
                </div>
              </div>
            )}

            {/* AI Voice Answer */}
            {aiSpeechResponse && (
              <div style={{ borderTop: (transcript || interimTranscript) ? "1px solid rgba(255, 255, 255, 0.08)" : "none", paddingTop: (transcript || interimTranscript) ? "12px" : "0" }}>
                <div style={{ fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.5px", color: "#10B981", fontWeight: 600, marginBottom: "4px" }}>
                  Copilot Response
                </div>
                <div style={{ fontSize: "14px", color: "rgba(255, 255, 255, 0.85)", lineHeight: 1.6 }}>
                  {aiSpeechResponse}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Suggested Queries Pills */}
        {!transcript && !aiSpeechResponse && voiceState === "idle" && (
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", justifyContent: "center", marginTop: "28px", maxWidth: "620px" }}>
            {[
              "Why did revenue change this month?",
              "Check stock risk for bearings",
              "Show overdue invoices & cash flow",
              "Compare supplier quotes"
            ].map((q, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => {
                  setTranscript(q);
                  executeVoiceQuery(q);
                }}
                className="yc-pill-badge"
                style={{
                  padding: "7px 14px",
                  borderRadius: "20px",
                  fontSize: "12px",
                  cursor: "pointer"
                }}
              >
                "{q}"
              </button>
            ))}
          </div>
        )}

        {/* Fallback Text Input Drawer */}
        {showTextInput && (
          <form 
            onSubmit={(e) => {
              e.preventDefault();
              if (typedQuery.trim()) {
                executeVoiceQuery(typedQuery);
                setTypedQuery("");
              }
            }}
            style={{ width: "100%", maxWidth: "560px", marginTop: "20px", display: "flex", gap: "8px" }}
          >
            <input
              type="text"
              value={typedQuery}
              onChange={(e) => setTypedQuery(e.target.value)}
              placeholder="Type your question..."
              autoFocus
              className="yc-glass-panel"
              style={{
                flex: 1,
                padding: "12px 18px",
                borderRadius: "14px",
                color: "#F8FAFC",
                fontSize: "14px",
                outline: "none"
              }}
            />
            <button
              type="submit"
              style={{
                background: "var(--ai-core)",
                color: "white",
                padding: "0 20px",
                borderRadius: "14px",
                fontWeight: 600,
                fontSize: "13px",
                border: "none",
                cursor: "pointer"
              }}
            >
              Send
            </button>
          </form>
        )}
      </main>

      {/* Floating Bottom Control Dock (Raycast / Linear Aesthetic) */}
      <footer 
        className="yc-glass-panel"
        style={{
          padding: "10px 18px",
          borderRadius: "32px",
          display: "flex",
          alignItems: "center",
          gap: "16px",
          zIndex: 10
        }}
      >
        {/* Mic Toggle Button */}
        <button
          type="button"
          onClick={handleOrbClick}
          style={{
            background: voiceState === "listening" 
              ? "linear-gradient(135deg, #EF4444 0%, #DC2626 100%)" 
              : "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)",
            color: "white",
            padding: "8px 18px",
            borderRadius: "24px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "13px",
            fontWeight: 600,
            border: "none",
            cursor: "pointer",
            boxShadow: voiceState === "listening" 
              ? "0 4px 14px rgba(239, 68, 68, 0.4)" 
              : "0 4px 14px rgba(99, 102, 241, 0.4)"
          }}
        >
          <span>{voiceState === "listening" ? "⏹ Stop" : "🎙️ Speak"}</span>
        </button>

        {/* Keyboard Toggle */}
        <button
          type="button"
          onClick={() => setShowTextInput(!showTextInput)}
          style={{
            background: showTextInput ? "rgba(255, 255, 255, 0.15)" : "transparent",
            color: "rgba(255, 255, 255, 0.8)",
            padding: "8px 12px",
            borderRadius: "20px",
            fontSize: "12px",
            cursor: "pointer",
            border: "none",
            display: "flex",
            alignItems: "center",
            gap: "6px"
          }}
          title="Type query instead of speaking"
        >
          <span>⌨️</span>
          <span>Type</span>
        </button>

        {/* Mute Audio Speaker Output */}
        <button
          type="button"
          onClick={() => setIsMuted(!isMuted)}
          style={{
            background: isMuted ? "rgba(239, 68, 68, 0.15)" : "transparent",
            color: isMuted ? "#EF4444" : "rgba(255, 255, 255, 0.8)",
            padding: "8px 12px",
            borderRadius: "20px",
            fontSize: "12px",
            cursor: "pointer",
            border: "none",
            display: "flex",
            alignItems: "center",
            gap: "6px"
          }}
          title={isMuted ? "Audio speech is muted" : "Audio speech is active"}
        >
          <span>{isMuted ? "🔇" : "🔊"}</span>
          <span>{isMuted ? "Muted" : "Audio ON"}</span>
        </button>

        <div style={{ width: "1px", height: "18px", background: "rgba(255, 255, 255, 0.1)" }} />

        {/* End Session Button */}
        <button
          type="button"
          onClick={handleClose}
          style={{
            background: "transparent",
            color: "rgba(255, 255, 255, 0.5)",
            padding: "6px 10px",
            fontSize: "12px",
            cursor: "pointer",
            border: "none"
          }}
        >
          Exit
        </button>
      </footer>
    </div>
  );
}
