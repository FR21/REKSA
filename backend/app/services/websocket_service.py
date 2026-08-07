import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.connections.discard(websocket)

    async def broadcast(self, event: str, data: dict[str, Any]) -> None:
        envelope = {"event": event, "timestamp": datetime.now(UTC).isoformat(), "data": data}
        stale: list[WebSocket] = []
        for connection in tuple(self.connections):
            try:
                await connection.send_json(envelope)
            except Exception:  # connection failure is isolated from MQTT/simulation processing
                stale.append(connection)
        for connection in stale:
            await self.disconnect(connection)


websocket_manager = WebSocketManager()

