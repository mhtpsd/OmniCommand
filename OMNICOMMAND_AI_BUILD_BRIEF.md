# OmniCommand AI — implementation brief for AI coding agents

## 0. How to use this document

You (the AI reading this) are being asked to complete the implementation
of a hackathon project called **OmniCommand AI**. The project's folder
structure and file scaffold already exist. Every file that still needs
work contains `NotImplementedError` stubs and a docstring describing
exactly what to build. This document is the single, self-contained
source of truth — read it fully before touching any code.

**Rules to follow:**
1. Do not rename files, folders, functions, or classes, and do not change
   any function signature listed in section 6 — other files already
   import these exact names.
2. Do not introduce Spring Boot, Apache Flink, Apache Spark, or
   PostgreSQL/PostGIS. Section 2 explains why each was deliberately cut.
3. Implement the TODOs in the build order given in section 8 — later
   files depend on earlier ones working correctly.
4. After implementing each file, sanity-check it against section 10
   before moving to the next.
5. If something in this brief conflicts with a comment inside an actual
   source file, the source file's comment wins — it is more specific.

---

## 1. Project overview

**What it is:** a real-time urban risk decision-intelligence tool. City
sensor data (water pipe pressure, flow, temperature, anomaly scores)
streams in continuously; the system computes a live risk score per zone
and surfaces it on a dashboard, so emergency response teams and city
planners can make faster decisions (e.g. dispatch a crew, evacuate a
zone) instead of waiting on a slow batch report.

**Primary users:** emergency response teams and city planning
authorities.

**The decision this supports:** "which zone needs attention right now,
and how urgent is it" — backed by a live numeric risk score per zone,
plus AI-generated hazard assessments from citizen-submitted photos.

**Hackathon rubric this must satisfy:**
- A clear real-world user and problem — done (see above).
- A specific decision/bottleneck/workflow that depends on data — done
  (zone risk score drives dispatch/evacuation decisions).
- A pipeline that ingests, cleans, analyzes, and visualizes data — Kafka
  ingests, `risk_scoring.py` analyzes, the Next.js dashboard visualizes.
- A useful output: a risk score, an alert, a recommendation — the
  per-zone `RiskScore` and Gemini-generated `TriageResponse`.
- Evidence that acceleration improves the experience — the standalone
  cuDF vs. pandas benchmark (section 6, `benchmark_cudf_vs_pandas.py`)
  and the live micro-batch pipeline itself.
- Use 2+ of: BigQuery / Cloud Storage / Managed Spark / GKE / Gemini
  Enterprise Agent Platform / Looker (GCP layer) and NVIDIA RAPIDS /
  cuDF / Spark RAPIDS / NVIDIA GPUs (NVIDIA layer) — satisfied by
  **BigQuery** (GCP layer) + **cuDF/RAPIDS** (NVIDIA layer), plus Gemini
  for the multimodal AI layer.

---

## 2. Architecture summary and key decisions

```
data-producer (CSV → Kafka)
        │
        ▼
   Kafka topic: urban-sensor-events
        │
        ▼
analytics-engine (FastAPI, single Python service)
   ├─ streaming/consumer.py     : micro-batches events every few seconds
   ├─ processing/risk_scoring.py: cuDF/pandas → per-zone RiskScore
   ├─ integrations/redis_client.py    → live cache
   ├─ integrations/bigquery_client.py → historical log (GCP layer)
   ├─ integrations/gemini_client.py   → photo → hazard assessment
   └─ api/*                     : REST + WebSocket, served to the frontend
        │
        ▼
frontend (Next.js + Mapbox/Deck.gl)
   fetches initial snapshot over REST, then live updates over WebSocket
```

**Why one backend service, not Spring Boot + FastAPI:** every capability
needed (REST, WebSocket push, Kafka consumer, cuDF processing, Gemini
calls, Redis/BigQuery clients) is natively available in Python/FastAPI.
Running two backend languages means two toolchains and a serialization
boundary for no functional gain, and multiplies what can break for
someone else running the project during judging.

**Why micro-batching instead of Flink/Spark:** a Python background
thread that buffers Kafka messages for a few seconds before processing
them gets the same practical outcome (bounded-latency aggregation)
without standing up and debugging a separate cluster under time
pressure. `RAPIDS Accelerator for Apache Spark` is a valid rubric option
but a heavier lift than plain `cudf.pandas` for this timeline.

