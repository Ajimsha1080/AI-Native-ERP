"""
Text-to-Speech (TTS) API routes.
Streams real-time neural voice audio for ERP agent reasoning and conversational outputs.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from packages.ai.tts_service import tts_service, VOICE_CATALOG
from packages.auth.dependencies import OptionalCurrentUser

router = APIRouter(prefix="/tts", tags=["Text-to-Speech (TTS)"])


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Text to synthesize into speech")
    voice: Optional[str] = Field(None, description="Voice ID e.g. en-US-AriaNeural, alloy")
    rate: Optional[str] = Field("+0%", description="Speech speed adjustment e.g. +10%, -10%")
    pitch: Optional[str] = Field("+0Hz", description="Speech pitch adjustment e.g. +5Hz, -5Hz")


@router.get("/voices")
async def list_voices():
    """Returns available enterprise neural and OpenAI voice models."""
    return {
        "status": "success",
        "default_voice": tts_service.default_voice,
        "voices": tts_service.list_voices(),
    }


@router.get("/speak")
async def speak_get(
    text: str = Query(..., min_length=1, max_length=5000, description="Text to speak"),
    voice: Optional[str] = Query(None, description="Voice identifier"),
    rate: Optional[str] = Query("+0%", description="Speed adjustment"),
    current_user: OptionalCurrentUser = None,
):
    """
    Synthesizes and streams audio/mpeg speech from query parameters.
    Suitable for direct audio HTML <audio src="..."> tags.
    """
    clean_text = tts_service.sanitize_text(text)
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided text does not contain vocalizable content."
        )

    return StreamingResponse(
        tts_service.stream_speech(text=clean_text, voice=voice, rate=rate or "+0%"),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=speech.mp3",
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        }
    )


@router.post("/speak")
async def speak_post(
    req: TTSRequest,
    current_user: OptionalCurrentUser = None,
):
    """
    Synthesizes and streams audio/mpeg speech from JSON payload.
    """
    clean_text = tts_service.sanitize_text(req.text)
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provided text does not contain vocalizable content."
        )

    return StreamingResponse(
        tts_service.stream_speech(text=clean_text, voice=req.voice, rate=req.rate or "+0%", pitch=req.pitch or "+0Hz"),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=speech.mp3",
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff",
        }
    )
