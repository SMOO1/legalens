import os

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.voice.voice import create_voice_session_internal

router = APIRouter(prefix="/voice", tags=["voice"])


async def _verify_internal_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> None:
    """
    Lightweight guard so only trusted clients (e.g. your own frontend
    or hotword listener process) can start a voice session.
    """
    expected = os.getenv("VOICE_AGENT_API_KEY", "dev-voice-agent-key")
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


@router.post("/session")
async def create_voice_session(
    _: None = Depends(_verify_internal_api_key),
) -> dict:
    """
    Create a short-lived ElevenLabs conversational session and return
    connection details for the caller.

    Typical flow:
    - a hotword listener detects "Hey Assistant"
    - it calls this endpoint
    - the frontend then uses the returned data with the ElevenLabs
      Conversational AI SDK to open a WebRTC / WebSocket connection
      and run the actual audio conversation loop.
    """
    return await create_voice_session_internal()


