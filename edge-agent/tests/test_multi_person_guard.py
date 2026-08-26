"""多人在场防护测试

一床一摄像头假设下，画面出现多人（家属/护工进入）时，相机行为类事件
应衰减置信度并打标存疑；bed_leave 等床垫主导规则不受影响。

使用 unittest.TestCase 以便 `python -m unittest discover` 自动发现。
"""

import os
import sys
import unittest
from unittest import mock

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
SRC_DIR = os.path.abspath(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from adapters.base import Observation, Quality
from inference import InferenceResult
from fusion import FusionEngine


def make_observation(source_type, data):
    return Observation(
        source_type=source_type,
        data=data,
        quality=Quality(confidence=0.9, latency_ms=10, degraded=False),
    )


def make_camera_obs(person_count=None, **extra):
    data = {
        "posture": "curled",
        "tremor_score": 0.8,
        "position_duration": 400,
        "presence": True,
    }
    if person_count is not None:
        data["person_count"] = person_count
    data.update(extra)
    return make_observation("camera", data)


def make_inference(behavior_track_count=None):
    predictions = {}
    if behavior_track_count is not None:
        predictions["behavior"] = {"track_count": behavior_track_count}
    return InferenceResult(
        model_name="yolo11n-pose", model_version="test",
        confidence=0.9, inference_ms=5, predictions=predictions,
    )


def build_engine(env_overrides=None) -> FusionEngine:
    env = {"EVENT_DEDUPE_SECONDS": "0", "LONG_STILL_SECONDS": "300"}
    env.update(env_overrides or {})
    with mock.patch.dict(os.environ, env):
        return FusionEngine("W-01", "EDGE-W01-B02", "B02")


class MultiPersonGuardTest(unittest.TestCase):
    """person_count>1 时相机行为类事件衰减 + 打标"""

    def test_multi_person_penalizes_seizure(self):
        engine = build_engine()
        events = engine.fuse([make_camera_obs(person_count=2)])
        seizure = [e for e in events if e.event_type == "seizure"]
        self.assertEqual(len(seizure), 1)
        event = seizure[0]
        # tremor_score=0.8，衰减 0.7 -> 0.56
        self.assertEqual(event.confidence, 0.56)
        self.assertIn("multi_person=2:confidence x0.7", event.rule_hits)
        self.assertEqual(event.details["multi_person"]["person_count"], 2)
        self.assertEqual(event.details["multi_person"]["original_confidence"], 0.8)

    def test_single_person_untouched(self):
        engine = build_engine()
        events = engine.fuse([make_camera_obs(person_count=1)])
        seizure = [e for e in events if e.event_type == "seizure"]
        self.assertEqual(len(seizure), 1)
        self.assertEqual(seizure[0].confidence, 0.8)
        self.assertNotIn("multi_person", seizure[0].details)

    def test_missing_count_with_behavior_fallback(self):
        """cam.data 无 person_count 时回退 behavior.track_count"""
        engine = build_engine()
        events = engine.fuse(
            [make_camera_obs(person_count=None)],
            inference=make_inference(behavior_track_count=3),
        )
        seizure = [e for e in events if e.event_type == "seizure"]
        self.assertEqual(len(seizure), 1)
        self.assertEqual(seizure[0].details["multi_person"]["person_count"], 3)

    def test_bed_leave_not_guarded(self):
        """床垫主导的离床事件不衰减（访客在场恰是离床高发场景）"""
        engine = build_engine({"BED_LEAVE_THRESHOLD": "30"})
        cam = make_camera_obs(person_count=2)
        bed = make_observation("bed_sensor", {"occupied": False, "absence_seconds": 60})
        events = engine.fuse([cam, bed])
        leaves = [e for e in events if e.event_type == "bed_leave"]
        self.assertEqual(len(leaves), 1)
        self.assertEqual(leaves[0].confidence, 0.85)
        self.assertNotIn("multi_person", leaves[0].details)

    def test_guard_disabled(self):
        engine = build_engine({"MULTI_PERSON_GUARD": "false"})
        events = engine.fuse([make_camera_obs(person_count=2)])
        seizure = [e for e in events if e.event_type == "seizure"]
        self.assertEqual(len(seizure), 1)
        self.assertEqual(seizure[0].confidence, 0.8)
        self.assertNotIn("multi_person", seizure[0].details)

    def test_custom_penalty(self):
        engine = build_engine({"MULTI_PERSON_CONF_PENALTY": "0.5"})
        events = engine.fuse([make_camera_obs(person_count=4)])
        seizure = [e for e in events if e.event_type == "seizure"]
        self.assertEqual(seizure[0].confidence, 0.4)
        self.assertEqual(seizure[0].details["multi_person"]["penalty"], 0.5)


if __name__ == "__main__":
    unittest.main()
