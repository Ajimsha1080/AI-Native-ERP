"use client";

import React, { useState, useEffect, useRef } from "react";
import { apiClient } from "../lib/api-client";

interface VoiceOption {
  id: string;
  name: string;
  category: string;
}

const VOICES: VoiceOption[] = [
  { id: "en-US-AriaNeural", name: "Aria (Professional US)", category: "Neural" },
  { id: "en-US-GuyNeural", name: "Guy (Conversational US)", category: "Neural" },
  { id: "en-US-JennyNeural", name: "Jenny (Warm & Natural)", category: "Neural" },
  { id: "en-IN-NeerjaNeural", name: "Neerja (Indian English)", category: "Indic" },
  { id: "en-IN-PrabhatNeural", name: "Prabhat (Indian English)", category: "Indic" },
  { id: "hi-IN-SwaraNeural", name: "Swara (Hindi Neural)", category: "Indic" },
  { id: "sarvam-bulbul-meera", name: "Meera (Sarvam Bulbul)", category: "Sarvam AI" },
  { id: "sarvam-bulbul-shubh", name: "Shubh (Sarvam Bulbul)", category: "Sarvam AI" },
  { id: "alloy", name: "Alloy (OpenAI Standard)", category: "OpenAI" },
  { id: "echo", name: "Echo (OpenAI Warm)", category: "OpenAI" },
  { id: "shimmer", name: "Shimmer (OpenAI Expressive)", category: "OpenAI" },
];

interface ChatGPTVoiceModeProps {
  isOpen: boolean;
  onClose: () => void;
  onTranscriptReceived?: (text: string) => void;
}

