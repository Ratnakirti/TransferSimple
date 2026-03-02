"""
WebSocket connection manager — broadcasts real-time card state updates to
all connected frontend clients.
"""
import json
from fastapi import WebSocket, WebSocketDisconnect, APIRouter

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._active = [ws for ws in self._active if ws is not websocket]

    async def broadcast(self, payload: dict) -> None:
        """Send a JSON payload to every connected client."""
        message = json.dumps(payload)
        dead: list[WebSocket] = []
        for ws in self._active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


# Module-level singleton — import this from routes.py
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        # Keep connection alive; we only push from the server side
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