**Why no PostgreSQL/PostGIS:** Redis holds live state, BigQuery holds
history. If zone geometry is ever needed for the map, load a static
GeoJSON file at startup instead of standing up a third data store.

**Why cuDF/RAPIDS via `cudf.pandas`:** it's a drop-in accelerator — the
exact same `pandas`-shaped code runs on GPU when available and silently
falls back to CPU pandas when not. This means `risk_scoring.py` works
identically on a judge's laptop with no GPU and on a GPU-enabled
machine. The GPU speedup itself is demonstrated separately, in
`benchmark_cudf_vs_pandas.py`, on a large synthetic dataset — the live
demo's ~1000-row CSV is too small to show a real speedup and would
likely run slower on GPU due to transfer overhead.

**Why Gemini output is framed as decision support, not automation:**
recommendations (e.g. "evacuate zone B") must be surfaced to a human
dispatcher to confirm, never auto-triggered. A misjudged water depth
from a blurry citizen photo should degrade gracefully (see
`gemini_client.py`'s fallback behavior in section 6), not cause a false
real-world action.

---

## 3. Full directory tree

```
OmniCommand AI/
├── EXECUTION_PLAN.md
├── docker-compose.yml                 # Kafka + Zookeeper + Redis — done
├── data/
│   └── water_leak_detection_1000_rows.csv
├── data-producer/                     # done, no changes needed
│   ├── producer.py
│   └── requirements.txt
├── analytics-engine/
│   ├── main.py                        # FastAPI entrypoint — TODO
│   ├── config.py                      # done
│   ├── requirements.txt
│   ├── .env.example
│   ├── models/
│   │   └── schemas.py                 # done
│   ├── streaming/
│   │   └── consumer.py                # TODO
│   ├── processing/
│   │   ├── risk_scoring.py            # TODO
│   │   └── benchmark_cudf_vs_pandas.py  # TODO (run standalone, not in main app)
│   ├── integrations/
│   │   ├── redis_client.py            # TODO
│   │   ├── bigquery_client.py         # TODO
│   │   └── gemini_client.py           # TODO
│   └── api/
│       ├── websocket.py               # TODO
│       ├── routes_risk.py             # TODO
│       └── routes_triage.py           # TODO
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── .env.local.example
    └── src/
        ├── app/
        │   ├── layout.tsx             # done
        │   ├── page.tsx               # TODO
        │   └── globals.css            # done
        ├── components/
        │   ├── MapView.tsx            # TODO
        │   ├── SystemTickers.tsx      # TODO
        │   └── ActionPanel.tsx        # TODO
        └── lib/
            └── api.ts                 # TODO
```

**Important naming note:** the Kafka-consuming folder is named
`streaming/`, not `kafka/`. A folder literally named `kafka` inside
`analytics-engine/` would shadow the installed `kafka` package the
moment anything does `from kafka import KafkaConsumer` — do not rename
it back.

---

## 4. Data contracts

These are fully implemented in `models/schemas.py` — reuse them exactly,
don't redefine equivalents elsewhere.

```python
class SensorEvent(BaseModel):
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
    pipe_section: str
    risk_score: float          # normalized 0-100
    risk_level: str            # "low" | "medium" | "high" | "critical"
    avg_pressure: float
    burst_count: int
    updated_at: datetime

class TriageResponse(BaseModel):
    zone: Optional[str] = None
    estimated_water_depth_m: Optional[float] = None
    hazard_type: str
    recommendation: str
    confidence: str            # "low" | "medium" | "high"
```

**WebSocket message shapes** (server → client, over `/ws/live`):
```json
{ "type": "risk_update", "data": [ /* RiskScore[] */ ] }
{ "type": "triage_alert", "data": { /* TriageResponse */ } }
```

---

## 5. Environment variables

`analytics-engine/.env` (copy from `.env.example`):
```
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=urban-sensor-events
KAFKA_CONSUMER_GROUP=analytics-engine
REDIS_HOST=localhost
REDIS_PORT=6379
GCP_PROJECT_ID=
BIGQUERY_DATASET=omnicommand
BIGQUERY_TABLE=sensor_risk_history
GOOGLE_APPLICATION_CREDENTIALS=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
BATCH_WINDOW_SECONDS=3
```

`frontend/.env.local` (copy from `.env.local.example`):
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws/live
NEXT_PUBLIC_MAPBOX_TOKEN=
```

---

## 6. File-by-file implementation specs

### `analytics-engine/streaming/consumer.py`
**Purpose:** consume `SensorEvent`s from Kafka, buffer them into
time-windowed micro-batches, and hand each batch off for processing.
**Imports:** `json`, `time`, `from kafka import KafkaConsumer` (from
`kafka-python-ng` — do not use plain `kafka-python`, it's incompatible
with Python 3.12+), `config.settings`, `models.schemas.SensorEvent`,
`processing.risk_scoring.compute_risk_scores`,
`integrations.redis_client.write_risk_scores`,
`integrations.bigquery_client.insert_batch`.
**Implement `run_consumer_loop()`:**
1. `KafkaConsumer` is blocking/synchronous — this function must run in a
   background thread (started from `main.py`, never directly in the
   FastAPI async event loop).
2. Create the consumer against `settings.KAFKA_TOPIC`,
   `settings.KAFKA_BOOTSTRAP_SERVERS`, `settings.KAFKA_CONSUMER_GROUP`,
   with `value_deserializer=lambda v: json.loads(v.decode("utf-8"))`,
   `auto_offset_reset="latest"`.
3. Maintain a `buffer: list[SensorEvent]` and `last_flush = time.time()`.
   Use `consumer.poll(timeout_ms=500)` in a loop (not the blocking
   `for msg in consumer:` iterator) so the flush timer can be checked
   even when no messages arrive.
4. When `time.time() - last_flush >= settings.BATCH_WINDOW_SECONDS` and
   the buffer is non-empty: call `compute_risk_scores(buffer)`, then
   `write_risk_scores(result)` and `insert_batch(result)`, then
   broadcast the result over the WebSocket manager (`api.websocket.
   manager`) using `asyncio.run_coroutine_threadsafe` with the event
   loop captured at startup (see `main.py` below), then clear the buffer
   and reset `last_flush`.
5. Wrap the loop in try/except for connection errors (e.g. Kafka not
   ready yet during startup) with a short retry backoff instead of
   crashing the app.

### `analytics-engine/processing/risk_scoring.py`
**Purpose:** the core "decision intelligence" logic — turns a raw batch
into a per-zone risk score. This is what satisfies the NVIDIA
acceleration-layer requirement.
**Imports:** `try: import cudf.pandas; cudf.pandas.install() except
ImportError: pass` (must come before `import pandas as pd` — this is
what makes the same code run on GPU when available and CPU otherwise),
`pandas as pd`, `datetime`, `models.schemas.RiskScore`.
**Implement `compute_risk_scores(batch: list[dict]) -> list[RiskScore]`:**
1. `df = pd.DataFrame(batch)`.
2. `groupby("pipe_section")` and aggregate: mean pressure, mean flow,
   mean temperature, sum of burst_status (→ burst_count), mean
   anomaly_score.
3. Compute a normalized 0–100 risk score per zone. Starting formula
   (tune weights after inspecting real data distributions):
   ```
   risk_score = (
       avg_anomaly * 40
       + min(burst_count, 5) * 10
       + max(0, avg_pressure - SAFE_PRESSURE_THRESHOLD) * 5
   )
   risk_score = min(100, max(0, risk_score))
   ```
   `SAFE_PRESSURE_THRESHOLD` is a module constant — set it from
   `df["Pressure (bar)"].describe()` on the real CSV.
4. Map to `risk_level`: 0–25 low, 25–60 medium, 60–85 high, 85–100
   critical.
5. Return one `RiskScore` per zone with `updated_at=datetime.now
   (timezone.utc)`.

### `analytics-engine/processing/benchmark_cudf_vs_pandas.py`
**Purpose:** produce your own CPU-vs-GPU timing proof, run separately
from the live pipeline (the live demo's dataset is too small to show a
real speedup). Run this on a machine/notebook with an NVIDIA GPU — a
free Google Colab **T4** runtime works, RAPIDS `cudf.pandas` comes
preinstalled there.
**Implement:**
1. Generate a synthetic DataFrame at real scale (5–10 million rows) with
   the same shape as the sensor schema (`pipe_section`, `pressure`,
   `flow_rate`, `temperature`, `burst_status`, `anomaly_score`) using
   `numpy.random`.
2. Time a `groupby(...).agg(...)` call identical to the one in
   `risk_scoring.py`, once in plain pandas, once with `cudf.pandas.
   install()` active (run these in separate processes/kernels — the
   install call is a global monkeypatch on pandas).
3. Print CPU seconds, GPU seconds, and the speedup ratio. Screenshot
   this output for the pitch deck instead of quoting NVIDIA's published
   benchmark numbers.

### `analytics-engine/integrations/redis_client.py`
**Purpose:** cache the latest risk score per zone for fast reads.
**Imports:** `json`, `functools.lru_cache`, `redis`, `config.settings`,
`models.schemas.RiskScore`.
**Implement:**
- `get_redis_client()` — `@lru_cache(maxsize=1)`, returns
  `redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT,
  decode_responses=True)`.
- `write_risk_scores(scores)` — for each score: `client.set(f"risk:
  {score.pipe_section}", score.model_dump_json())` and
  `client.sadd("risk:zones", score.pipe_section)`.
- `get_all_risk_scores()` — read `client.smembers("risk:zones")`, fetch
  and parse each `risk:{zone}` key back into a `RiskScore`, return the
  list. This backs `GET /api/risk-scores`.

### `analytics-engine/integrations/bigquery_client.py`
**Purpose:** historical log — satisfies the GCP data-layer requirement.
**One-time setup before coding:** enable the BigQuery API on a GCP
project, authenticate (`gcloud auth application-default login` or a
service-account JSON via `GOOGLE_APPLICATION_CREDENTIALS`), and create
the dataset + table:
```
bq mk --dataset {GCP_PROJECT_ID}:omnicommand
bq mk --table {GCP_PROJECT_ID}:omnicommand.sensor_risk_history \
  pipe_section:STRING,risk_score:FLOAT,risk_level:STRING,\
  avg_pressure:FLOAT,burst_count:INTEGER,updated_at:TIMESTAMP
```
Free tier (1 TiB queries/month, 10 GB storage/month) comfortably covers
a hackathon demo.
**Implement:**
- `get_bigquery_client()` — `@lru_cache(maxsize=1)`, returns
  `bigquery.Client(project=settings.GCP_PROJECT_ID)`.
- `insert_batch(scores)` — `client.insert_rows_json(table_id, rows)`
  where `rows = [s.model_dump(mode="json") for s in scores]`. Wrap in
  try/except and log failures — BigQuery must never be able to crash
  the live pipeline; it's a supplementary historical log, not the
  critical path.
- `query_recent_history(pipe_section, hours=24)` — parameterized query
  (use `bigquery.ScalarQueryParameter` to avoid injection) filtering
  `pipe_section` and a time window, `ORDER BY updated_at ASC`, returned
  as a list of dicts. Backs `GET /api/history/{pipe_section}`.

### `analytics-engine/integrations/gemini_client.py`
**Purpose:** multimodal hazard triage from a citizen photo.
**Model note:** verify current model availability before building — as
of mid-2026, `gemini-2.5-flash` (fast/cheap) or `gemini-3.1-pro`
(higher accuracy on complex scenes) are reasonable defaults. Do not use
any `gemini-1.5-*` model — that line is fully retired.
**Imports:** `json`, `functools.lru_cache`, `from google import genai`,
`from google.genai import types`, `config.settings`,
`models.schemas.TriageResponse`.
**Implement:**
- `get_gemini_client()` — `@lru_cache(maxsize=1)`, returns
  `genai.Client(api_key=settings.GEMINI_API_KEY)`.
- `analyze_flood_photo(image_bytes, mime_type="image/jpeg")`:
  1. Build a prompt asking Gemini to identify hazard type, estimate
     water depth in meters using visible reference objects if flooding,
     give a one-sentence recommendation, and respond **only** as JSON
     matching the `TriageResponse` shape.
  2. Call `client.models.generate_content(model=settings.GEMINI_MODEL,
     contents=[types.Part.from_bytes(data=image_bytes,
     mime_type=mime_type), prompt_text])`.
  3. Parse `response.text` as JSON (strip ```json fences if present).
  4. On any failure (API error, bad JSON), return a `TriageResponse`
     with `hazard_type="unknown"`, `confidence="low"`, and
     `recommendation="Unable to auto-analyze -- flag for manual
     review"` — never raise. This must degrade gracefully.
  5. **Frame this as decision support, not automation** — reflect that
     in any UI copy the frontend shows around this result.

### `analytics-engine/api/websocket.py`
**Purpose:** manage connected dashboard clients and broadcast updates.
**Implement `class ConnectionManager`:**
- `active_connections: list[WebSocket] = []`
- `async def connect(websocket)` — `await websocket.accept()`, append.
- `def disconnect(websocket)` — remove, guard against `ValueError`.
- `async def broadcast(message: dict)` — `json.dumps` once, then
  `await ws.send_text(...)` for each connection; if a send raises,
  disconnect that client instead of crashing the whole broadcast.
- Instantiate a single shared `manager = ConnectionManager()` at module
  level — imported by `main.py`, `streaming/consumer.py`, and
  `api/routes_triage.py`.

### `analytics-engine/api/routes_risk.py`
**Implement two endpoints under `APIRouter(prefix="/api", tags=["risk"])`:**
- `GET /risk-scores` → returns `integrations.redis_client.
  get_all_risk_scores()`.
- `GET /history/{pipe_section}?hours=24` → returns
  `integrations.bigquery_client.query_recent_history(pipe_section,
  hours)`. Catch failures and raise `HTTPException(502, ...)` so the
  frontend can show "history unavailable" instead of a raw 500.

### `analytics-engine/api/routes_triage.py`
**Implement `POST /triage`** under `APIRouter(prefix="/api",
tags=["triage"])`, accepting `file: UploadFile = File(...)`:
1. `image_bytes = await file.read()`.
2. `result = analyze_flood_photo(image_bytes, mime_type=file.
   content_type)`.
3. `await manager.broadcast({"type": "triage_alert", "data": result.
   model_dump(mode="json")})`.
4. `return result`.

### `analytics-engine/main.py`
**Implement:**
1. FastAPI app with CORS middleware (`allow_origins=["*"]` is fine for
   local hackathon dev only — note this should be restricted before any
   real deployment).
2. Include `risk_router` and `triage_router`.
3. `GET /health` → `{"status": "ok"}`.
4. `WebSocket /ws/live` — `await manager.connect(websocket)`, then loop
   `await websocket.receive_text()` inside try/except
   `WebSocketDisconnect`, calling `manager.disconnect(websocket)` on
   disconnect. This endpoint is push-only from the server's side.
5. `@app.on_event("startup")` — capture the running event loop, start
   `streaming.consumer.run_consumer_loop` in a daemon `threading.Thread`
   so the blocking Kafka consumer doesn't block FastAPI's async loop.

### `frontend/src/lib/api.ts`
**Implement:**
- `fetchRiskScores()` — `fetch(`${API_BASE}/api/risk-scores`)`, parse
  JSON as `RiskScore[]`.
- `fetchHistory(pipeSection, hours=24)` — same pattern against
  `/api/history/{pipeSection}?hours={hours}`.
- `submitTriagePhoto(file)` — build `FormData`, `POST` to `/api/triage`
  (don't set `Content-Type` manually — let the browser set the
  multipart boundary), parse JSON as `TriageResponse`.
- `openLiveSocket(onMessage)` — `new WebSocket(WS_URL)`, `onmessage`
  handler that `JSON.parse`s `event.data` and calls `onMessage`, return
  the socket so the caller can close it on unmount.

### `frontend/src/app/page.tsx`
**Implement:**
- `useState` for `riskScores: RiskScore[]` and `alerts:
  TriageResponse[]`.
- `useEffect` (empty deps): call `fetchRiskScores().then
  (setRiskScores)`, then `openLiveSocket` with a handler that updates
  `riskScores` on `"risk_update"` and prepends to `alerts` on
  `"triage_alert"`. Return a cleanup that closes the socket.
- Render layout: `<MapView riskScores={riskScores} />` as the main
  panel, `<SystemTickers riskScores={riskScores} />` along the top,
  `<ActionPanel alerts={alerts} />` as a side panel.

### `frontend/src/components/MapView.tsx`
**Implement:**
- The CSV has no lat/lng — add a hardcoded lookup table `{ [pipe_section]:
  [lng, lat] }` for a demo city area (fastest path for a hackathon).
- Map `risk_level` to an RGB color array matching the `--risk-*` values
  in `globals.css` (low: green, medium: amber, high: orange, critical:
  red) so map colors and ticker badges agree.
- Build a Deck.gl `ScatterplotLayer` keyed on zone position, colored and
  sized by risk, `pickable: true` with a hover/click tooltip showing
  `pipe_section` + `risk_score`.
- Render inside `<DeckGL>` wrapping a `<Map>` (react-map-gl) using
  `NEXT_PUBLIC_MAPBOX_TOKEN` and a dark Mapbox style.

### `frontend/src/components/SystemTickers.tsx`
**Implement:** derive (as a pure function of the `riskScores` prop, no
extra state) — `zonesMonitored`, `avgRiskScore`, `criticalZones` count,
and `lastUpdated` as a relative time string ticking on a 1-second
interval. Render as a horizontal row of small metric cards; highlight
`criticalZones` in the `--risk-critical` color when > 0.

### `frontend/src/components/ActionPanel.tsx`
**Implement:** a file input + "Analyze photo" button calling
`submitTriagePhoto`, with a loading state while the Gemini call is in
flight (a few seconds). Render the `alerts` prop as a scrollable list of
cards (hazard type, recommendation, confidence, estimated depth if
present), with the newest alert visually highlighted.

---

## 7. REST + WebSocket API contract

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/health` | — | `{"status": "ok"}` |
| GET | `/api/risk-scores` | — | `RiskScore[]` |
| GET | `/api/history/{pipe_section}?hours=24` | — | historical rows (list of dicts) |
| POST | `/api/triage` | multipart file upload | `TriageResponse` |
| WS | `/ws/live` | — | pushes `{type: "risk_update"|"triage_alert", data: ...}` |

---

## 8. Build order

1. `docker compose up -d` — confirm all three containers healthy.
2. Run `data-producer/producer.py` — confirm events are sent.
3. Copy both `.env.example` files, fill in real values.
4. Implement `redis_client.py`, then a placeholder `risk_scoring.py`;
   test both manually with a hardcoded batch before touching Kafka.
5. Implement `streaming/consumer.py`; run it standalone (temporary
   `if __name__ == "__main__": run_consumer_loop()`), confirm scores
   land in Redis (`redis-cli GET risk:<zone>`).
6. Implement `main.py` + `routes_risk.py`; run with `uvicorn main:app
   --reload --port 8000`; hit `/health` and `/api/risk-scores`.
7. Implement `api/websocket.py` + the `/ws/live` endpoint; test with a
   WebSocket client while the producer runs.
8. Implement `bigquery_client.py` + the history endpoint (decoupled —
   the live dashboard works without this if it's not finished in time).
9. Implement `gemini_client.py` + `routes_triage.py`; test with `curl -F
   "file=@sample.jpg" http://localhost:8000/api/triage`.
10. `cd frontend && npm install && npm run dev`. Build `page.tsx` with
    hardcoded fake data first to get the layout right, then wire in
    `lib/api.ts`, then `MapView.tsx`, `SystemTickers.tsx`,
    `ActionPanel.tsx` in that order.
11. Run `benchmark_cudf_vs_pandas.py` on a free Colab T4 runtime;
    screenshot the timing output for the pitch deck. Independent of
    everything else, do this whenever convenient.

---

## 9. Known constraints and gotchas

- Use `kafka-python-ng`, not `kafka-python` — the original is
  unmaintained and breaks on Python 3.12+ with `ModuleNotFoundError:
  kafka.vendor.six.moves`. Both import as `from kafka import ...`.
- Never name a local folder `kafka/` inside `analytics-engine/` — it
  will shadow the installed package.
- `cudf.pandas.install()` must be called before any `import pandas` in
  the same file, and only once per process — don't call it in a file
  that also gets imported by something running the CPU-only benchmark
  path in the same process.
- BigQuery and Gemini calls should both fail gracefully (log + continue
  / return a low-confidence fallback) rather than crash the live
  pipeline — neither is on the critical path for the core demo to work.
- Gemini's water-depth/recommendation output is decision support for a
  human dispatcher, never an autonomous trigger for a real action.

---

## 10. Definition of done

- [ ] `docker compose up -d` brings up a healthy stack from a clean clone.
- [ ] Producer streams the CSV into Kafka.
- [ ] Dashboard shows live risk scores updating without a page refresh.
- [ ] Uploading a flood photo returns a Gemini recommendation within a
      few seconds and appears in `ActionPanel`.
- [ ] `benchmark_cudf_vs_pandas.py` output is captured for the deck.
- [ ] At least one BigQuery row is queryable after a demo run.
