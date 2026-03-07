import os
from typing import Optional

from elevenlabs.client import AsyncElevenLabs  # type: ignore[import-not-found]
from fastapi import HTTPException, status


def _get_required_env(name: str) -> str:
    """Return a required environment variable or raise a 500 error."""
    value = os.getenv(name)
    if not value:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{name} is not configured on the server.",
        )
    return value


def get_elevenlabs_client() -> AsyncElevenLabs:
    """
    Construct an AsyncElevenLabs client using the server-side API key.
    Keeping this on the backend avoids exposing the key to the browser.
    """
    api_key = _get_required_env("ELEVENLABS_API_KEY")
    return AsyncElevenLabs(api_key=api_key)


async def create_voice_session_internal(agent_id_env: str = "AGENT_ID") -> dict:
    """
    Internal helper used by the FastAPI router to create a short-lived
    ElevenLabs conversational session and return connection details.
    """
    agent_id = _get_required_env(agent_id_env)
    client = get_elevenlabs_client()

    # For private agents, ElevenLabs requires a WebRTC token.
    token_response = await client.conversational_ai.conversations.get_webrtc_token(
        agent_id=agent_id,
    )

    token: Optional[str] = getattr(token_response, "token", None)
    if token is None and isinstance(token_response, dict):
        token = token_response.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to obtain a WebRTC token from ElevenLabs.",
        )

    return {
        "agent_id": agent_id,
        "webrtc_token": token,
        "connection_type": "webrtc",
    }

