"""MQTT 消息处理器（误报回流）

订阅主题：
  - ward/+/alert/+/ack  → 检测 false_positive 动作，触发困难样本生成
  - ward/+/node/+/event → 缓存事件数据作为生成上下文

复用 cloud-backend 的重连退避、信封解包模式。
"""

import json
import uuid
import threading

import paho.mqtt.client as mqtt

from .config import MQTT_BROKER, MQTT_PORT
from .logger import get_logger

logger = get_logger(__name__)

MQTT_RECONNECT_MIN = 2
MQTT_RECONNECT_MAX = 60


class MqttHandler:
    """订阅误报确认消息，回调触发扩散生成"""

    def __init__(self, db=None, on_false_positive=None):
        self.db = db
        self.on_false_positive = on_false_positive
        self.client = mqtt.Client(
            client_id=f"diffusion-service-{uuid.uuid4().hex[:8]}"
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        # 让 paho 自动管理重连退避，避免在回调线程里 sleep 阻塞网络循环
        # （与 cloud-backend/app/mqtt_handler.py 保持一致）。
        self.client.reconnect_delay_set(
            min_delay=MQTT_RECONNECT_MIN, max_delay=MQTT_RECONNECT_MAX)
        self._event_cache: dict[str, dict] = {}

    def connect(self):
        self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self.client.loop_start()
        logger.info(f"MQTT 客户端已启动 (broker={MQTT_BROKER}:{MQTT_PORT})")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("MQTT 客户端已断开")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT 连接成功")
            topics = [
                ("ward/+/alert/+/ack", 1),
                ("ward/+/node/+/event", 1),
            ]
            for topic, qos in topics:
                client.subscribe(topic, qos=qos)
                logger.info(f"订阅主题: {topic}")
        else:
            logger.error(f"MQTT 连接失败, rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        # 仅记录日志，重连由 paho 的 reconnect_delay_set 自动处理；
        # 不在此 sleep 或手动 reconnect，以免阻塞网络循环线程。
        if rc != 0:
            logger.warning(f"MQTT 意外断开 (rc={rc})，paho 将自动重连")
        else:
            logger.info("MQTT 正常断开")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            business = payload.get("payload", payload)
            topic_parts = msg.topic.split("/")

            # ward/{ward_id}/alert/{event_id}/ack
            if len(topic_parts) == 5 and topic_parts[0] == "ward" and topic_parts[2] == "alert":
                self._handle_ack(business, envelope=payload)

            # ward/{ward_id}/node/{node_id}/event
            elif len(topic_parts) == 5 and topic_parts[0] == "ward" and topic_parts[2] == "node" and topic_parts[4] == "event":
                self._handle_event(business, envelope=payload)

        except json.JSONDecodeError:
            logger.warning(f"MQTT 消息 JSON 解析失败: {msg.topic}")
        except Exception as e:
            logger.error(f"MQTT 消息处理异常: {e}")

    def _handle_ack(self, business: dict, envelope: dict):
        action = business.get("action", "")
        if action != "false_positive":
            return

        event_id = business.get("event_id")
        if not event_id:
            logger.warning("误报确认消息缺少 event_id")
            return

        logger.info(f"收到误报确认: event_id={event_id}")

        cached = self._event_cache.get(event_id, {})
        fp_event = {
            "event_id": event_id,
            "ward_id": business.get("ward_id", cached.get("ward_id", "")),
            "bed_id": business.get("bed_id", cached.get("bed_id", "")),
            "event_type": cached.get("event_type", "unknown"),
            "priority": cached.get("priority", ""),
            "original_data": cached,
            "occurred_at": cached.get("occurred_at", ""),
            "false_positive_at": envelope.get("occurred_at", ""),
        }

        if self.db:
            self.db.save_false_positive(fp_event)

        if self.on_false_positive:
            threading.Thread(
                target=self.on_false_positive,
                args=(fp_event,),
                daemon=True,
            ).start()

    def _handle_event(self, business: dict, envelope: dict):
        event_id = business.get("event_id")
        if not event_id:
            return
        self._event_cache[event_id] = business

        # 清理旧缓存（保留最近 500 条）。按 dict 插入序取最早的 100 条：
        # 此前用 sorted(keys) 排的是 event_id（UUID）字典序，与到达先后无关，
        # 会随机淘汰掉刚缓存的事件，导致误报回流取不到上下文。
        if len(self._event_cache) > 500:
            for k in list(self._event_cache)[:100]:
                del self._event_cache[k]
