"""Unit tests for cloud-llm-service."""

import json
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import ValidationError

from app.llm_client import LLMClient
from app.mqtt_handler import CloudMqttHandler
from app.schemas import InferenceRequest, InferenceResponse, MqttEnvelope


class TestLLMClient(unittest.TestCase):
    def setUp(self):
        self.client = LLMClient(mode="mock")

    def test_mock_confirm_high_confidence_p1(self):
        result = self.client._mock_infer({
            "event_id": "evt-001",
            "trace_id": "tr-001",
            "event_type": "fall_suspected",
            "priority": "P1",
            "confidence": 0.85,
        })
        self.assertEqual(result["judgment"], "confirm")
        self.assertEqual(result["event_id"], "evt-001")
        self.assertIn("检测到患者疑似跌倒", result["advice"])

    def test_mock_reject_low_confidence(self):
        result = self.client._mock_infer({
            "event_id": "evt-002",
            "trace_id": "tr-002",
            "event_type": "bed_leave",
            "priority": "P2",
            "confidence": 0.15,
        })
        self.assertEqual(result["judgment"], "reject")

    def test_mock_escalate_medium(self):
        result = self.client._mock_infer({
            "event_id": "evt-003",
            "trace_id": "tr-003",
            "event_type": "abnormal_posture",
            "priority": "P2",
            "confidence": 0.5,
        })
        self.assertEqual(result["judgment"], "escalate")

    def test_mock_delay_is_configurable_for_integration_timeout(self):
        old_delay = os.environ.get("MOCK_INFERENCE_DELAY_MS")
        os.environ["MOCK_INFERENCE_DELAY_MS"] = "15"
        try:
            started_at = time.perf_counter()
            self.client._mock_infer({
                "event_id": "evt-delay",
                "trace_id": "tr-delay",
                "event_type": "fall_suspected",
                "priority": "P1",
                "confidence": 0.9,
            })
        finally:
            if old_delay is None:
                os.environ.pop("MOCK_INFERENCE_DELAY_MS", None)
            else:
                os.environ["MOCK_INFERENCE_DELAY_MS"] = old_delay
        self.assertGreaterEqual((time.perf_counter() - started_at) * 1000, 10)

    def test_response_has_required_fields(self):
        result = self.client._mock_infer({
            "event_id": "evt-004",
            "trace_id": "tr-004",
            "event_type": "fall_suspected",
            "priority": "P1",
            "confidence": 0.9,
        })
        required = [
            "event_id",
            "trace_id",
            "judgment",
            "confidence",
            "advice",
            "latency_ms",
            "model_name",
            "model_version",
        ]
        for field in required:
            self.assertIn(field, result, f"Missing field: {field}")

    def test_parse_json_llm_output(self):
        judgment, confidence, advice = self.client._parse_llm_output(
            '{"judgment":"confirm","confidence":0.82,"advice":"立即查看床位"}',
            {"event_id": "evt", "trace_id": "tr", "event_type": "fall_suspected"},
        )
        self.assertEqual(judgment, "confirm")
        self.assertEqual(confidence, 0.82)
        self.assertEqual(advice, "立即查看床位")

    def test_parse_invalid_llm_output_falls_back_to_valid_judgment(self):
        judgment, confidence, advice = self.client._parse_llm_output(
            "unclear output",
            {
                "event_id": "evt",
                "trace_id": "tr",
                "event_type": "fall_suspected",
                "priority": "P2",
                "confidence": 0.4,
            },
        )
        self.assertIn(judgment, ["confirm", "reject", "escalate"])
        self.assertGreaterEqual(confidence, 0.0)
        self.assertTrue(advice)


