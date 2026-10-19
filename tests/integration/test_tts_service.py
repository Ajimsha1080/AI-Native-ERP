"""
Integration tests for Enterprise Text-to-Speech (TTS) Service & Streaming API.

Tests:
- Voice catalog retrieval
- Zero-Trust PCI-DSS & credential sanitization before vocalization
- Real-time chunked audio streaming (Edge Neural & OpenAI)
- Guaranteed offline fallback tone generation
- HTTP REST API endpoints (/api/v1/tts/voices, /api/v1/tts/speak)
"""

import pytest
from httpx import AsyncClient, ASGITransport

from apps.api.main import app
from packages.ai.tts_service import tts_service, TTSService, VOICE_CATALOG


def test_tts_voice_catalog():
    """Verifies available voices include neural, OpenAI, and Sarvam AI options."""
    service = TTSService()
    voices = service.list_voices()
    assert len(voices) >= 8

    voice_ids = [v["id"] for v in voices]
    assert "en-US-AriaNeural" in voice_ids
    assert "en-US-GuyNeural" in voice_ids
    assert "alloy" in voice_ids
    assert "sarvam-bulbul-meera" in voice_ids
    assert "en-IN-NeerjaNeural" in voice_ids


@pytest.mark.asyncio
async def test_tts_sarvam_voice_fallback():
    """Verifies Sarvam AI voice generates valid audio (using mock/edge fallback)."""
    service = TTSService()
    chunks = []
    async for chunk in service.stream_speech(
        text="Your ERP transaction has completed successfully.",
        voice="sarvam-bulbul-meera"
    ):
        if chunk:
            chunks.append(chunk)

    total_bytes = sum(len(c) for c in chunks)
    assert len(chunks) > 0
    assert total_bytes > 200


def test_tts_text_sanitization_pci_dss():
    """Verifies credit cards, CVVs, and passwords are sanitized before vocalization."""
    service = TTSService()
    raw_prompt = "Order approved for card 4532-1234-5678-9010 with CVV 789 and password: SuperSecretPassword!"
    clean_text = service.sanitize_text(raw_prompt)

    # Must NOT contain raw card or security code
    assert "4532-1234-5678-9010" not in clean_text
    assert "789" not in clean_text
    assert "[CREDIT_CARD_REDACTED]" in clean_text
    assert "[CVV_REDACTED]" in clean_text
    assert "SuperSecretPassword" not in clean_text


@pytest.mark.asyncio
async def test_tts_stream_speech():
    """Verifies edge neural audio generation streams valid audio bytes."""
    service = TTSService()
    chunks = []
    async for chunk in service.stream_speech(text="Inventory stock levels are healthy.", voice="en-US-AriaNeural"):
        if chunk:
            chunks.append(chunk)

    total_bytes = sum(len(c) for c in chunks)
    assert len(chunks) > 0
    assert total_bytes > 500


def test_tts_synthetic_fallback_generator():
    """Verifies fallback synthetic generator produces valid PCM WAV audio headers."""
    service = TTSService()
    wav_bytes = service._generate_synthetic_tone(duration_sec=0.2)
    assert len(wav_bytes) > 44
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"


@pytest.mark.asyncio
async def test_tts_api_endpoints():
    """Tests GET /api/v1/tts/voices, GET /api/v1/tts/speak, and POST /api/v1/tts/speak."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Test GET /api/v1/tts/voices
        res_voices = await client.get("/api/v1/tts/voices")
        assert res_voices.status_code == 200
        voices_data = res_voices.json()
        assert voices_data["status"] == "success"
        assert len(voices_data["voices"]) >= 5

        # 2. Test GET /api/v1/tts/speak
        res_speak_get = await client.get("/api/v1/tts/speak?text=Hello+from+Agentic+ERP&voice=en-US-AriaNeural")
        assert res_speak_get.status_code == 200
        assert res_speak_get.headers["content-type"] == "audio/mpeg"
        assert len(res_speak_get.content) > 200

        # 3. Test POST /api/v1/tts/speak
        res_speak_post = await client.post(
            "/api/v1/tts/speak",
            json={
                "text": "Purchase order PO-2026-0042 has been created.",
                "voice": "en-US-AriaNeural",
                "rate": "+0%"
            }
        )
        assert res_speak_post.status_code == 200
        assert res_speak_post.headers["content-type"] == "audio/mpeg"
        assert len(res_speak_post.content) > 200

        # 4. Test validation error on empty input
        res_empty = await client.post("/api/v1/tts/speak", json={"text": ""})
        assert res_empty.status_code in [400, 422]
