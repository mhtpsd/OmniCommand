"""
integrations/gemini_client.py
--------------------------------
Now calls the local ADK agent server (triage-agent/) instead of the
Gemini API directly -- this is what makes the hazard triage feature
count as genuine Gemini Enterprise Agent Platform usage.
"""

import base64
import json
import uuid

import httpx

from models.schemas import TriageResponse

ADK_BASE_URL = "http://localhost:8001"   # the triage-agent api_server
ADK_APP_NAME = "flood_triage_agent"      # must match the folder name


def analyze_flood_photo(image_bytes: bytes, mime_type: str = "image/jpeg") -> TriageResponse:
    user_id = "dashboard"
    session_id = str(uuid.uuid4())

    try:
        # 1. Create a session for this request.
        httpx.post(
            f"{ADK_BASE_URL}/apps/{ADK_APP_NAME}/users/{user_id}/sessions/{session_id}",
            json={},
            timeout=10,
        ).raise_for_status()

        # 2. Send the image + prompt to the agent.
        response = httpx.post(
            f"{ADK_BASE_URL}/run",
            json={
                "appName": ADK_APP_NAME,
                "userId": user_id,
                "sessionId": session_id,
                "newMessage": {
                    "role": "user",
                    "parts": [
                        {"inline_data": {
                            "mime_type": mime_type,
                            "data": base64.b64encode(image_bytes).decode(),
                        }},
                        {"text": "Analyze this hazard photo."},
                    ],
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        events = response.json()

        # 3. Extract the agent's final text reply from the event list.
        reply_text = _extract_final_text(events)

        cleaned = reply_text.strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        return TriageResponse(**parsed)

    except Exception as exc:
        print(f"[gemini_client] ADK agent failed, returning fallback: {exc}")
        # Never let a failed AI call crash the request -- degrade gracefully.
        return TriageResponse(
            hazard_type="unknown",
            confidence="low",
            recommendation="Unable to auto-analyze -- flag for manual review",
        )


def _extract_final_text(events: list) -> str:
    """
    Iterate `events` (a list of ADK event dicts) and find the last
    one with a text part in its content.
    """
    for event in reversed(events):
        for part in event.get("content", {}).get("parts", []):
            if "text" in part:
                return part["text"]
    raise ValueError("No text reply found in agent response")
