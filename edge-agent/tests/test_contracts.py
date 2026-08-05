"""云边协同推理契约测试：inference request/response JSON Schema 校验。

任务书要求：补齐 inference request/response JSON Schema 或等价的字段校验，
明确外层 envelope 与 payload 的 event_id、trace_id、judgment、confidence、
advice、latency_ms。契约文件位于 contracts/，云端 Pydantic 模型见
cloud-llm-service/app/schemas.py，两侧字段必须一致。
"""

import json
import os
import sys
import unittest

try:
    from jsonschema import Draft7Validator, RefResolver, ValidationError
except ImportError:
    Draft7Validator = None

CONTRACTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "contracts"))


def _load(name):
    with open(os.path.join(CONTRACTS_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


def _validator(schema):
    """构造带本地 $ref（envelope.json）解析的校验器。

    contracts/*.json 的 $id 使用 https://smart-ward/... 虚拟命名空间，
    需要把 envelope.json 注册进 store 避免真实网络请求。
    """
    envelope = _load("envelope.json")
    store = {envelope["$id"]: envelope}
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft7Validator(schema, resolver=resolver)


ENVELOPE_OK = {
    "message_id": "msg-001",
    "event_id": "evt-001",
    "schema_version": "v1",
    "occurred_at": "2026-08-05T08:30:00Z",
    "source": "edge:EDGE-W01-B01",
    "trace_id": "trace-001",
    "payload": {},
}


@unittest.skipIf(Draft7Validator is None, "jsonschema 未安装，跳过契约校验测试")
class InferenceRequestSchemaTest(unittest.TestCase):
    def setUp(self):
        self.schema = _load("inference_request.json")
        self.validator = _validator(self.schema)

    def test_valid_request_passes(self):
        message = {
            **ENVELOPE_OK,
            "payload": {
                "event_id": "evt-001",
                "trace_id": "trace-001",
                "request_mode": "cloud",
                "timeout_ms": 30000,
                "requested_at": "2026-08-05T08:30:00Z",
                "event_type": "fall_suspected",
                "priority": "P1",
                "confidence": 0.82,
                "ward_id": "W-01",
                "node_id": "EDGE-W01-B01",
                "bed_id": "B01",
                "model_name": "qwen2.5-1.5b-instruct-q4_k_m",
                "model_version": "1.0.0-int4",
                "details": {"behavior": {"action": "falling"}},
                "llm_prompt": None,
            },
        }
        self.assertTrue(self.validator.is_valid(message),
                        list(self.validator.iter_errors(message)))

    def test_payload_requires_event_id_trace_id_event_type(self):
        for missing in ("event_id", "trace_id", "event_type"):
            payload = {
                "event_id": "evt-001",
                "trace_id": "trace-001",
                "event_type": "fall_suspected",
            }
            payload.pop(missing)
            self.assertFalse(
                self.validator.is_valid({**ENVELOPE_OK, "payload": payload}),
                f"缺少 {missing} 应校验失败")

    def test_invalid_judgment_rejected_in_request_mode(self):
        payload = {
            "event_id": "evt-001",
            "trace_id": "trace-001",
            "event_type": "fall_suspected",
            "request_mode": "bad_mode",
        }
        self.assertFalse(self.validator.is_valid({**ENVELOPE_OK, "payload": payload}))


@unittest.skipIf(Draft7Validator is None, "jsonschema 未安装，跳过契约校验测试")
class InferenceResponseSchemaTest(unittest.TestCase):
    def setUp(self):
        self.schema = _load("inference_response.json")
        self.validator = _validator(self.schema)

    def test_valid_response_passes(self):
        message = {
            **ENVELOPE_OK,
            "payload": {
                "event_id": "evt-001",
                "trace_id": "trace-001",
                "judgment": "confirm",
                "confidence": 0.93,
                "advice": "请立即前往确认 B01 患者状态",
                "latency_ms": 812.5,
                "model_name": "qwen2.5-14b",
                "model_version": "awq-int4",
            },
        }
        self.assertTrue(self.validator.is_valid(message),
                        list(self.validator.iter_errors(message)))

    def test_response_requires_all_six_contract_fields(self):
        """缺任一验收字段不得进入成功路径（任务书硬要求）。"""
        required = ("event_id", "trace_id", "judgment", "confidence",
                    "advice", "latency_ms")
        base = {
            "event_id": "evt-001",
            "trace_id": "trace-001",
            "judgment": "confirm",
            "confidence": 0.9,
            "advice": "建议复核",
            "latency_ms": 100.0,
        }
        for field in required:
            payload = dict(base)
            payload.pop(field)
            self.assertFalse(
                self.validator.is_valid({**ENVELOPE_OK, "payload": payload}),
                f"响应缺少 {field} 应校验失败")

    def test_invalid_judgment_rejected(self):
        payload = {
            "event_id": "evt-001",
            "trace_id": "trace-001",
            "judgment": "maybe",
            "confidence": 0.9,
            "advice": "x",
            "latency_ms": 1.0,
        }
        self.assertFalse(self.validator.is_valid({**ENVELOPE_OK, "payload": payload}))


@unittest.skipIf(Draft7Validator is None, "jsonschema 未安装，跳过契约校验测试")
class CloudSchemaConsistencyTest(unittest.TestCase):
    """JSON Schema 与 cloud-llm-service Pydantic 模型字段一致性。"""

    def test_request_fields_match_cloud_pydantic_model(self):
        import importlib.util
        schemas_py = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..",
            "cloud-llm-service", "app", "schemas.py"))
        if not os.path.exists(schemas_py):
            self.skipTest("cloud-llm-service/app/schemas.py 不存在")
        spec = importlib.util.spec_from_file_location("cloud_schemas", schemas_py)
        module = importlib.util.module_from_spec(spec)
        sys.modules["cloud_schemas"] = module
        spec.loader.exec_module(module)

        request_schema = _load("inference_request.json")
        schema_fields = set(request_schema["properties"]["payload"]["properties"])
        model_fields = set(module.InferenceRequest.model_fields)
        self.assertTrue(schema_fields.issubset(model_fields),
                        f"Schema 字段超出 Pydantic 模型: {schema_fields - model_fields}")

        response_schema = _load("inference_response.json")
        resp_fields = set(response_schema["properties"]["payload"]["properties"])
        model_resp = set(module.InferenceResponse.model_fields)
        self.assertTrue(resp_fields.issubset(model_resp),
                        f"Response Schema 字段超出 Pydantic 模型: {resp_fields - model_resp}")


if __name__ == "__main__":
    unittest.main()
