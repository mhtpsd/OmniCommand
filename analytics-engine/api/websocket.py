"""
api/websocket.py
------------------
Maintain the set of connected dashboard clients and broadcast live
updates to all of them whenever the Kafka consumer finishes a batch, or
a Gemini triage result comes in.
"""

import json

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass  # already removed -- fine

    async def broadcast(self, message: dict) -> None:
        payload = json.dumps(message)
        for ws in list(self.active_connections):  # copy: disconnect() mutates the list
            try:
                await ws.send_text(payload)
            except Exception:
                self.disconnect(ws)


# Single shared instance -- imported by main.py's /ws/live endpoint,
# streaming/consumer.py (to push new risk scores), and
# api/routes_triage.py (to push new Gemini alerts).
manager = ConnectionManager()
