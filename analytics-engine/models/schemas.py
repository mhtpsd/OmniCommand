"""
models/schemas.py
------------------
STATUS: Fully implemented -- these are simple enough to define outright
rather than leave as a TODO. Every other file (streaming/, processing/,
integrations/, api/) should import from here instead of passing raw dicts,
so field names stay consistent across the whole app.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SensorEvent(BaseModel):
    """Mirrors the JSON payload data-producer/producer.py sends to Kafka."""
    timestamp: str
    sensor_id: str
    pipe_section: str
    pressure: float
    flow_rate: float
    temperature: float
    leak_status: int
    burst_status: int
    anomaly_score: float


class RiskScore(BaseModel):
    """Output of processing/risk_scoring.py -- one row per pipe_section per batch."""
    pipe_section: str
    risk_score: float          # normalized 0-100
    risk_level: str            # "low" | "medium" | "high" | "critical"
    avg_pressure: float
    burst_count: int
    updated_at: datetime


class TriageResponse(BaseModel):
    """Output of integrations/gemini_client.py after analyzing a citizen photo."""
    zone: Optional[str] = None
    estimated_water_depth_m: Optional[float] = None
    hazard_type: str           # e.g. "flooding", "downed power line", "road blockage"
    recommendation: str        # human-readable recommendation text
    confidence: str            # "low" | "medium" | "high"
