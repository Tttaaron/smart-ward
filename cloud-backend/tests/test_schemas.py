"""Pydantic 请求模型校验测试（对齐 docs/07 TC-101~118 的入参校验）"""

import unittest

from pydantic import ValidationError

from app.schemas import (
    AckRequest, ModelDeployRequest, EnvControlRequest, ShiftSummaryRequest,
    InjectionRequest,
)


class AckRequestTest(unittest.TestCase):
    def test_valid_actions_accepted(self):
        for action in ("acknowledge", "resolve", "false_positive", "escalate"):
            req = AckRequest(action=action, operator_id="nurse-01")
            self.assertEqual(req.action, action)

    def test_invalid_action_rejected(self):
        with self.assertRaises(ValidationError):
            AckRequest(action="delete", operator_id="nurse-01")

    def test_invalid_operator_role_rejected(self):
        with self.assertRaises(ValidationError):
            AckRequest(action="acknowledge", operator_id="nurse-01",
                       operator_role="doctor")

    def test_operator_id_required(self):
        with self.assertRaises(ValidationError):
            AckRequest(action="acknowledge")


class ModelDeployRequestTest(unittest.TestCase):
    def setUp(self):
        self.base = dict(
            model_name="shufflenetv2-sa", model_version="1.0.0-int4",
            artifact_url="http://models/fall.pt",
        )

    def test_valid_deploy_request(self):
        req = ModelDeployRequest(**self.base)
        self.assertEqual(req.runtime, "onnx")
        self.assertEqual(req.target_device, "cpu")

    def test_invalid_runtime_rejected(self):
        with self.assertRaises(ValidationError):
            ModelDeployRequest(**self.base, runtime="rknn")

    def test_invalid_target_device_rejected(self):
        with self.assertRaises(ValidationError):
            ModelDeployRequest(**self.base, target_device="cloud")

    def test_missing_artifact_url_rejected(self):
        with self.assertRaises(ValidationError):
            ModelDeployRequest(model_name="m", model_version="v")


class EnvControlRequestTest(unittest.TestCase):
    def test_valid_devices(self):
        for device in ("ac", "light", "fresh_air"):
            EnvControlRequest(node_id="N1", device=device, action="on")

    def test_invalid_device_rejected(self):
        with self.assertRaises(ValidationError):
            EnvControlRequest(node_id="N1", device="fan", action="on")

    def test_invalid_action_rejected(self):
        with self.assertRaises(ValidationError):
            EnvControlRequest(node_id="N1", device="light", action="toggle")


class ShiftSummaryRequestTest(unittest.TestCase):
    def test_valid_periods(self):
        for period in ("day", "evening", "night"):
            ShiftSummaryRequest(ward_id="W-01", shift_date="2026-08-10",
                                shift_period=period)

    def test_invalid_period_rejected(self):
        with self.assertRaises(ValidationError):
            ShiftSummaryRequest(ward_id="W-01", shift_date="2026-08-10",
                                shift_period="morning")


class InjectionRequestTest(unittest.TestCase):
    def test_valid_request(self):
        req = InjectionRequest(event_type="fall_suspected", priority="P1")
        self.assertEqual(req.ward_id, "W-01")
        self.assertEqual(req.confidence, 0.9)

    def test_invalid_priority_rejected(self):
        with self.assertRaises(ValidationError):
            InjectionRequest(priority="P9")

    def test_confidence_out_of_range_rejected(self):
        with self.assertRaises(ValidationError):
            InjectionRequest(confidence=1.5)


if __name__ == "__main__":
    unittest.main()
