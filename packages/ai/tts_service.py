"""
Enterprise Text-to-Speech (TTS) Service.

Supports:
- High-fidelity Microsoft Neural Voices (Zero-token cost, natural inflection)
- OpenAI Audio Speech (tts-1, tts-1-hd with alloy, echo, onyx, shimmer, fable, nova)
- Zero-Trust PCI-DSS & PII scrubbing before audio vocalization
- Real-time chunked streaming for sub-second first-byte latency
- Offline synthetic fallback for high-availability reliability
"""

import io
import struct
import math
from typing import AsyncIterator, Dict, Any, List, Optional
import structlog

from packages.config.settings import settings
from packages.security.guardrails import guardrails

logger = structlog.get_logger("ai.tts_service")

# Supported Neural & Enterprise Voice Catalog
VOICE_CATALOG = [
    {
        "id": "en-US-AriaNeural",
        "name": "Aria (US Neural - Professional)",
        "gender": "Female",
        "language": "en-US",
        "provider": "edge",
        "recommended_for": "Executive ERP Assistant & Finance"
    },
    {
        "id": "en-US-GuyNeural",
        "name": "Guy (US Neural - Conversational)",
        "gender": "Male",
        "language": "en-US",
        "provider": "edge",
        "recommended_for": "Operations & Logistics"
    },
    {
        "id": "en-US-JennyNeural",
        "name": "Jenny (US Neural - Friendly)",
        "gender": "Female",
        "language": "en-US",
        "provider": "edge",
        "recommended_for": "Customer Success & HR"
    },
    {
        "id": "en-GB-SoniaNeural",
        "name": "Sonia (UK Neural - Formal)",
        "gender": "Female",
        "language": "en-GB",
        "provider": "edge",
        "recommended_for": "Legal & Audit Compliance"
    },
    {
        "id": "en-AU-NatashaNeural",
        "name": "Natasha (AU Neural - Dynamic)",
        "gender": "Female",
        "language": "en-AU",
        "provider": "edge",
        "recommended_for": "Sales & CRM"
    },
    {
        "id": "alloy",
        "name": "Alloy (OpenAI Balanced)",
        "gender": "Neutral",
        "language": "en-US",
        "provider": "openai",
        "recommended_for": "Versatile Multi-Agent Dispatch"
    },
    {
        "id": "echo",
        "name": "Echo (OpenAI Warm)",
        "gender": "Male",
        "language": "en-US",
        "provider": "openai",
        "recommended_for": "Procurement & Warehouse"
    },
    {
        "id": "shimmer",
        "name": "Shimmer (OpenAI Clear)",
        "gender": "Female",
        "language": "en-US",
        "provider": "openai",
        "recommended_for": "General Command Center"
    },
    # Indian Indic & Sarvam AI Voices (Bulbul Model Family)
    {
        "id": "en-IN-NeerjaNeural",
        "name": "Neerja (Indian English - Professional)",
        "gender": "Female",
        "language": "en-IN",
        "provider": "edge",
        "recommended_for": "India ERP Finance & Operations"
    },
    {
        "id": "en-IN-PrabhatNeural",
        "name": "Prabhat (Indian English - Dynamic)",
        "gender": "Male",
        "language": "en-IN",
        "provider": "edge",
        "recommended_for": "India Sales & Procurement"
    },
    {
        "id": "hi-IN-SwaraNeural",
        "name": "Swara (Hindi Neural - Natural)",
        "gender": "Female",
        "language": "hi-IN",
        "provider": "edge",
        "recommended_for": "Hindi Business Operations"
    },
    {
        "id": "sarvam-bulbul-meera",
        "name": "Meera (Sarvam AI Bulbul - Hindi/English)",
        "gender": "Female",
        "language": "hi-IN",
        "provider": "sarvam",
        "recommended_for": "Sarvam Indic Conversational Agent"
    },
    {
        "id": "sarvam-bulbul-shubh",
        "name": "Shubh (Sarvam AI Bulbul - Hindi/English)",
        "gender": "Male",
        "language": "hi-IN",
        "provider": "sarvam",
        "recommended_for": "Sarvam Indic Operations Assistant"
    },
    {
        "id": "sarvam-bulbul-priya",
        "name": "Priya (Sarvam AI Bulbul - Tamil/English)",
        "gender": "Female",
        "language": "ta-IN",
        "provider": "sarvam",
        "recommended_for": "Sarvam Tamil Regional Copilot"
    },
    {
        "id": "sarvam-bulbul-aravind",
        "name": "Aravind (Sarvam AI Bulbul - Telugu/English)",
        "gender": "Male",
        "language": "te-IN",
        "provider": "sarvam",
        "recommended_for": "Sarvam Telugu Regional Copilot"
    }
]

OPENAI_VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
SARVAM_VOICE_MAP = {
    "sarvam-bulbul-meera": {"speaker": "meera", "lang": "hi-IN", "fallback_edge": "hi-IN-SwaraNeural"},
    "sarvam-bulbul-shubh": {"speaker": "shubh", "lang": "hi-IN", "fallback_edge": "en-IN-PrabhatNeural"},
    "sarvam-bulbul-priya": {"speaker": "priya", "lang": "ta-IN", "fallback_edge": "ta-IN-PallaviNeural"},
    "sarvam-bulbul-aravind": {"speaker": "arvind", "lang": "te-IN", "fallback_edge": "en-IN-PrabhatNeural"},
}


