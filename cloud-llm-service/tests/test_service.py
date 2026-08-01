"""云端LLM服务单元测试"""
import unittest
from app.llm_client import LLMClient
from app.schemas import InferenceRequest, InferenceResponse, MqttEnvelope


class TestLLMClient(unittest.TestCase):

    def setUp(self):
        self.client = LLMClient(mode="mock")

    def test_mock_confirm_high_confidence_p1(self):
        """P1高置信度 → confirm"""
        result = self.client._mock_infer({
            "event_id": "evt-001",
            "trace_id": "tr-001",
            "event_type": "fall_suspected",
            "priority": "P1",
            "confidence": 0.85,
        })
        self.assertEqual(result["judgment"], "confirm")
        self.assertEqual(result["event_id"], "evt-001")

    def test_mock_reject_low_confidence(self):
        """低置信度 → reject"""
        result = self.client._mock_infer({
            "event_id": "evt-002",
            "trace_id": "tr-002",
            "event_type": "bed_leave",
            "priority": "P2",
            "confidence": 0.15,
        })
        self.assertEqual(result["judgment"], "reject")

    def test_mock_escalate_medium(self):
        """中等置信度 → escalate"""
        result = self.client._mock_infer({
            "event_id": "evt-003",
            "trace_id": "tr-003",
            "event_type": "abnormal_posture",
            "priority": "P2",
            "confidence": 0.5,
        })
        self.assertEqual(result["judgment"], "escalate")

    def test_response_has_required_fields(self):
        """响应包含所有必需字段"""
        result = self.client._mock_infer({
            "event_id": "evt-004",
            "trace_id": "tr-004",
            "event_type": "fall_suspected",
            "priority": "P1",
            "confidence": 0.9,
        })
        required = ["event_id", "trace_id", "judgment", "confidence",
                     "advice", "latency_ms", "model_name", "model_version"]
        for field in required:
            self.assertIn(field, result, f"Missing field: {field}")

    def test_valid_judgment_values(self):
        """judgment 只取 confirm/reject/escalate"""
        for conf, pri in [(0.9, "P1"), (0.15, "P2"), (0.5, "P2")]:
            result = self.client._mock_infer({
                "event_id": "test",
                "trace_id": "test",
                "event_type": "fall_suspected",
                "priority": pri,
                "confidence": conf,
            })
            self.assertIn(result["judgment"], ["confirm", "reject", "escalate"])

    def test_advice_not_empty(self):
        """护理建议不能为空"""
        for event_type in ["fall_suspected", "seizure", "bed_leave",
                           "fall_prediction", "long_still", "abnormal_posture"]:
            for conf in [0.1, 0.5, 0.9]:
                result = self.client._mock_infer({
                    "event_id": "test",
                    "trace_id": "test",
                    "event_type": event_type,
                    "priority": "P2",
                    "confidence": conf,
                })
                self.assertTrue(len(result["advice"]) > 0,
                                f"Empty advice for {event_type} conf={conf}")


class TestSchemas(unittest.TestCase):

    def test_inference_request_parsing(self):
        payload = {
            "event_id": "evt-001",
            "trace_id": "tr-001",
            "event_type": "fall_suspected",
            "priority": "P1",
            "confidence": 0.85,
            "node_id": "EDGE-W01-B01",
        }
        req = InferenceRequest(**payload)
        self.assertEqual(req.event_id, "evt-001")
        self.assertEqual(req.priority, "P1")

    def test_inference_response_valid(self):
        resp = InferenceResponse(
            event_id="evt-001",
            trace_id="tr-001",
            judgment="confirm",
            confidence=0.85,
            advice="建议立即前往检查",
            latency_ms=45.2,
        )
        self.assertIn(resp.judgment, ["confirm", "reject", "escalate"])

    def test_envelope_parsing(self):
        env = MqttEnvelope(**{
            "message_id": "msg-1",
            "event_id": "evt-1",
            "trace_id": "tr-1",
            "payload": {"event_type": "fall_suspected"},
        })
        self.assertEqual(env.event_id, "evt-1")
        self.assertEqual(env.payload["event_type"], "fall_suspected")


if __name__ == "__main__":
    unittest.main()
