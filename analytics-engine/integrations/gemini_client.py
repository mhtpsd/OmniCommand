"""
integrations/gemini_client.py
--------------------------------
Calls the Gemini API directly via google-genai -- this works in production
(Railway) without needing the local ADK agent server. The ADK triage agent
(triage-agent/) uses the same model and instruction and is the reference
implementation for the Agent Platform rubric; this module is the production
path that the deployed backend actually calls.
"""

import base64
import json
from functools import lru_cache

from google import genai
from google.genai import types

from config import settings
from models.schemas import TriageResponse

# Same instruction used in triage-agent/flood_triage_agent/agent.py
_TRIAGE_PROMPT = """You are an urban hazard triage assistant supporting an
emergency response dashboard. Given a photo of a possible hazard
(flooding, downed power line, road blockage, or other), identify the
hazard type. If flooding, estimate water depth in meters using visible
reference objects (car doors, curbs, people) as scale. Give a
one-sentence recommendation for a human dispatcher to review -- phrase
it as a suggestion for a person to confirm, never as an automatic
action. Respond ONLY with a JSON object (no markdown fences, no extra
text) in exactly this shape:
{"hazard_type": string, "estimated_water_depth_m": number or null,
"recommendation": string, "confidence": "low"|"medium"|"high"}"""


@lru_cache(maxsize=1)
def _get_client() -> genai.Client:
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def analyze_flood_photo(image_bytes: bytes, mime_type: str = "image/jpeg") -> TriageResponse:
    """Send a citizen photo to Gemini 2.5 Flash and return a structured triage result.

    Degrades gracefully on any failure -- a bad API call or malformed
    JSON response returns a low-confidence fallback instead of raising.
    """
    try:
        client = _get_client()
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                _TRIAGE_PROMPT,
            ],
        )
        reply = response.text.strip()
        # Strip ```json fences if the model adds them despite instructions.
        cleaned = reply.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        return TriageResponse(**parsed)

    except Exception as exc:
        print(f"[gemini_client] Gemini call failed, returning fallback: {exc}")
        # Never let a failed AI call crash the live pipeline.
        return TriageResponse(
            hazard_type="unknown",
            confidence="low",
            recommendation="Unable to auto-analyze -- flag for manual review",
        )
