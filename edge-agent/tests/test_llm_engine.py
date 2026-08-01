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


if __name__ == "__main__":
    unittest.main()