class TTSService:
    """Enterprise Text-to-Speech Engine with PCI-DSS Scrubbing and Multi-Provider Fallbacks."""

    def __init__(self):
        self.default_voice = getattr(settings, "tts_default_voice", "en-US-AriaNeural")

    def list_voices(self) -> List[Dict[str, Any]]:
        """Returns the list of available enterprise voices."""
        return VOICE_CATALOG

    def sanitize_text(self, text: str) -> str:
        """
        Enforces PCI-DSS and privacy safety by redacting card numbers,
        passwords, and CVVs before they can be spoken.
        """
        if not text:
            return ""
        # Redact payment card numbers, CVVs, passwords
        clean = guardrails.sanitize_pci_data(text)
        # Strip code blocks and markdown symbols for cleaner vocal delivery
        clean = clean.replace("```", "").replace("**", "").replace("*", "")
        return clean.strip()

    def _generate_synthetic_tone(self, duration_sec: float = 0.5) -> bytes:
        """Generates a clean synthetic PCM WAV audio buffer as guaranteed fallback."""
        sample_rate = 16000
        num_samples = int(sample_rate * duration_sec)
        raw_pcm = bytearray()
        for i in range(num_samples):
            val = int(32767.0 * 0.1 * math.sin(2.0 * math.pi * 440.0 * (i / sample_rate)))
            raw_pcm.extend(struct.pack("<h", val))

        buf = io.BytesIO()
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + len(raw_pcm)))
        buf.write(b"WAVEfmt ")
        buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
        buf.write(b"data")
        buf.write(struct.pack("<I", len(raw_pcm)))
        buf.write(raw_pcm)
        return buf.getvalue()

    async def stream_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: str = "+0%",
        pitch: str = "+0Hz"
    ) -> AsyncIterator[bytes]:
        """
        Streams synthesized audio chunks with sub-second time-to-first-byte.
        """
        clean_text = self.sanitize_text(text)
        if not clean_text:
            yield b""
            return

        selected_voice = voice or self.default_voice
        emitted_any = False

        # Provider 1: Sarvam AI (Bulbul Indic Neural TTS)
        sarvam_key = getattr(settings, "sarvam_api_key", None)
        if (selected_voice in SARVAM_VOICE_MAP or selected_voice.startswith("sarvam-")) and sarvam_key:
            try:
                import httpx
                import base64
                sarvam_cfg = SARVAM_VOICE_MAP.get(selected_voice, {"speaker": "meera", "lang": "hi-IN"})
                payload = {
                    "inputs": [clean_text],
                    "target_language_code": sarvam_cfg["lang"],
                    "speaker": sarvam_cfg["speaker"],
                    "model": "bulbul:v1"
                }
                headers = {
                    "api-subscription-key": sarvam_key,
                    "Content-Type": "application/json"
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post("https://api.sarvam.ai/text-to-speech", json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        audios = data.get("audios", [])
                        if audios and isinstance(audios, list):
                            audio_bytes = base64.b64decode(audios[0])
                            # Stream in 4KB chunks
                            chunk_size = 4096
                            for i in range(0, len(audio_bytes), chunk_size):
                                emitted_any = True
                                yield audio_bytes[i:i + chunk_size]
                            return
            except Exception as exc:
                logger.warning("sarvam_tts_failed_fallback_to_edge", error=str(exc))

        # Provider 2: OpenAI Audio Speech (ChatGPT-grade neural voice model)
        openai_key = getattr(settings, "openai_api_key", "")
        tts_provider = getattr(settings, "tts_provider", "edge")
        should_use_openai = (selected_voice in OPENAI_VOICES or tts_provider == "openai") and bool(openai_key and openai_key.startswith("sk-"))
        if should_use_openai:
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=openai_key)
                openai_voice = selected_voice if selected_voice in OPENAI_VOICES else "alloy"
                openai_model = getattr(settings, "tts_model", "tts-1-hd")
                response = await client.audio.speech.create(
                    model=openai_model,
                    voice=openai_voice,
                    input=clean_text,
                    response_format="mp3"
                )
                async for chunk in response.iter_bytes(chunk_size=4096):
                    if chunk:
                        emitted_any = True
                        yield chunk
                return
            except Exception as exc:
                logger.warning("openai_tts_failed_fallback_to_edge", error=str(exc))

        # Provider 3: Microsoft Neural Edge-TTS (Default, Free, Natural, Fast)
        try:
            import edge_tts
            if selected_voice in SARVAM_VOICE_MAP:
                edge_voice = SARVAM_VOICE_MAP[selected_voice].get("fallback_edge", "en-IN-NeerjaNeural")
            elif selected_voice in OPENAI_VOICES:
                edge_voice = "en-US-AriaNeural"
            else:
                edge_voice = selected_voice

            communicate = edge_tts.Communicate(
                text=clean_text,
                voice=edge_voice,
                rate=rate,
                pitch=pitch
            )
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio" and chunk.get("data"):
                    emitted_any = True
                    yield chunk["data"]
        except Exception as exc:
            logger.warning("edge_tts_stream_failed", error=str(exc))

        # Provider 3: Guaranteed Synthetic Fallback
        if not emitted_any:
            logger.info("using_synthetic_audio_fallback")
            yield self._generate_synthetic_tone(duration_sec=0.5)

    async def synthesize_to_bytes(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: str = "+0%",
        pitch: str = "+0Hz"
    ) -> bytes:
        """Accumulates all audio chunks into a single audio/mpeg or audio/wav bytes object."""
        buffer = bytearray()
        async for chunk in self.stream_speech(text=text, voice=voice, rate=rate, pitch=pitch):
            buffer.extend(chunk)
        return bytes(buffer)


# Global singleton instance
tts_service = TTSService()
