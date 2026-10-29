import json

from fastapi import WebSocket


class TelemetryHub:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, frame: dict) -> None:
        message = json.dumps({"type": "telemetry", "frame": frame})
        stale = []
        for websocket in tuple(self.connections):
            try:
                await websocket.send_text(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)


hub = TelemetryHub()
