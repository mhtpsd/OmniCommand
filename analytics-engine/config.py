"""
config.py
---------
Loads every environment variable from `.env` (see .env.example) into one
Settings object that every other module imports from, instead of each
file calling os.getenv() separately. Simple enough to implement outright
rather than leave as a TODO.
"""

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "urban-sensor-events")
    KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "analytics-engine")

    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

    GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
    BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "omnicommand")
    BIGQUERY_TABLE = os.getenv("BIGQUERY_TABLE", "sensor_risk_history")

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    BATCH_WINDOW_SECONDS = int(os.getenv("BATCH_WINDOW_SECONDS", "3"))


settings = Settings()

if not settings.GCP_PROJECT_ID:
    print("[config] WARNING: GCP_PROJECT_ID is not set -- BigQuery writes will fail.")
if not settings.GEMINI_API_KEY:
    print("[config] WARNING: GEMINI_API_KEY is not set -- photo triage will fail.")
