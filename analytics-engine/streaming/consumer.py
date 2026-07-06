"""
streaming/consumer.py
----------------------
Consume SensorEvent messages from Kafka, group them into small time-windowed
batches (micro-batching), and hand each batch to processing/risk_scoring.py.
This is what makes the system "streaming" without needing a separate
Flink/Spark cluster -- see EXECUTION_PLAN.md, "Decisions & tradeoffs".

KafkaConsumer (kafka-python-ng) is blocking/synchronous -- run this loop in
a background thread, started from main.py's startup event, never directly
inside the FastAPI async event loop.
"""

import asyncio
import json
import time

from kafka import KafkaConsumer

from config import settings
from models.schemas import SensorEvent
from processing.risk_scoring import compute_risk_scores
from integrations.redis_client import write_risk_scores
from integrations.bigquery_client import insert_batch


def _make_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        settings.KAFKA_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=settings.KAFKA_CONSUMER_GROUP,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
    )


def _flush(buffer: list[SensorEvent], loop: "asyncio.AbstractEventLoop | None") -> None:
    """Compute risk scores for the buffered batch and fan them out to
    Redis (live reads), BigQuery (history), and connected dashboards."""
    risk_scores = compute_risk_scores([event.model_dump() for event in buffer])

    write_risk_scores(risk_scores)
    insert_batch(risk_scores)

    if loop is not None and risk_scores:
        # api.websocket.manager.broadcast is async; this loop runs in a
        # plain background thread, so schedule the coroutine onto the
        # FastAPI event loop captured at startup instead of calling it
        # directly (which would fail -- there's no running loop here).
        from api.websocket import manager

        message = {
            "type": "risk_update",
            "data": [score.model_dump(mode="json") for score in risk_scores],
        }
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), loop)


def run_consumer_loop(loop: "asyncio.AbstractEventLoop | None" = None) -> None:
    """Blocking micro-batch consumer loop. Must run in a background thread
    (see main.py's startup event), never directly on the FastAPI async
    event loop -- KafkaConsumer is synchronous.

    `loop` is the running asyncio event loop captured by main.py at
    startup, used to bridge broadcast() calls from this sync thread back
    onto the async app. It's optional so this function can still be run
    standalone (e.g. `python -m streaming.consumer` for local testing) --
    in that case risk scores still land in Redis/BigQuery, they just
    won't be pushed over any websocket.
    """
    buffer: list[SensorEvent] = []
    last_flush = time.time()

    while True:
        try:
            consumer = _make_consumer()
            print(f"[consumer] connected to Kafka topic '{settings.KAFKA_TOPIC}'")

            while True:
                records = consumer.poll(timeout_ms=500)
                for _partition, messages in records.items():
                    for message in messages:
                        try:
                            buffer.append(SensorEvent(**message.value))
                        except Exception as exc:  # malformed event -- skip, don't crash
                            print(f"[consumer] skipping malformed event: {exc}")

                now = time.time()
                if buffer and now - last_flush >= settings.BATCH_WINDOW_SECONDS:
                    try:
                        _flush(buffer, loop)
                    except Exception as exc:
                        # BigQuery/Redis/broadcast hiccups shouldn't kill the
                        # consumer -- log and keep going with the next batch.
                        print(f"[consumer] error flushing batch: {exc}")
                    finally:
                        buffer.clear()
                        last_flush = now

        except Exception as exc:
            # Kafka not ready yet (e.g. still starting up in docker-compose),
            # or the connection dropped -- retry after a short backoff
            # instead of crashing the whole app.
            print(f"[consumer] connection error: {exc} -- retrying in 3s")
            time.sleep(3)


if __name__ == "__main__":
    # Standalone smoke test (see EXECUTION_PLAN.md build order step 5):
    # confirms risk scores land in Redis without needing the full FastAPI
    # app running. redis-cli SMEMBERS risk:zones / GET risk:<zone> to check.
    run_consumer_loop()
