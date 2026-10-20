from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import WebSocket

from .config import get_settings
from .telemetry import record_ws_connection, record_ws_message


settings = get_settings()


class LiveStreamManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        if settings.websocket_ping_interval_seconds > 0 and self._heartbeat_task is None:
            self._heartbeat_task = loop.create_task(self._heartbeat_worker())

    async def shutdown(self) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        for websocket in list(self._connections):
            try:
                await websocket.close()
            except Exception:
                pass
        self._connections.clear()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        record_ws_connection(1)
        await websocket.send_json(
            {
                "type": "connection",
                "status": "connected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "transport": "websocket",
            }
        )

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)
            record_ws_connection(-1)

    async def broadcast(self, payload: dict) -> None:
        if not self._connections:
            return

        disconnected: list[WebSocket] = []
        for websocket in list(self._connections):
            try:
                await websocket.send_json(payload)
            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(websocket)

        if payload.get("type") != "heartbeat":
            record_ws_message(max(len(self._connections), 1))

    def broadcast_nowait(self, payload: dict) -> None:
        if self._loop is None:
            return
        future = asyncio.run_coroutine_threadsafe(self.broadcast(payload), self._loop)
        future.add_done_callback(self._swallow_future_exception)

    async def _heartbeat_worker(self) -> None:
        while True:
            await asyncio.sleep(settings.websocket_ping_interval_seconds)
            await self.broadcast(
                {
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "connections": len(self._connections),
                }
            )

    @staticmethod
    def _swallow_future_exception(future: asyncio.Future[None]) -> None:
        try:
            future.result()
        except Exception:
            pass


live_stream_manager = LiveStreamManager()


def get_live_stream_manager() -> LiveStreamManager:
    return live_stream_manager
