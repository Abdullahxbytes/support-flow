"""WebSocket Router and Handlers for real-time ticket event streaming."""

import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status

from src.core.config import get_settings

logger = logging.getLogger("supportflow.ws")
router = APIRouter()


async def ping_heartbeat(websocket: WebSocket, manager) -> None:
    """Send periodic heartbeat ping messages to keep connection active."""
    try:
        while True:
            await asyncio.sleep(20)
            await websocket.send_json({"type": "ping"})
    except (WebSocketDisconnect, RuntimeError):
        logger.info("Heartbeat failed, connection assumed dead.")
    except asyncio.CancelledError:
        pass


@router.websocket("/tickets")
async def websocket_tickets(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    """Establish real-time event streaming connection for authenticated clients."""
    settings = get_settings()
    if token != settings.WS_SECRET_TOKEN:
        logger.warning("Rejected WebSocket connection: invalid token.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Extract ws_manager from global application state
    manager = websocket.app.state.ws_manager
    await manager.connect(websocket)

    # Start the background heartbeat loop
    ping_task = asyncio.create_task(ping_heartbeat(websocket, manager))

    try:
        while True:
            data = await websocket.receive_json()
            # Handle incoming pong or other messages if any
            if data.get("type") == "pong":
                logger.debug("Received client pong.")
    except WebSocketDisconnect:
        logger.info("Client disconnected gracefully.")
    except Exception as exc:
        logger.warning(f"Unexpected error in WebSocket loop: {exc}")
    finally:
        ping_task.cancel()
        await manager.disconnect(websocket)
        try:
            await websocket.close()
        except Exception:
            pass
