"""
WebSocket endpoint for real-time execution streaming.

Provides live updates of pipeline execution events to connected clients.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .execution import _execution_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for broadcasting events."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal(self, message: dict[str, Any], websocket: WebSocket) -> None:
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning("Failed to send WebSocket message: %s", e)

    async def broadcast(self, message: dict[str, Any]) -> None:
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


@router.websocket("/ws/execution")
async def execution_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming execution events.

    Protocol:
    - Server sends events as JSON objects with "type" field
    - Event types:
      - StageStartedEvent: {"type": "stage_started", "stage": "...", ...}
      - StageCompletedEvent: {"type": "stage_completed", "stage": "...", "signal": "...", ...}
      - StageIterationEvent: {"type": "stage_iteration", "stage": "...", "iteration": N, ...}
      - PipelineCompletedEvent: {"type": "pipeline_completed", "status": "...", ...}
      - status: {"type": "status", "status": "...", "current_stage": "...", ...}
    """
    await manager.connect(websocket)
    last_event_index = 0

    try:
        # Send initial status
        state = _execution_state.get_state()
        await manager.send_personal({
            "type": "status",
            **state,
            "event_count": len(_execution_state.events),
        }, websocket)

        # Stream events loop
        while True:
            # Check for new events
            events = _execution_state.get_events(last_event_index)
            for event in events:
                await manager.send_personal(event, websocket)
            last_event_index = len(_execution_state.events)

            # Send periodic status updates
            state = _execution_state.get_state()
            await manager.send_personal({
                "type": "status",
                **state,
                "event_count": len(_execution_state.events),
            }, websocket)

            # Small delay to prevent busy loop
            await asyncio.sleep(0.5)

            # Check if client is still connected by trying to receive
            # (with a short timeout so we don't block)
            try:
                # This will raise WebSocketDisconnect if client disconnected
                await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                # No message received, continue
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
        manager.disconnect(websocket)
