import asyncio
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from src.main import app


def test_websocket_auth_success() -> None:
    """Verify that a WebSocket connection succeeds with a valid token."""
    client = TestClient(app)
    with client.websocket_connect("/ws/tickets?token=supportflow-websocket-token") as websocket:
        assert websocket is not None


def test_websocket_auth_failure() -> None:
    """Verify that a WebSocket connection fails with code 1008 for an invalid token."""
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/tickets?token=invalid-token"):
            pass
    assert exc_info.value.code == 1008


def test_websocket_broadcast() -> None:
    """Verify that a broadcast message is received by all active connections."""
    client = TestClient(app)
    with client.websocket_connect("/ws/tickets?token=supportflow-websocket-token") as ws1:
        with client.websocket_connect("/ws/tickets?token=supportflow-websocket-token") as ws2:
            # Standardized schema event
            event_payload = {
                "event": "TICKET_CREATED",
                "timestamp": "2026-08-03T19:08:15Z",
                "data": {"ticket_id": 123, "status": "OPEN"}
            }
            # Broadcast the event payload
            asyncio.run(app.state.ws_manager.broadcast(event_payload))
            
            # Receive and assert
            data1 = ws1.receive_json()
            data2 = ws2.receive_json()
            
            assert data1 == event_payload
            assert data2 == event_payload


def test_websocket_disconnect_cleanup() -> None:
    """Verify that client disconnections correctly update active_connections."""
    client = TestClient(app)
    initial_count = len(app.state.ws_manager.active_connections)
    
    with client.websocket_connect("/ws/tickets?token=supportflow-websocket-token"):
        assert len(app.state.ws_manager.active_connections) == initial_count + 1
        
    assert len(app.state.ws_manager.active_connections) == initial_count
