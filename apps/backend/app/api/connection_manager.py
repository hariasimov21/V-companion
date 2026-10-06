from fastapi import WebSocket
from pydantic import BaseModel

from app.core.logging import get_logger

log = get_logger("ws")


class ConnectionManager:
    """Tracks connected desktop clients and broadcasts server events to them."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def add(self, websocket: WebSocket) -> None:
        self._clients.add(websocket)
        log.info("Client connected", extra={"fields": {"clients": self.client_count}})

    def remove(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)
        log.info("Client disconnected", extra={"fields": {"clients": self.client_count}})

    async def send(self, websocket: WebSocket, event: BaseModel) -> None:
        await websocket.send_text(event.model_dump_json())

    async def publish(self, event: BaseModel) -> None:
        for client in list(self._clients):
            try:
                await self.send(client, event)
            except Exception:  # A dead socket must not break delivery to the others.
                log.debug("Dropping unreachable client")
                self._clients.discard(client)
