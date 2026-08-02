"""云端MQTT处理器

订阅边缘端推理请求，调用LLM研判后回传结果。

主题:
  订阅: ward/+/node/+/inference/request
  发布: node/{node_id}/inference/response
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

import paho.mqtt.client as mqtt

from .llm_client import LLMClient
from .schemas import MqttEnvelope, InferenceResponse

logger = logging.getLogger(__name__)


class CloudMqttHandler:
    """云端MQTT消息处理器"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.broker_host = os.getenv("MQTT_BROKER", "localhost")
        self.broker_port = int(os.getenv("MQTT_PORT", "1883"))
        self.client = mqtt.Client(client_id=f"cloud-llm-{uuid4().hex[:8]}")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        # 去重缓存
        self._processed_events: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._dedup_ttl = 300  # 5分钟去重

        # 统计
        self.total_requests = 0
        self.total_responses = 0
        self.total_errors = 0
        self.start_time = time.time()

    def connect(self) -> None:
        """连接MQTT Broker"""
        self.client.connect_async(self.broker_host, self.broker_port, 60)
        self.client.loop_start()
        logger.info(f"MQTT connecting to {self.broker_host}:{self.broker_port}")

    def disconnect(self) -> None:
        """断开连接"""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("MQTT disconnected")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            # 订阅所有病房/节点的推理请求
            client.subscribe("ward/+/node/+/inference/request", qos=1)
            logger.info("MQTT connected, subscribed to inference/request")
        else:
            logger.error(f"MQTT connection failed: rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        logger.warning(f"MQTT disconnected: rc={rc}")

    def _on_message(self, client, userdata, msg):
        """处理收到的推理请求"""
        try:
            raw = msg.payload.decode("utf-8")
            envelope_data = json.loads(raw)
        except Exception as e:
            logger.error(f"Failed to parse message: {e}")
            self.total_errors += 1
            return

        # 解析信封
        envelope = MqttEnvelope(**envelope_data)
        payload = envelope.payload or envelope_data

        event_id = payload.get("event_id") or envelope.event_id or ""
        trace_id = payload.get("trace_id") or envelope.trace_id or ""

        if not event_id:
            logger.warning("Request missing event_id, ignored")
            return

        # 去重
        with self._lock:
            now = time.time()
            self._cleanup_dedup(now)
            if event_id in self._processed_events:
                logger.info(f"Duplicate request ignored: event={event_id}")
                return
            self._processed_events[event_id] = now

        self.total_requests += 1
        node_id = payload.get("node_id", "")
        if not node_id:
            parts = msg.topic.split("/")
            if len(parts) >= 4:
                node_id = parts[3]

        logger.info(f"Processing: event={event_id}, trace={trace_id}, "
                     f"type={payload.get('event_type')}, node={node_id}")

        # 调用LLM推理
        try:
            result = self.llm.infer(payload)
        except Exception as e:
            logger.error(f"LLM inference failed: {e}")
            self.total_errors += 1
            result = {
                "event_id": event_id,
                "trace_id": trace_id,
                "judgment": "escalate",
                "confidence": 0.0,
                "advice": f"云端推理异常: {str(e)[:100]}",
                "latency_ms": 0,
                "model_name": self.llm.model_name,
                "model_version": self.llm.model_version,
            }

        # 发布响应
        self._publish_response(node_id, result)

    def _publish_response(self, node_id: str, result: Dict[str, Any]) -> None:
        """发布推理响应"""
        if not node_id:
            logger.error("Cannot publish response: missing node_id")
            return

        topic = f"node/{node_id}/inference/response"
        response = {
            "message_id": str(uuid4()),
            "event_id": result["event_id"],
            "trace_id": result["trace_id"],
            "schema_version": "v1",
            "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "cloud:llm-service",
            "payload": {
                "event_id": result["event_id"],
                "trace_id": result["trace_id"],
                "judgment": result["judgment"],
                "confidence": result["confidence"],
                "advice": result["advice"],
                "latency_ms": result["latency_ms"],
                "model_name": result["model_name"],
                "model_version": result["model_version"],
            },
        }

        msg_info = self.client.publish(
            topic,
            json.dumps(response, ensure_ascii=False),
            qos=1,
        )
        # 注意：不能在 MQTT 回调线程内 wait_for_publish —— paho 的 PUBACK
        # 也在 loop 线程处理，同步等待会自锁，导致每次固定阻塞 timeout 秒。
        # publish 本身是异步入队，由 loop 线程发送，rc 已即时反映入队结果。

        if msg_info.rc == mqtt.MQTT_ERR_SUCCESS:
            self.total_responses += 1
            logger.info(f"Response sent: {topic} -> {result['judgment']}")
        else:
            self.total_errors += 1
            logger.error(f"Failed to publish response: rc={msg_info.rc}")

    def _cleanup_dedup(self, now: float) -> None:
        """清理过期的去重记录"""
        expired = [eid for eid, ts in self._processed_events.items()
                   if now - ts > self._dedup_ttl]
        for eid in expired:
            del self._processed_events[eid]

    def get_stats(self) -> Dict[str, Any]:
        """获取服务统计"""
        uptime = time.time() - self.start_time
        with self._lock:
            pending_dedup = len(self._processed_events)
        return {
            "broker": f"{self.broker_host}:{self.broker_port}",
            "uptime_seconds": round(uptime, 1),
            "total_requests": self.total_requests,
            "total_responses": self.total_responses,
            "total_errors": self.total_errors,
            "pending_dedup": pending_dedup,
            "llm_mode": self.llm.mode,
        }
