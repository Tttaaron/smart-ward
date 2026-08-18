"""Unit tests for cloud-llm-service."""

import json
import unittest
from types import SimpleNamespace

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


if __name__ == "__main__":
    unittest.main()
