import json
import asyncio
from typing import List
from fastapi import WebSocket
from .logger import get_logger

logger = get_logger(__name__)

HEARTBEAT_INTERVAL = 30
HEARTBEAT_TIMEOUT = 10


class WebSocketManager:
    """WebSocket连接管理器: 心跳检测、广播推送"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.last_pong: dict = {}
        self.loop = None
        self._heartbeat_task = None

    async def connect(self, websocket: WebSocket):
        """接受WebSocket连接并记录心跳时间"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.last_pong[id(websocket)] = asyncio.get_event_loop().time()
        logger.info(f"WebSocket连接建立, 当前连接数: {len(self.active_connections)}")
        if self._heartbeat_task is None and self.loop:
            self._heartbeat_task = asyncio.ensure_future(self._heartbeat_loop())

    def disconnect(self, websocket: WebSocket):
        """移除WebSocket连接并清理心跳记录"""
        ws_id = id(websocket)
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.last_pong.pop(ws_id, None)
        logger.info(f"WebSocket断开, 当前连接数: {len(self.active_connections)}")
        if not self.active_connections and self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    async def _heartbeat_loop(self):
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            now = asyncio.get_event_loop().time()
            dead = []
            for conn in self.active_connections:
                ws_id = id(conn)
                if now - self.last_pong.get(ws_id, 0) > HEARTBEAT_INTERVAL + HEARTBEAT_TIMEOUT:
                    dead.append(conn)
                else:
                    try:
                        await conn.send_text(json.dumps({"type": "ping"}))
                    except Exception:
                        dead.append(conn)
            for conn in dead:
                logger.warning("WebSocket心跳超时, 断开连接")
                try:
                    await conn.close()
                except Exception:
                    pass
                self.disconnect(conn)

    async def handle_pong(self, websocket: WebSocket):
        self.last_pong[id(websocket)] = asyncio.get_event_loop().time()

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

    def broadcast_sync(self, message: dict):
        if self.loop and self.active_connections:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(message), self.loop
            )
