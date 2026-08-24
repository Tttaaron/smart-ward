"""LLM runtime profile and model metadata regression tests."""

import os
import sys
import unittest
from unittest.mock import patch

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from llm_engine import LLMEngine, _env_bool


class LLMEngineConfigTest(unittest.TestCase):
    def test_compact_model_metadata_is_inferred(self):
        with patch.dict(os.environ, {
            "LLM_MODE": "mock",
            "LLM_PROFILE": "compact",
            "LLM_MODEL_PATH": "/app/models/qwen2.5-0.5b-gguf/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        }, clear=False):
            engine = LLMEngine()

        self.assertEqual(engine.MODEL_NAME, "qwen2.5-0.5b-instruct")
        self.assertEqual(engine.profile, "compact")
        self.assertEqual(engine.n_ctx, 512)
        self.assertEqual(engine.n_batch, 128)
        self.assertFalse(engine.use_mlock)

    def test_explicit_model_name_overrides_inference(self):
        with patch.dict(os.environ, {
            "LLM_MODE": "mock",
            "LLM_MODEL_PATH": "/tmp/qwen2.5-0.5b-instruct-q4_k_m.gguf",
            "LLM_MODEL_NAME": "custom-edge-model",
        }, clear=False):
            engine = LLMEngine()

        self.assertEqual(engine.MODEL_NAME, "custom-edge-model")

    def test_env_bool_has_strict_values(self):
        with patch.dict(os.environ, {"LLM_USE_MMAP": "false"}, clear=False):
            self.assertFalse(_env_bool("LLM_USE_MMAP", True))
        with patch.dict(os.environ, {"LLM_USE_MMAP": "yes"}, clear=False):
            self.assertTrue(_env_bool("LLM_USE_MMAP", False))


class LLMEngineSwitchTest(unittest.TestCase):
    """运行时模型切换（蒸馏学生模型下发）"""

    def setUp(self):
        with patch.dict(os.environ, {"LLM_MODE": "mock"}, clear=False):
            self.engine = LLMEngine()

    def test_switch_mock_updates_metadata(self):
        ok = self.engine.switch_model(
            "/app/models/qwen2.5-1.5b-ward-distilled/qwen2.5-1.5b-ward-q4_k_m.gguf",
            model_name="qwen2.5-1.5b-ward", model_version="distilled-v2-q4_k_m")
        self.assertTrue(ok)
        self.assertEqual(self.engine.MODEL_NAME, "qwen2.5-1.5b-ward")
        self.assertEqual(self.engine.MODEL_VERSION, "distilled-v2-q4_k_m")
        self.assertIn("qwen2.5-1.5b-ward", self.engine.model_path)

    def test_switch_infers_name_from_path(self):
        self.engine.switch_model("/app/models/qwen2.5-0.5b-instruct-q4_k_m.gguf")
        self.assertEqual(self.engine.MODEL_NAME, "qwen2.5-0.5b-instruct")

    def test_rollback_restores_previous(self):
        orig_name = self.engine.MODEL_NAME
        orig_version = self.engine.MODEL_VERSION
        self.engine.switch_model("/app/models/ward.gguf",
                                 model_name="qwen2.5-1.5b-ward", model_version="v2")
        self.assertTrue(self.engine.rollback())
        self.assertEqual(self.engine.MODEL_NAME, orig_name)
        self.assertEqual(self.engine.MODEL_VERSION, orig_version)

    def test_rollback_without_previous_returns_false(self):
        self.assertFalse(self.engine.rollback())

    def test_switch_real_missing_file_keeps_current(self):
        # 强制 real 模式：文件不存在 -> 返回 False，元数据不变
        self.engine.mode = "real"
        before_name = self.engine.MODEL_NAME
        ok = self.engine.switch_model("/no/such/file.gguf",
                                      model_name="qwen2.5-1.5b-ward")
        self.assertFalse(ok)
        self.assertEqual(self.engine.MODEL_NAME, before_name)


if __name__ == "__main__":
    unittest.main()
