"""WebSocket Connection Manager for real-time client communication."""

import asyncio
import logging
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("supportflow.ws")


class ConnectionManager:
    """Manages active WebSocket connections asynchronously and thread-safely."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept connection and register it in the active pool."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info("New WebSocket connection registered.")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove connection from the active pool."""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info("WebSocket connection removed.")

    async def send_personal_message(self, message: dict, websocket: WebSocket) -> None:
        """Send a direct JSON message to a specific connection."""
        try:
            await websocket.send_json(message)
        except (WebSocketDisconnect, RuntimeError) as exc:
            logger.warning(f"Failed to send personal message, connection dead: {exc}")
            await self.disconnect(websocket)

    async def broadcast(self, message: dict) -> None:
        """Broadcast JSON message to all active connections.

        Prunes dead connections on the fly if sending fails.
        """
        async with self._lock:
            # Create a copy to prevent mutation during iteration
            current_connections = list(self.active_connections)

        for websocket in current_connections:
            try:
                await websocket.send_json(message)
            except (WebSocketDisconnect, RuntimeError) as exc:
                logger.warning(f"Failed to send broadcast, pruning connection: {exc}")
                await self.disconnect(websocket)
