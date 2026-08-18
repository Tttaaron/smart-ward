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
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"cloud-llm-{uuid4().hex[:8]}",
        )
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

    def _log_event(self, stage: str, level: int = logging.INFO, **fields) -> None:
        record = {
            "stage": stage,
            "service": "cloud-llm-service",
            **{key: value for key, value in fields.items() if value is not None},
        }
        logger.log(
            level,
            "cloud_inference %s",
            json.dumps(record, ensure_ascii=False, sort_keys=True),
        )

    def connect(self) -> None:
        self.client.connect_async(self.broker_host, self.broker_port, 60)
        self.client.loop_start()
        self._log_event(
            "mqtt_connecting",
            broker=self.broker_host,
            port=self.broker_port,
            llm_mode=self.llm.mode,
        )

    def disconnect(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()
        self._log_event("mqtt_disconnected")

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        rc = getattr(reason_code, "value", reason_code)
        if rc == 0:
            topic = "ward/+/node/+/inference/request"
            client.subscribe(topic, qos=1)
            self._log_event("mqtt_subscribed", topic=topic, qos=1)
        else:
            self.total_errors += 1
            self._log_event("mqtt_connect_failed", level=logging.ERROR, rc=rc)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        rc = getattr(reason_code, "value", reason_code)
        level = logging.WARNING if rc else logging.INFO
        self._log_event("mqtt_disconnected", level=level, rc=rc)

    def _on_message(self, client, userdata, msg):
        self._log_event(
            "request_received",
            topic=msg.topic,
            payload_bytes=len(msg.payload),
        )

        try:
            envelope_data = json.loads(msg.payload.decode("utf-8"))
            envelope = MqttEnvelope(**envelope_data)
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
            self.total_errors += 1
            self._log_event(
                "request_parse_failed",
                level=logging.ERROR,
                topic=msg.topic,
                error=str(exc),
            )
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
            self.total_errors += 1
            self._log_event(
                "request_invalid",
                level=logging.ERROR,
                topic=msg.topic,
                event_id=payload.get("event_id"),
                trace_id=payload.get("trace_id"),
                node_id=payload.get("node_id"),
                ward_id=payload.get("ward_id"),
                error=str(exc),
            )
            return

        self._log_event(
            "request_validated",
            topic=msg.topic,
            event_id=request.event_id,
            trace_id=request.trace_id,
            node_id=request.node_id,
            ward_id=request.ward_id,
            event_type=request.event_type,
            priority=request.priority,
            confidence=request.confidence,
            request_mode=request.request_mode,
            timeout_ms=request.timeout_ms,
        )

        cached = self._get_cached_result(request.event_id)
        if cached is not None:
            self.total_duplicates += 1
            response = dict(cached.result)
            response["trace_id"] = request.trace_id
            node_id = request.node_id or cached.node_id
            self._log_event(
                "duplicate_reused",
                event_id=request.event_id,
                trace_id=request.trace_id,
                old_trace_id=cached.trace_id,
                node_id=node_id,
                judgment=response.get("judgment"),
                confidence=response.get("confidence"),
                latency_ms=response.get("latency_ms"),
            )
            self._publish_response(node_id, response)
            return

        self.total_requests += 1
        self._log_event(
            "inference_started",
            event_id=request.event_id,
            trace_id=request.trace_id,
            node_id=request.node_id,
            ward_id=request.ward_id,
            event_type=request.event_type,
            mode=self.llm.mode,
            model_name=self.llm.model_name,
            model_version=self.llm.model_version,
        )

        result = self._infer_with_fallback(request)

        self._log_event(
            "inference_completed",
            event_id=result.get("event_id"),
            trace_id=result.get("trace_id"),
            node_id=request.node_id,
            ward_id=request.ward_id,
            event_type=request.event_type,
            judgment=result.get("judgment"),
            confidence=result.get("confidence"),
            latency_ms=result.get("latency_ms"),
            model_name=result.get("model_name"),
            model_version=result.get("model_version"),
        )

        self._store_cached_result(request.event_id, request.trace_id, request.node_id, result)
        self._publish_response(request.node_id, result)

    def _infer_with_fallback(self, request: InferenceRequest) -> Dict[str, Any]:
        try:
            result = self.llm.infer(request.model_dump())
        except Exception as exc:
            self.total_errors += 1
            self._log_event(
                "inference_failed",
                level=logging.ERROR,
                event_id=request.event_id,
                trace_id=request.trace_id,
                node_id=request.node_id,
                mode=self.llm.mode,
                error=str(exc),
            )
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
            self.total_errors += 1
            self._log_event(
                "response_invalid",
                level=logging.ERROR,
                event_id=request.event_id,
                trace_id=request.trace_id,
                node_id=request.node_id,
                error=str(exc),
            )
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
            self.total_errors += 1
            self._log_event(
                "response_publish_failed",
                level=logging.ERROR,
                event_id=result.get("event_id"),
                trace_id=result.get("trace_id"),
                node_id=node_id,
                reason="missing_node_id",
            )
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

        self._log_event(
            "response_publishing",
            event_id=response.event_id,
            trace_id=response.trace_id,
            node_id=node_id,
            topic=topic,
            judgment=response.judgment,
            confidence=response.confidence,
            latency_ms=response.latency_ms,
            model_name=response.model_name,
            model_version=response.model_version,
        )

        msg_info = self.client.publish(
            topic,
            json.dumps(envelope, ensure_ascii=False),
            qos=1,
        )
        if msg_info.rc == mqtt.MQTT_ERR_SUCCESS:
            self.total_responses += 1
            self._log_event(
                "response_published",
                event_id=response.event_id,
                trace_id=response.trace_id,
                node_id=node_id,
                topic=topic,
                judgment=response.judgment,
                confidence=response.confidence,
                latency_ms=response.latency_ms,
                model_name=response.model_name,
                model_version=response.model_version,
            )
            return True

        self.total_errors += 1
        self._log_event(
            "response_publish_failed",
            level=logging.ERROR,
            event_id=response.event_id,
            trace_id=response.trace_id,
            node_id=node_id,
            topic=topic,
            rc=msg_info.rc,
        )
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
        self._log_event(
            "dedup_cache_stored",
            event_id=event_id,
            trace_id=trace_id,
            node_id=node_id,
            ttl_seconds=self._dedup_ttl,
        )

    def _cleanup_dedup(self, now: float) -> None:
        expired = [
            event_id
            for event_id, cached in self._processed_events.items()
            if now - cached.stored_at > self._dedup_ttl
        ]
        for event_id in expired:
            del self._processed_events[event_id]
            self._log_event("dedup_cache_expired", event_id=event_id)

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