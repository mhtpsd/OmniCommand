# OmniCommand AI — execution plan

This file is the map for the whole repo. Every source file below already
contains a header comment explaining its own purpose, required imports,
and a step-by-step TODO for what to implement inside it. Build in the
order listed in "Build order" — each phase is independently testable
before you move to the next.

## Current status

| Piece | Status |
|---|---|
| `docker-compose.yml` (Kafka, Zookeeper, Redis) | Done, tested |
| `data-producer/` (CSV → Kafka) | Done, tested |
| `analytics-engine/` (FastAPI, cuDF, Gemini, BigQuery) | Implemented -- see notes below |
| `frontend/` (Next.js dashboard) | Implemented -- see notes below |

## Implementation notes (added after completing the TODOs)

- **`python-multipart` was missing from `analytics-engine/requirements.txt`.**
  FastAPI's `UploadFile`/`File(...)` (used by `routes_triage.py`) requires
  it at runtime -- without it, importing `main.py` raises `RuntimeError:
  Form data requires "python-multipart" to be installed`. Added as a
  pinned dependency.
- **`frontend/package.json` didn't pin `@deck.gl/core`.** `deck.gl`,
  `@deck.gl/react`, and `@deck.gl/layers` were all pinned to `9.0.38`,
  but their shared `@deck.gl/core` peer dependency was left unpinned, so
  npm resolved a newer `9.3.6` for some of them. That version removed
  `phongLighting`/`gouraudLighting` exports the pinned layers package
  still imports, so `next build` failed with "Attempted import error"
  from webpack. Pinned `@deck.gl/core` to `9.0.38` directly -- confirmed
  `npm ls @deck.gl/core` now shows a single deduped version and
  `next build` / `next dev` both succeed.
- Every backend module was smoke-tested directly (not just imported):
  `compute_risk_scores` against a hardcoded batch, a real Redis
  round-trip (write → read back), the FastAPI app booted with
  `/health`, `/api/risk-scores`, `/ws/live`, and `/api/triage` all
  exercised live, and `benchmark_cudf_vs_pandas.py` run end-to-end
  (CPU pass completes and times itself; GPU pass fails with a clear,
  actionable message on a non-RAPIDS machine instead of crashing).
  Kafka/BigQuery/Gemini themselves weren't reachable in the sandbox this
  was built in, so those three integrations are validated via their
  documented graceful-failure paths (consumer retry-backoff, BigQuery
  502, Gemini low-confidence fallback) rather than a live call --
  worth a real end-to-end pass once you have `docker compose up -d`,
  a GCP project, and a Gemini key in hand.
- `data/water_leak_detection_1000_rows.csv` isn't in the scaffold --
  you'll still need to drop the Kaggle CSV there yourself before running
  `data-producer/producer.py`.
- `SAFE_PRESSURE_THRESHOLD` in `risk_scoring.py` is left at the
  scaffold's placeholder (6.0 bar) since the real CSV wasn't available
  to compute `.describe()` against -- re-check it once you have the
  actual data.


## Decisions & tradeoffs (context for why the scaffold looks like this)

- **No Spring Boot.** Everything backend-side lives in one FastAPI
  service (`analytics-engine/`). Running two backend languages (Java +
  Python) for a hackathon timeline adds a second toolchain and a
  serialization boundary for no functional gain — FastAPI covers the
  REST API, WebSocket push, Kafka consumer, cuDF processing, and Gemini
  calls all in one process.
- **No Flink/Spark.** A Python background thread doing micro-batching
  (`streaming/consumer.py`) gets the same bounded-latency aggregation a
  full stream-processing engine would, without standing up and
  debugging a separate cluster under time pressure.
- **No PostgreSQL/PostGIS.** Redis holds live state, BigQuery holds
  history. If you need zone geometry for the map, use a static GeoJSON
  file loaded at startup instead of a third database.
- **cuDF/RAPIDS satisfies the NVIDIA layer**, via `cudf.pandas` — a
  drop-in accelerator, same code path on CPU or GPU. The GPU speedup
  proof runs separately (`processing/benchmark_cudf_vs_pandas.py`) on a
  large synthetic dataset, since the live demo's ~1000-row CSV is too
  small to show a real speedup.
- **BigQuery satisfies the GCP layer**, as a lightweight historical
  insert — not a full data warehouse build-out.

Together, cuDF/RAPIDS + BigQuery satisfy the hackathon's "use 2+ from
the combined GCP/NVIDIA list" requirement without adding infrastructure
you don't have time to debug.

## Full directory tree