export default function ChatGPTVoiceMode({ isOpen, onClose, onTranscriptReceived }: ChatGPTVoiceModeProps) {
  const [status, setStatus] = useState<"idle" | "listening" | "thinking" | "speaking">("idle");
  const [userSpeech, setUserSpeech] = useState<string>("");
  const [aiSpeech, setAiSpeech] = useState<string>("");
  const [selectedVoice, setSelectedVoice] = useState<string>("en-US-AriaNeural");
  const [handsFree, setHandsFree] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string>("");

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const recognitionRef = useRef<any>(null);
  const silenceTimerRef = useRef<any>(null);
  const statusRef = useRef(status);
  statusRef.current = status;

  // Clean up audio & speech when closing
  useEffect(() => {
    if (!isOpen) {
      stopAudio();
      stopListening();
      setStatus("idle");
      setUserSpeech("");
      setAiSpeech("");
      setErrorMsg("");
    } else {
      // Auto-start listening when voice mode opens
      const timer = setTimeout(() => {
        startListening();
      }, 400);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
  };

  const stopListening = () => {
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
    }
  };

  const startListening = () => {
    stopAudio();
    stopListening();
    setErrorMsg("");
    setUserSpeech("");

    const SpeechRecognition = typeof window !== "undefined"
      ? ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)
      : null;

    if (!SpeechRecognition) {
      setErrorMsg("Voice mode requires Google Chrome or Microsoft Edge browser.");
      setStatus("idle");
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;
      recognition.lang = "en-US";
      recognition.interimResults = true;
      recognition.continuous = true;

      setStatus("listening");

      recognition.onstart = () => {
        setStatus("listening");
      };

      recognition.onresult = (event: any) => {
        let currentTranscript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          currentTranscript += event.results[i][0].transcript;
        }

        if (currentTranscript.trim()) {
          setUserSpeech(currentTranscript);

          // Reset silence debounce timer: 1.4s of silence auto-submits query
          if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = setTimeout(() => {
            stopListening();
            submitVoiceQuery(currentTranscript.trim());
          }, 1400);
        }
      };

      recognition.onerror = (event: any) => {
        console.warn("Speech recognition error:", event.error);
        if (event.error === "not-allowed" || event.error === "permission-denied") {
          setErrorMsg("Microphone permission blocked. Please allow microphone in browser URL bar.");
          setStatus("idle");
        } else if (event.error === "no-speech") {
          // If idle with no speech, continue listening
          if (statusRef.current === "listening") {
            // Keep alive
          }
        }
      };

      recognition.onend = () => {
        if (statusRef.current === "listening" && !userSpeech) {
          // Restart if still in listening state and no query submitted
          try {
            recognition.start();
          } catch {
            setStatus("idle");
          }
        }
      };

      recognition.start();
    } catch (err: any) {
      console.error("Failed to start speech recognition:", err);
      setErrorMsg("Could not access microphone.");
      setStatus("idle");
    }
  };

  const submitVoiceQuery = async (queryText: string) => {
    if (!queryText.trim()) {
      setStatus("listening");
      return;
    }

    if (onTranscriptReceived) {
      onTranscriptReceived(queryText);
    }

    setStatus("thinking");

    try {
      // Send query to ERP AI reasoning engine
      const res = await apiClient.post("/api/v1/dashboard/command", { query: queryText });
      const answer = res.summary || res.recommendation || "Task analyzed and completed successfully.";
      setAiSpeech(answer);

      // Play ChatGPT-level TTS audio
      await playNeuralVoice(answer);
    } catch (err) {
      console.error("AI response error:", err);
      const fallbackMsg = "I processed your request, but could not retrieve live ledgers. Please check your connection.";
      setAiSpeech(fallbackMsg);
      await playNeuralVoice(fallbackMsg);
    }
  };

  const playNeuralVoice = async (text: string) => {
    stopAudio();
    setStatus("speaking");

    // Sanitize and clean for natural speech
    const clean = text.replace(/\[\^[0-9]+\]/g, "").slice(0, 600);
    const audioUrl = `/api/v1/tts/speak?text=${encodeURIComponent(clean)}&voice=${encodeURIComponent(selectedVoice)}`;

    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    audio.onended = () => {
      setStatus("idle");
      // If hands-free is enabled, seamlessly loop back to listening for next sentence!
      if (handsFree) {
        setTimeout(() => {
          startListening();
        }, 500);
      }
    };

    audio.onerror = () => {
      setStatus("idle");
      if (handsFree) {
        setTimeout(() => {
          startListening();
        }, 800);
      }
    };

    try {
      await audio.play();
    } catch (playErr) {
      console.warn("Audio playback interrupted or blocked:", playErr);
      setStatus("idle");
    }
  };

  // User taps the glowing orb to interrupt / speak
  const handleOrbClick = () => {
    if (status === "speaking") {
      stopAudio();
      startListening();
    } else if (status === "listening") {
      if (userSpeech.trim()) {
        stopListening();
        submitVoiceQuery(userSpeech.trim());
      } else {
        stopListening();
        setStatus("idle");
      }
    } else if (status === "thinking") {
      // Do nothing while AI is reasoning
    } else {
      startListening();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100000,
        background: "radial-gradient(circle at center, #0f172a 0%, #020617 100%)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "32px 24px",
        color: "#ffffff",
        backdropFilter: "blur(20px)",
        animation: "fadeIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      {/* Top Header Bar */}
      <div
        style={{
          width: "100%",
          maxWidth: "800px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width: "12px",
              height: "12px",
              borderRadius: "50%",
              background: status === "listening" ? "#ef4444" : status === "speaking" ? "#10b981" : status === "thinking" ? "#a855f7" : "#64748b",
              boxShadow: status !== "idle" ? `0 0 16px ${status === "listening" ? "#ef4444" : status === "speaking" ? "#10b981" : "#a855f7"}` : "none",
              transition: "all 0.3s ease",
            }}
          />
          <span style={{ fontSize: "14px", fontWeight: 600, letterSpacing: "0.5px" }}>
            ChatGPT Advanced Voice Mode
          </span>
        </div>

        {/* Voice Selector & Close Button */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <select
            value={selectedVoice}
            onChange={(e) => {
              setSelectedVoice(e.target.value);
              stopAudio();
            }}
            style={{
              background: "rgba(255, 255, 255, 0.08)",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              color: "#f8fafc",
              borderRadius: "20px",
              padding: "6px 14px",
              fontSize: "12px",
              outline: "none",
              cursor: "pointer",
            }}
          >
            {VOICES.map((v) => (
              <option key={v.id} value={v.id} style={{ background: "#0f172a", color: "#fff" }}>
                {v.name} ({v.category})
              </option>
            ))}
          </select>

          <button
            onClick={() => setHandsFree(!handsFree)}
            style={{
              background: handsFree ? "rgba(99, 102, 241, 0.25)" : "rgba(255, 255, 255, 0.08)",
              border: `1px solid ${handsFree ? "#6366f1" : "rgba(255, 255, 255, 0.15)"}`,
              color: handsFree ? "#818cf8" : "#94a3b8",
              borderRadius: "20px",
              padding: "6px 12px",
              fontSize: "12px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
            title="Auto-listen after speaking"
          >
            <span>🔄</span> Hands-Free: {handsFree ? "ON" : "OFF"}
          </button>

          <button
            onClick={onClose}
            style={{
              background: "rgba(255, 255, 255, 0.1)",
              border: "none",
              color: "#cbd5e1",
              borderRadius: "50%",
              width: "36px",
              height: "36px",
              cursor: "pointer",
              fontSize: "16px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "background 0.2s",
            }}
            title="Exit Voice Mode"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Main Center Stage: Animated Organic Soundwave Orb */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          flex: 1,
          width: "100%",
          maxWidth: "600px",
          gap: "36px",
        }}
      >
        {/* Interactive Glowing Fluid Audio Orb */}
        <div
          onClick={handleOrbClick}
          style={{
            position: "relative",
            width: "220px",
            height: "220px",
            borderRadius: "50%",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "transform 0.3s ease",
            transform: status === "speaking" ? "scale(1.08)" : status === "listening" ? "scale(1.04)" : "scale(1)",
          }}
          title={status === "speaking" ? "Tap to interrupt & speak" : status === "listening" ? "Tap to submit" : "Tap to speak"}
        >
          {/* Outer Ripple Rings */}
          <div
            style={{
              position: "absolute",
              inset: status === "speaking" ? "-30px" : status === "listening" ? "-20px" : "-10px",
              borderRadius: "50%",
              background: status === "speaking"
                ? "radial-gradient(circle, rgba(16, 185, 129, 0.25) 0%, transparent 70%)"
                : status === "listening"
                ? "radial-gradient(circle, rgba(239, 68, 68, 0.25) 0%, transparent 70%)"
                : status === "thinking"
                ? "radial-gradient(circle, rgba(168, 85, 247, 0.25) 0%, transparent 70%)"
                : "radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%)",
              filter: "blur(14px)",
              animation: status !== "idle" ? "pulseGlow 2s infinite ease-in-out" : "none",
              transition: "all 0.5s ease",
            }}
          />

          {/* Main Core Orb */}
          <div
            style={{
              width: "180px",
              height: "180px",
              borderRadius: "50%",
              background: status === "speaking"
                ? "linear-gradient(135deg, #10b981 0%, #065f46 50%, #047857 100%)"
                : status === "listening"
                ? "linear-gradient(135deg, #ef4444 0%, #991b1b 50%, #7f1d1d 100%)"
                : status === "thinking"
                ? "linear-gradient(135deg, #a855f7 0%, #6b21a8 50%, #581c87 100%)"
                : "linear-gradient(135deg, #6366f1 0%, #4338ca 50%, #312e81 100%)",
              boxShadow: status === "speaking"
                ? "0 0 50px rgba(16, 185, 129, 0.6), inset 0 0 20px rgba(255, 255, 255, 0.4)"
                : status === "listening"
                ? "0 0 50px rgba(239, 68, 68, 0.6), inset 0 0 20px rgba(255, 255, 255, 0.4)"
                : status === "thinking"
                ? "0 0 50px rgba(168, 85, 247, 0.6), inset 0 0 20px rgba(255, 255, 255, 0.4)"
                : "0 0 40px rgba(99, 102, 241, 0.4), inset 0 0 20px rgba(255, 255, 255, 0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              position: "relative",
              zIndex: 2,
              animation: status === "speaking" ? "floatSpeaking 1.8s infinite ease-in-out" : "floatIdle 3s infinite ease-in-out",
            }}
          >
            {/* Center Dynamic Icon / Waveform Bars */}
            {status === "speaking" ? (
              <div style={{ display: "flex", alignItems: "center", gap: "6px", height: "48px" }}>
                <span className="wave-bar wave-1" />
                <span className="wave-bar wave-2" />
                <span className="wave-bar wave-3" />
                <span className="wave-bar wave-4" />
                <span className="wave-bar wave-5" />
              </div>
            ) : status === "listening" ? (
              <div style={{ fontSize: "36px", filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.4))" }}>
                🎙️
              </div>
            ) : status === "thinking" ? (
              <div style={{ fontSize: "32px", animation: "spin 1.5s linear infinite" }}>
                ⚙️
              </div>
            ) : (
              <div style={{ fontSize: "32px", opacity: 0.9 }}>
                ✨
              </div>
            )}
          </div>
        </div>

        {/* Current State Indicator */}
        <div style={{ textAlign: "center" }}>
          <div
            style={{
              fontSize: "18px",
              fontWeight: 600,
              color: status === "speaking" ? "#34d399" : status === "listening" ? "#f87171" : status === "thinking" ? "#c084fc" : "#cbd5e1",
              marginBottom: "8px",
              letterSpacing: "0.5px",
            }}
          >
            {status === "speaking" && "AI is speaking... (Tap orb to interrupt)"}
            {status === "listening" && "Listening... (Speak your request)"}
            {status === "thinking" && "Reasoning over ERP ledgers..."}
            {status === "idle" && "Tap the orb to start speaking"}
          </div>

          {errorMsg && (
            <div style={{ color: "#f87171", fontSize: "13px", marginTop: "4px" }}>
              ⚠️ {errorMsg}
            </div>
          )}
        </div>

        {/* Real-Time Live Transcript Subtitle Box */}
        <div
          style={{
            width: "100%",
            minHeight: "80px",
            maxHeight: "140px",
            overflowY: "auto",
            background: "rgba(15, 23, 42, 0.6)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            borderRadius: "16px",
            padding: "16px 20px",
            fontSize: "14px",
            lineHeight: "1.6",
            color: "#e2e8f0",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
          }}
        >
          {status === "listening" && userSpeech && (
            <div>
              <span style={{ color: "#94a3b8", fontSize: "12px", display: "block", marginBottom: "4px" }}>You:</span>
              <span style={{ fontStyle: "italic" }}>"{userSpeech}"</span>
            </div>
          )}

          {status === "thinking" && (
            <span style={{ color: "#c084fc", fontStyle: "italic" }}>
              "{userSpeech || "Analyzing business request..."}"
            </span>
          )}

          {status === "speaking" && aiSpeech && (
            <div>
              <span style={{ color: "#34d399", fontSize: "12px", display: "block", marginBottom: "4px" }}>Copilot:</span>
              <span>{aiSpeech}</span>
            </div>
          )}

          {status === "idle" && !aiSpeech && !userSpeech && (
            <span style={{ color: "#64748b" }}>
              Try saying: "Why did revenue change this month?" or "Check stock for bearings"
            </span>
          )}
        </div>
      </div>

      {/* Bottom Control Bar */}
      <div
        style={{
          width: "100%",
          maxWidth: "400px",
          display: "flex",
          justifyContent: "center",
          gap: "16px",
        }}
      >
        <button
          onClick={handleOrbClick}
          style={{
            padding: "12px 28px",
            borderRadius: "28px",
            background: status === "speaking"
              ? "rgba(239, 68, 68, 0.2)"
              : "rgba(255, 255, 255, 0.1)",
            border: `1px solid ${status === "speaking" ? "#ef4444" : "rgba(255, 255, 255, 0.2)"}`,
            color: status === "speaking" ? "#f87171" : "#ffffff",
            fontSize: "14px",
            fontWeight: 600,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            transition: "all 0.2s ease",
          }}
        >
          {status === "speaking" ? "⏹️ Interrupt / Speak" : status === "listening" ? "🛑 Done Speaking" : "🎙️ Speak Now"}
        </button>

        <button
          onClick={onClose}
          style={{
            padding: "12px 24px",
            borderRadius: "28px",
            background: "transparent",
            border: "1px solid rgba(255, 255, 255, 0.2)",
            color: "#94a3b8",
            fontSize: "14px",
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          Close
        </button>
      </div>

      {/* CSS Animation Keyframes */}
      <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: scale(0.97); }
          to { opacity: 1; transform: scale(1); }
        }
        @keyframes pulseGlow {
          0%, 100% { transform: scale(1); opacity: 0.5; }
          50% { transform: scale(1.15); opacity: 0.9; }
        }
        @keyframes floatSpeaking {
          0%, 100% { transform: translateY(0px) rotate(0deg); }
          50% { transform: translateY(-8px) rotate(2deg); }
        }
        @keyframes floatIdle {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-4px); }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .wave-bar {
          display: inline-block;
          width: 5px;
          background: #ffffff;
          border-radius: 3px;
          animation: wave 1.2s infinite ease-in-out;
        }
        .wave-1 { height: 16px; animation-delay: 0.0s; }
        .wave-2 { height: 32px; animation-delay: 0.15s; }
        .wave-3 { height: 48px; animation-delay: 0.3s; }
        .wave-4 { height: 28px; animation-delay: 0.45s; }
        .wave-5 { height: 18px; animation-delay: 0.6s; }
        @keyframes wave {
          0%, 100% { transform: scaleY(0.4); opacity: 0.6; }
          50% { transform: scaleY(1.0); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
