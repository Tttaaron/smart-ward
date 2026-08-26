"""进程级单例：WebSocket 连接管理器与 MQTT 处理器。

单独成模块，让 `app.main` 与 `app.routers.*` 共享同一实例——
测试里 `app.main.mqtt_handler` 拿到的与各路由使用的是同一个对象。
"""

from .mqtt_handler import MqttHandler
from .websocket_manager import WebSocketManager

ws_manager = WebSocketManager()
mqtt_handler = MqttHandler(ws_manager)