class TestSchemas(unittest.TestCase):
    def test_inference_request_parsing(self):
        req = InferenceRequest(**{
            "event_id": "evt-001",
            "trace_id": "tr-001",
            "event_type": "fall_suspected",
            "priority": "P1",
            "confidence": 0.85,
            "node_id": "EDGE-W01-B01",
        })
        self.assertEqual(req.event_id, "evt-001")
        self.assertEqual(req.priority, "P1")

    def test_inference_response_valid(self):
        resp = InferenceResponse(
            event_id="evt-001",
            trace_id="tr-001",
            judgment="confirm",
            confidence=0.85,
            advice="建议立即前往检查。",
            latency_ms=45.2,
        )
        self.assertEqual(resp.judgment, "confirm")

    def test_inference_response_rejects_invalid_judgment(self):
        with self.assertRaises(ValidationError):
            InferenceResponse(
                event_id="evt-001",
                trace_id="tr-001",
                judgment="maybe",
                confidence=0.85,
                advice="bad",
                latency_ms=1,
            )

    def test_envelope_parsing(self):
        env = MqttEnvelope(**{
            "message_id": "msg-1",
            "event_id": "evt-1",
            "trace_id": "tr-1",
            "payload": {"event_type": "fall_suspected"},
        })
        self.assertEqual(env.event_id, "evt-1")
        self.assertEqual(env.payload["event_type"], "fall_suspected")


class TestRealVllmMode(unittest.TestCase):
    def _request(self):
        return {
            "event_id": "evt-vllm",
            "trace_id": "trace-vllm",
            "event_type": "fall_suspected",
            "priority": "P1",
            "confidence": 0.9,
            "timeout_ms": 5000,
        }

    def test_vllm_uses_configured_base_url_model_and_api_key(self):
        env = {
            "VLLM_BASE_URL": "http://vllm.example:8000/v1",
            "VLLM_MODEL": "qwen2.5-14b",
            "VLLM_MODEL_VERSION": "Qwen2.5-14B-Instruct-AWQ",
            "VLLM_API_KEY": "test-key",
            "VLLM_ALLOW_MOCK_FALLBACK": "false",
        }
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "confirm|0.91|Nurse review"}}]
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "httpx.post", return_value=response
        ) as post:
            client = LLMClient(mode="vllm")
            result = client.infer(self._request())

        self.assertEqual(result["model_name"], "qwen2.5-14b")
        self.assertEqual(result["model_version"], "Qwen2.5-14B-Instruct-AWQ")
        self.assertEqual(post.call_args.args[0], "http://vllm.example:8000/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "qwen2.5-14b")

    def test_vllm_error_does_not_silently_fallback_by_default(self):
        with patch.dict(os.environ, {"VLLM_ALLOW_MOCK_FALLBACK": "false"}, clear=True), patch(
            "httpx.post", side_effect=RuntimeError("backend offline")
        ):
            client = LLMClient(mode="vllm")
            with self.assertRaisesRegex(RuntimeError, "vLLM inference failed"):
                client.infer(self._request())

    def test_vllm_readiness_requires_configured_model(self):
        response = Mock()
        response.json.return_value = {"data": [{"id": "qwen2.5-14b"}]}
        with patch.dict(os.environ, {"VLLM_MODEL": "qwen2.5-14b"}, clear=True), patch(
            "httpx.get", return_value=response
        ) as get:
            client = LLMClient(mode="vllm")
            readiness = client.readiness()

        self.assertTrue(readiness["ready"])
        self.assertEqual(readiness["model"], "qwen2.5-14b")
        self.assertEqual(get.call_args.args[0], "http://localhost:8501/v1/models")


class FakePublishResult:
    rc = 0


class FakeMqttClient:
    def __init__(self):
        self.published = []
        self.subscriptions = []

    def publish(self, topic, payload, qos=0):
        self.published.append((topic, json.loads(payload), qos))
        return FakePublishResult()

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))


class CountingLLM:
    mode = "mock"
    model_name = "mock-cloud-model"
    model_version = "0.1-test"

    def __init__(self):
        self.calls = 0
        self.requests = []

    def infer(self, request):
        self.calls += 1
        self.requests.append(request)
        return {
            "event_id": request["event_id"],
            "trace_id": request["trace_id"],
            "judgment": "confirm",
            "confidence": 0.91,
            "advice": "请立即查看床位。",
            "latency_ms": 12.3,
            "model_name": self.model_name,
            "model_version": self.model_version,
        }


