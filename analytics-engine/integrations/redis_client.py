"""
integrations/redis_client.py
-----------------------------
Store the latest risk score per zone in Redis (fast cache for the live
dashboard) and read them back for the REST API. Redis here is only
"latest known state" -- history lives in BigQuery (bigquery_client.py).
"""

import json
from functools import lru_cache

import redis

from config import settings
from models.schemas import RiskScore


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    """Single reused connection -- @lru_cache means the first call builds it
    and every subsequent call returns the same instance."""
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True,
    )


def write_risk_scores(scores: list[RiskScore]) -> None:
    """Cache the latest risk score per zone. `risk:zones` is a set of zone
    names so get_all_risk_scores() knows which `risk:{zone}` keys to read
    back without needing a KEYS scan."""
    client = get_redis_client()
    for score in scores:
        client.set(f"risk:{score.pipe_section}", score.model_dump_json())
        client.sadd("risk:zones", score.pipe_section)


def get_all_risk_scores() -> list[RiskScore]:
    """Backs GET /api/risk-scores in api/routes_risk.py."""
    client = get_redis_client()
    zones = client.smembers("risk:zones")

    scores: list[RiskScore] = []
    for zone in zones:
        raw = client.get(f"risk:{zone}")
        if raw:
            scores.append(RiskScore.model_validate_json(raw))
    return scores