```
OmniCommand AI/
├── EXECUTION_PLAN.md
├── docker-compose.yml
├── data/
│   └── water_leak_detection_1000_rows.csv   # place the Kaggle CSV here
├── data-producer/
│   ├── producer.py
│   └── requirements.txt
├── analytics-engine/
│   ├── main.py                       # FastAPI entrypoint
│   ├── config.py                     # env var loading (done)
│   ├── requirements.txt
│   ├── .env.example
│   ├── models/
│   │   └── schemas.py                # Pydantic models (done)
│   ├── streaming/
│   │   └── consumer.py               # Kafka micro-batch consumer
│   ├── processing/
│   │   ├── risk_scoring.py           # cuDF/pandas risk score logic
│   │   └── benchmark_cudf_vs_pandas.py  # standalone GPU proof, run separately
│   ├── integrations/
│   │   ├── redis_client.py
│   │   ├── bigquery_client.py
│   │   └── gemini_client.py
│   └── api/
│       ├── websocket.py              # live push connection manager
│       ├── routes_risk.py
│       └── routes_triage.py
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── .env.local.example
    └── src/
        ├── app/
        │   ├── layout.tsx
        │   ├── page.tsx
        │   └── globals.css
        ├── components/
        │   ├── MapView.tsx
        │   ├── SystemTickers.tsx
        │   └── ActionPanel.tsx
        └── lib/
            └── api.ts
```

## Build order

Work top to bottom — each step should visibly work before starting the next.

1. **Infra up.** `docker compose up -d` from the project root. Confirm
   all three containers report healthy: `docker compose ps`.
2. **Producer running.** `cd data-producer && py producer.py` — confirm
   console output shows events being sent.
3. **Settings + models.** `config.py` and `models/schemas.py` are
   already fully implemented — copy `.env.example` to `.env` and fill
   in real values before anything else will work.
4. **Redis round-trip.** Implement `integrations/redis_client.py`, then
   `processing/risk_scoring.py` with a simple placeholder formula.
   Manually test both with a tiny hardcoded batch in a Python shell
   before wiring up Kafka — confirms Redis read/write works in
   isolation.
5. **Kafka consumer.** Implement `streaming/consumer.py`. Run it
   standalone (temporarily add a `if __name__ == "__main__":
   run_consumer_loop()` block) with the producer running, and confirm
   risk scores land in Redis (`redis-cli GET risk:<zone>`).
6. **FastAPI app.** Implement `main.py` and `api/routes_risk.py`. Start
   with `uvicorn main:app --reload --port 8000`, hit
   `GET /health` and `GET /api/risk-scores` in a browser to confirm the
   whole ingest → process → cache → API path works end to end.
7. **WebSocket push.** Implement `api/websocket.py`'s methods and the
   `/ws/live` endpoint in `main.py`. Test with a simple `wscat -c
   ws://localhost:8000/ws/live` or a browser console WebSocket while the
   producer is running — confirm messages arrive as new batches process.
8. **BigQuery.** Implement `integrations/bigquery_client.py` and
   `api/routes_risk.py`'s history endpoint. This step is decoupled from
   everything else — if it's not working by demo time, the live
   dashboard still works without it.
9. **Gemini triage.** Implement `integrations/gemini_client.py` and
   `api/routes_triage.py`. Test with `curl -F "file=@sample.jpg"
   http://localhost:8000/api/triage` using any flood photo you find
   online, before wiring up the frontend upload control.
10. **Frontend.** `cd frontend && npm install && npm run dev`. Build
    `page.tsx` first with hardcoded fake data to get the layout right,
    then wire in `lib/api.ts`, then `MapView.tsx`, `SystemTickers.tsx`,
    `ActionPanel.tsx` in that order — the map is the highest-effort
    piece, so do it once the data plumbing around it is already proven.
11. **GPU benchmark.** Run `processing/benchmark_cudf_vs_pandas.py` on a
    free Google Colab T4 runtime. Screenshot the CPU-vs-GPU timing
    output for your pitch deck. This step has no dependency on anything
    else and can be done in parallel at any point.

## Environment variables checklist

Copy both `.env.example` files before step 3 and fill in:
- `analytics-engine/.env`: Kafka, Redis, GCP project ID, BigQuery
  dataset/table, Gemini API key
- `frontend/.env.local`: API base URL, WebSocket URL, Mapbox token

## Definition of done (demo checklist)

- [ ] `docker compose up -d` brings up a healthy stack from a clean clone
- [ ] Producer streams the CSV into Kafka
- [ ] Dashboard shows live risk scores updating without a page refresh
- [ ] Uploading a flood photo returns a Gemini recommendation within a
      few seconds and appears in ActionPanel
- [ ] `benchmark_cudf_vs_pandas.py` output screenshot is in the pitch deck
- [ ] At least one BigQuery row is queryable after a demo run (proves
      the historical layer isn't just decoration)
