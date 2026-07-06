# OmniCommand AI

Real-time urban infrastructure risk monitoring powered by Kafka, Redis, Gemini, and BigQuery.

## What it is

OmniCommand AI ingests live pressure/flow sensor data from 10 pipe zones, computes risk scores using a physics-based formula (pressure drop + flow spike), surfaces alerts on a live Mapbox dashboard, and lets field workers upload hazard photos for AI-powered triage via Google's Gemini Enterprise Agent Platform (ADK).

## How to run (development)

**Prerequisites:** Docker Desktop (Linux containers), Python 3.10+, Node.js 18+.

```bash
# 1. Infrastructure (Kafka + Zookeeper + Redis)
docker compose up -d

# 2. ADK Triage Agent  (terminal 1)
cd triage-agent
pip install -r requirements.txt
adk api_server . --port 8001

# 3. Analytics Backend  (terminal 2)
cd analytics-engine
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 4. Sensor Data Producer  (terminal 3)
cd data-producer
py producer.py

# 5. Frontend  (terminal 4)
cd frontend
npm install && npm run dev
```

Open **http://localhost:3000** for the live dashboard.

## Detailed setup

See [`EXECUTION_PLAN.md`](./EXECUTION_PLAN.md) for full environment setup, API key instructions, and BigQuery/Vertex AI integration steps.

## Architecture

```
[Sensor CSV] → producer.py → Kafka → consumer.py → risk_scoring.py → Redis → FastAPI → Next.js
                                                                           ↓
                                                                       BigQuery
[Photo Upload] → Next.js → /api/triage → ADK Agent Server (port 8001) → Gemini
```

## Tech stack

| Layer | Technology |
|---|---|
| Streaming | Apache Kafka (Confluent) |
| State cache | Redis |
| AI acceleration | cuDF/RAPIDS (pandas drop-in) |
| AI triage | Gemini Enterprise Agent Platform (ADK) |
| GCP storage | BigQuery |
| Map | Mapbox GL JS |
| Frontend | Next.js 15 |
| Backend | FastAPI |
