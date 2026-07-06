"""
api/routes_risk.py
--------------------
REST endpoints for reading current and historical risk scores. These are
what MapView.tsx / SystemTickers.tsx on the frontend call on initial page
load (they get subsequent updates over the WebSocket instead of polling).
"""

from fastapi import APIRouter, HTTPException

from integrations.redis_client import get_all_risk_scores
from integrations.bigquery_client import query_recent_history

router = APIRouter(prefix="/api", tags=["risk"])


@router.get("/risk-scores")
def get_risk_scores():
    """Initial snapshot the dashboard fetches on page load, before the
    WebSocket connection takes over for live updates."""
    return get_all_risk_scores()


@router.get("/history/{pipe_section}")
def get_history(pipe_section: str, hours: int = 24):
    """Powers the dashboard's trend chart for a single zone. BigQuery is
    supplementary (see EXECUTION_PLAN.md) -- surface failures as a clean
    502 instead of a raw 500 so the frontend can show "history
    unavailable" rather than crash."""
    try:
        return query_recent_history(pipe_section, hours)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"history unavailable: {exc}")
