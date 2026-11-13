import json
from typing import Dict, Set
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Map of user_id -> set of active WebSockets (allows multi-tab support)
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            payload = json.dumps(message)
            dead_sockets = set()
            for ws in self.active_connections[user_id]:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead_sockets.add(ws)
            for dead in dead_sockets:
                self.active_connections[user_id].discard(dead)

    async def broadcast_to_users(self, message: dict, user_ids: list):
        for uid in user_ids:
            await self.send_personal_message(message, str(uid))

manager = ConnectionManager()