class SlowLLM(CountingLLM):
    def __init__(self, delay_s):
        super().__init__()
        self.delay_s = delay_s

    def infer(self, request):
        time.sleep(self.delay_s)
        return super().infer(request)


class TestCloudMqttHandler(unittest.TestCase):
    def _message(self, payload, trace_id="trace-001"):
        envelope = {
            "message_id": "msg-001",
            "event_id": payload.get("event_id"),
            "trace_id": trace_id,
            "schema_version": "v1",
            "source": "edge:EDGE-W01-B01",
            "payload": payload,
        }
        return SimpleNamespace(
            topic="ward/W-01/node/EDGE-W01-B01/inference/request",
            payload=json.dumps(envelope, ensure_ascii=False).encode("utf-8"),
        )

    def test_normal_request_publishes_response(self):
        llm = CountingLLM()
        handler = CloudMqttHandler(llm)
        handler.client = FakeMqttClient()

        handler._on_message(None, None, self._message({
            "event_id": "evt-001",
            "trace_id": "trace-001",
            "event_type": "fall_suspected",
            "priority": "P1",
            "confidence": 0.9,
        }))

        self.assertEqual(llm.calls, 1)
        self.assertEqual(len(handler.client.published), 1)
        topic, envelope, qos = handler.client.published[0]
        self.assertEqual(topic, "node/EDGE-W01-B01/inference/response")
        self.assertEqual(qos, 1)
        self.assertEqual(envelope["payload"]["event_id"], "evt-001")
        self.assertEqual(envelope["payload"]["trace_id"], "trace-001")
        self.assertEqual(envelope["payload"]["judgment"], "confirm")

    def test_duplicate_request_reuses_cached_result_with_new_trace(self):
        llm = CountingLLM()
        handler = CloudMqttHandler(llm)
        handler.client = FakeMqttClient()

        handler._on_message(None, None, self._message({
            "event_id": "evt-dup",
            "trace_id": "trace-001",
            "event_type": "fall_suspected",
            "confidence": 0.9,
        }, trace_id="trace-001"))
        handler._on_message(None, None, self._message({
            "event_id": "evt-dup",
            "trace_id": "trace-002",
            "event_type": "fall_suspected",
            "confidence": 0.9,
        }, trace_id="trace-002"))

        self.assertEqual(llm.calls, 1)
        self.assertEqual(handler.total_duplicates, 1)
        self.assertEqual(len(handler.client.published), 2)
        second_payload = handler.client.published[1][1]["payload"]
        self.assertEqual(second_payload["event_id"], "evt-dup")
        self.assertEqual(second_payload["trace_id"], "trace-002")

    def test_invalid_request_missing_event_id_is_rejected(self):
        llm = CountingLLM()
        handler = CloudMqttHandler(llm)
        handler.client = FakeMqttClient()

        handler._on_message(None, None, self._message({
            "trace_id": "trace-001",
            "event_type": "fall_suspected",
            "confidence": 0.9,
        }))

        self.assertEqual(llm.calls, 0)
        self.assertEqual(len(handler.client.published), 0)
        self.assertEqual(handler.total_errors, 1)

    def test_inference_timeout_publishes_escalate_response(self):
        llm = SlowLLM(delay_s=0.08)
        handler = CloudMqttHandler(llm)
        handler.client = FakeMqttClient()

        handler._on_message(None, None, self._message({
            "event_id": "evt-timeout",
            "trace_id": "trace-timeout",
            "event_type": "fall_suspected",
            "priority": "P1",
            "confidence": 0.9,
            "timeout_ms": 10,
        }))

        self.assertEqual(len(handler.client.published), 1)
        payload = handler.client.published[0][1]["payload"]
        self.assertEqual(payload["judgment"], "escalate")
        self.assertEqual(payload["latency_ms"], 10.0)
        self.assertEqual(payload["status"], "timeout")
        self.assertIn("timeout", payload["advice"].lower())
        self.assertEqual(handler.total_errors, 1)


if __name__ == "__main__":
    unittest.main()
