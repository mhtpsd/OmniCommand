"""
api/routes_triage.py
-----------------------
Endpoint for citizen photo uploads -> Gemini hazard analysis. Powers the
"upload a photo" demo flow shown in ActionPanel.tsx on the frontend.
"""

from fastapi import APIRouter, UploadFile, File

from integrations.gemini_client import analyze_flood_photo
from api.websocket import manager

router = APIRouter(prefix="/api", tags=["triage"])


@router.post("/triage")
async def triage_photo(file: UploadFile = File(...)):
    image_bytes = await file.read()
    result = analyze_flood_photo(image_bytes, mime_type=file.content_type)

    # Push to every connected dashboard immediately so ActionPanel.tsx
    # updates live, in addition to the direct REST response below.
    await manager.broadcast({"type": "triage_alert", "data": result.model_dump(mode="json")})

    return result
