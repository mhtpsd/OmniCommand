"""
main.py
--------
FastAPI entrypoint. Wires together: CORS (so the Next.js frontend can call
this API from a different port), the REST routers, the WebSocket endpoint
for live push updates, and starts the Kafka consumer as a background
thread on startup.

RUN
cd analytics-engine
uvicorn main:app --reload --port 8000
"""

import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api.routes_risk import router as risk_router
from api.routes_triage import router as triage_router
from api.websocket import manager
from streaming.consumer import run_consumer_loop


# Use the modern lifespan context manager instead of the deprecated
# @app.on_event("startup") / @app.on_event("shutdown") pattern
# (FastAPI >= 0.93 recommends lifespan; on_event still works but
# emits a DeprecationWarning on FastAPI 0.115).
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ------- startup -------
    # KafkaConsumer is synchronous/blocking, so it can't run on the main
    # async event loop. Capture the running loop here and hand it to the
    # consumer thread so it can bridge its broadcast() calls back onto
    # it via asyncio.run_coroutine_threadsafe (see streaming/consumer.py).
    # asyncio.get_running_loop() is the correct call inside an async context
    # (replaces the deprecated asyncio.get_event_loop() in Python 3.10+).
    loop = asyncio.get_running_loop()
    thread = threading.Thread(
        target=run_consumer_loop, args=(loop,), daemon=True
    )
    thread.start()

    yield  # application runs here

    # ------- shutdown (daemon thread exits automatically with the process) -------


app = FastAPI(title="OmniCommand Analytics Engine", lifespan=lifespan)

# TODO: restrict allow_origins to your actual frontend URL before any
# real deployment -- "*" is fine for local hackathon development only.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(risk_router)
app.include_router(triage_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Push-only from the server's side -- the client doesn't need
            # to send anything meaningful back, this just keeps the
            # connection open and lets us detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
