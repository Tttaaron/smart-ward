"""MQTT consumer for cloud-side inference requests."""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from .llm_client import LLMClient
from .schemas import InferenceRequest, InferenceResponse, MqttEnvelope

logger = logging.getLogger(__name__)


@dataclass
class CachedInference:
    trace_id: str
    node_id: str
    result: Dict[str, Any]
    stored_at: float


class CloudMqttHandler:
    """Subscribe to edge requests and publish cloud inference responses."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.broker_host = os.getenv("MQTT_BROKER", "localhost")
        self.broker_port = int(os.getenv("MQTT_PORT", "1883"))
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"cloud-llm-{uuid4().hex[:8]}")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        self._processed_events: Dict[str, CachedInference] = {}
        self._lock = threading.Lock()
        self._dedup_ttl = int(os.getenv("CLOUD_DEDUP_TTL_SECONDS", "300"))

        self.total_requests = 0
        self.total_responses = 0
        self.total_duplicates = 0
        self.total_errors = 0
        self.start_time = time.time()

    def connect(self) -> None:
        self.client.connect_async(self.broker_host, self.broker_port, 60)
        self.client.loop_start()
        logger.info("MQTT connecting to %s:%s", self.broker_host, self.broker_port)

    def disconnect(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("MQTT disconnected")

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        rc = getattr(reason_code, "value", reason_code)
        if rc == 0:
            client.subscribe("ward/+/node/+/inference/request", qos=1)
            logger.info("MQTT connected, subscribed to ward/+/node/+/inference/request")
        else:
            logger.error("MQTT connection failed: rc=%s", rc)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        rc = getattr(reason_code, "value", reason_code)
        logger.warning("MQTT disconnected: rc=%s", rc)

    def _on_message(self, client, userdata, msg):
        try:
            envelope_data = json.loads(msg.payload.decode("utf-8"))
            envelope = MqttEnvelope(**envelope_data)
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
            logger.error("Failed to parse MQTT inference request: %s", exc)
            self.total_errors += 1
            return

        payload = dict(envelope.payload or envelope_data)
        if envelope.event_id and not payload.get("event_id"):
            payload["event_id"] = envelope.event_id
        if envelope.trace_id and not payload.get("trace_id"):
            payload["trace_id"] = envelope.trace_id

        topic_node_id = self._node_id_from_topic(msg.topic)
        if topic_node_id and not payload.get("node_id"):
            payload["node_id"] = topic_node_id
        topic_ward_id = self._ward_id_from_topic(msg.topic)
        if topic_ward_id and not payload.get("ward_id"):
            payload["ward_id"] = topic_ward_id

        try:
            request = InferenceRequest(**payload)
        except ValidationError as exc:
            logger.error("Invalid inference request ignored: %s", exc)
            self.total_errors += 1
            return

        cached = self._get_cached_result(request.event_id)
        if cached is not None:
            self.total_duplicates += 1
            response = dict(cached.result)
            response["trace_id"] = request.trace_id
            node_id = request.node_id or cached.node_id
            logger.info(
                "Duplicate request reused cached result: event=%s old_trace=%s new_trace=%s",
                request.event_id,
                cached.trace_id,
                request.trace_id,
            )
            self._publish_response(node_id, response)
            return

        self.total_requests += 1
        logger.info(
            "Processing inference request: event=%s trace=%s type=%s node=%s",
            request.event_id,
            request.trace_id,
            request.event_type,
            request.node_id,
        )

        result = self._infer_with_fallback(request)
        self._store_cached_result(request.event_id, request.trace_id, request.node_id, result)
        self._publish_response(request.node_id, result)

    def _infer_with_fallback(self, request: InferenceRequest) -> Dict[str, Any]:
        try:
            result = self.llm.infer(request.model_dump())
        except Exception as exc:
            logger.error("LLM inference failed: %s", exc)
            self.total_errors += 1
            result = {
                "event_id": request.event_id,
                "trace_id": request.trace_id,
                "judgment": "escalate",
                "confidence": 0.0,
                "advice": f"云端推理异常，请护士人工复核：{str(exc)[:100]}",
                "latency_ms": 0.1,
                "model_name": self.llm.model_name,
                "model_version": self.llm.model_version,
            }

        try:
            response = InferenceResponse(**result)
        except ValidationError as exc:
            logger.error("LLM returned invalid response, escalating: %s", exc)
            self.total_errors += 1
            response = InferenceResponse(
                event_id=request.event_id,
                trace_id=request.trace_id,
                judgment="escalate",
                confidence=0.0,
                advice="云端模型返回格式异常，请护士人工复核。",
                latency_ms=0.1,
                model_name=self.llm.model_name,
                model_version=self.llm.model_version,
            )
        return response.model_dump()

    def _publish_response(self, node_id: str, result: Dict[str, Any]) -> bool:
        if not node_id:
            logger.error("Cannot publish inference response: missing node_id")
            self.total_errors += 1
            return False

        response = InferenceResponse(**result)
        topic = f"node/{node_id}/inference/response"
        envelope = {
            "message_id": str(uuid4()),
            "event_id": response.event_id,
            "trace_id": response.trace_id,
            "schema_version": "v1",
            "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "cloud:llm-service",
            "payload": response.model_dump(),
        }

        msg_info = self.client.publish(
            topic,
            json.dumps(envelope, ensure_ascii=False),
            qos=1,
        )
        if msg_info.rc == mqtt.MQTT_ERR_SUCCESS:
            self.total_responses += 1
            logger.info("Inference response sent: %s event=%s judgment=%s", topic, response.event_id, response.judgment)
            return True

        self.total_errors += 1
        logger.error("Failed to publish inference response: rc=%s", msg_info.rc)
        return False

    def _get_cached_result(self, event_id: str) -> Optional[CachedInference]:
        now = time.time()
        with self._lock:
            self._cleanup_dedup(now)
            return self._processed_events.get(event_id)

    def _store_cached_result(self, event_id: str, trace_id: str, node_id: str, result: Dict[str, Any]) -> None:
        now = time.time()
        with self._lock:
            self._cleanup_dedup(now)
            self._processed_events[event_id] = CachedInference(
                trace_id=trace_id,
                node_id=node_id,
                result=dict(result),
                stored_at=now,
            )

    def _cleanup_dedup(self, now: float) -> None:
        expired = [
            event_id
            for event_id, cached in self._processed_events.items()
            if now - cached.stored_at > self._dedup_ttl
        ]
        for event_id in expired:
            del self._processed_events[event_id]

    @staticmethod
    def _node_id_from_topic(topic: str) -> str:
        parts = topic.split("/")
        if len(parts) >= 4 and parts[0] == "ward" and parts[2] == "node":
            return parts[3]
        return ""

    @staticmethod
    def _ward_id_from_topic(topic: str) -> str:
        parts = topic.split("/")
        if len(parts) >= 1 and parts[0] == "ward":
            return parts[1]
        return ""

    def get_stats(self) -> Dict[str, Any]:
        uptime = time.time() - self.start_time
        with self._lock:
            pending_dedup = len(self._processed_events)
        return {
            "broker": f"{self.broker_host}:{self.broker_port}",
            "uptime_seconds": round(uptime, 1),
            "total_requests": self.total_requests,
            "total_responses": self.total_responses,
            "total_duplicates": self.total_duplicates,
            "total_errors": self.total_errors,
            "pending_dedup": pending_dedup,
            "dedup_ttl_seconds": self._dedup_ttl,
            "llm_mode": self.llm.mode,
        }

