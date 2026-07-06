# Adding Gemini Enterprise Agent Platform to OmniCommand AI

## Why this addition

Your existing `integrations/gemini_client.py` calls the Gemini API
directly via `google-genai`. That's genuine, valuable AI usage, but it
is **not** the same rubric item as "Gemini Enterprise Agent Platform" --
that's a specific Google Cloud product (the evolution of Vertex AI,
built around the Agent Development Kit). This addition makes the claim
literally true: the triage logic runs as an ADK `Agent`, served through
ADK's Agent Platform runtime, instead of a bare model call.

**Result:** 3 fully legitimate rubric items -- BigQuery (GCP layer),
cuDF/RAPIDS (NVIDIA layer), Gemini Enterprise Agent Platform via ADK
(GCP layer) -- plus Cloud Storage if you added that too.

## Step 0 — verify before relying on anything below

ADK had a 2.0 release with breaking API changes recently. Two specific
things in this doc are my best-informed understanding, not fully
source-verified — have Antigravity fetch these pages and confirm before
finalizing:
- https://google.github.io/adk-docs/runtime/api-server/ — confirm the
  exact JSON key names for sending an **image** as part of a multimodal
  message (I've written `inline_data: {mime_type, data}` below, matching
  the underlying Gemini Content API convention, but confirm the ADK REST
  layer uses the same casing).
- The exact shape of the `/run` response (I've described it below as a
  list of "events" where the final one contains the agent's text reply
  — confirm the exact field names to extract it).

Everything else in this doc (the `Agent` class, the `adk api_server`
command, the session-creation endpoint, the `.env` variables) is
corroborated by multiple independent, current sources.

## What's already scaffolded for you

```
triage-agent/
├── requirements.txt              # google-adk
└── flood_triage_agent/
    ├── __init__.py                # from . import agent
    ├── agent.py                   # root_agent = Agent(...) — done
    └── .env.example               # copy to .env, fill in credentials
```

`agent.py` is fully implemented already — it's a straightforward
`Agent` definition, no TODOs. The folder name `flood_triage_agent`
matters: it becomes the "app name" in every ADK API URL below, so don't
rename it without updating the URLs too.

## Running the agent locally

```bash
cd triage-agent
pip install -r requirements.txt
cp flood_triage_agent/.env.example flood_triage_agent/.env
# edit .env with your credentials (see the two options in that file)

adk api_server . --port 8001
```

This starts a headless FastAPI backend (no UI) serving your agent on
`http://localhost:8001`. Loading it from `triage-agent/` (the parent
folder) is intentional — ADK discovers agent subfolders inside whatever
directory you point it at.

**Test it with text first, before adding images**, to confirm the loop works:
```bash
curl -X POST http://localhost:8001/apps/flood_triage_agent/users/demo_user/sessions/demo_session \
  -H "Content-Type: application/json" -d '{}'

curl -X POST http://localhost:8001/run \
  -H "Content-Type: application/json" \
  -d '{"appName":"flood_triage_agent","userId":"demo_user","sessionId":"demo_session","newMessage":{"role":"user","parts":[{"text":"A street is flooded with water up to car door handles. Analyze this hazard."}]}}'
```
You should get back a JSON response containing the agent's reply — confirm the reply text matches the JSON shape defined in `agent.py`'s `INSTRUCTION` before moving on to image input.

## What to change in analytics-engine

**Replace the internals of `integrations/gemini_client.py`** — keep the
exact same function signature and `TriageResponse` return type, so
`routes_triage.py` and everything downstream needs zero changes.

```python
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
        # VERIFY: confirm "inline_data"/"mime_type"/"data" key casing
        # against the ADK API server docs (see Step 0 above) before
        # relying on this in your final demo.
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
        # VERIFY: confirm the exact field names here against a real
        # response payload from your curl test above -- print(events)
        # once during testing and adjust this extraction to match.
        reply_text = _extract_final_text(events)

        cleaned = reply_text.strip().removeprefix("```json").removesuffix("```").strip()
        parsed = json.loads(cleaned)
        return TriageResponse(**parsed)

    except Exception:
        # Never let a failed AI call crash the request -- degrade gracefully.
        return TriageResponse(
            hazard_type="unknown",
            confidence="low",
            recommendation="Unable to auto-analyze -- flag for manual review",
        )


def _extract_final_text(events: list) -> str:
    """
    TODO: iterate `events` (a list of ADK event dicts) and find the last
    one with a text part in its content, e.g. something like:
        for event in reversed(events):
            for part in event.get("content", {}).get("parts", []):
                if "text" in part:
                    return part["text"]
    Print a real response during testing to confirm the actual structure
    before trusting this.
    """
    raise NotImplementedError("TODO: implement based on a real ADK response payload")
```

**Also update `analytics-engine/requirements.txt`**: remove `google-genai`
(no longer called directly from this service) and add `httpx`.

## Docker / process notes

Keep this as a separate local process for now (`adk api_server . --port
8001` run alongside your existing `docker compose up -d` and `uvicorn
main:app`) rather than folding it into `docker-compose.yml` — one more
moving part to containerize isn't worth the risk this close to
submission. Document the extra run step clearly in your README /
EXECUTION_PLAN.md so anyone re-running your demo knows to start it.

## Update your pitch materials

- **Architecture diagram**: add a small "Triage Agent (ADK / Gemini
  Enterprise Agent Platform)" box that `gemini_client.py` calls over
  HTTP — this is a legitimate extra box, not padding, and it's a good
  visual for judges who know the product name.
- **Rubric slide**: BigQuery + cuDF/RAPIDS + Gemini Enterprise Agent
  Platform = 3 confirmed items across both lists, comfortably clearing
  "use two or more."
- **Tech stack slide**: swap "Gemini API" for "Gemini Enterprise Agent
  Platform (ADK)".

## Definition of done for this addition

- [ ] `adk api_server . --port 8001` starts cleanly from `triage-agent/`
- [ ] The text-only curl test returns a valid JSON hazard assessment
- [ ] `gemini_client.py`'s `_extract_final_text` is implemented against a
      real observed response payload (not guessed)
- [ ] Uploading a photo through your existing `/api/triage` endpoint
      still returns a `TriageResponse` end-to-end, unchanged from the
      frontend's perspective
- [ ] Pitch deck and architecture diagram updated to reflect this
