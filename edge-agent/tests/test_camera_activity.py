"""mock 摄像头日常活动模拟测试

验证 CameraAdapter（mock 模式）输出与 yolo 模式同构的 activity entry：
- 默认姿态输出活动标签（label/since/switched/previous）
- 场景注入姿态变化时产生切换事件（switched=True + previous）
- 姿态稳定时活动保持、since 持续
- mock camera 活动可贯通 fusion 事件 details（与 yolo 链路一致）
"""

import os
import sys
import unittest
from types import SimpleNamespace

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from adapters.camera import CameraAdapter  # noqa: E402
from adapters.base import Observation, Quality  # noqa: E402
from scenario import ScenarioDriver, SceneState  # noqa: E402
from fusion import FusionEngine, InferenceResult  # noqa: E402


def make_observation(source_type, data, confidence=0.9):
    return Observation(
        source_type=source_type,
        data=data,
        quality=Quality(confidence=confidence, latency_ms=10, degraded=False),
    )


def make_driver(scene_types):
    """构造带指定场景的驱动（scenes 在 __init__ 中按环境变量构造，需显式设置）"""
    driver = ScenarioDriver()
    driver.scenes = {
        st: SceneState(scene_type=st, duration_ticks=5) for st in scene_types
    }
    return driver


class MockCameraActivityTest(unittest.TestCase):
    def setUp(self):
        self.cam = CameraAdapter("EDGE-W01-B01", "B01")

    def _activity(self, cam=None):
        cam = cam or self.cam
        obs = cam.read()
        self.assertEqual(obs.source_type, "camera")
        return obs.data["activity"]

    def test_default_activity_from_posture(self):
        """默认姿态 sitting -> 活动 sit，字段与 yolo 同构"""
        entry = self._activity()
        self.assertEqual(entry["label"], "sit")
        self.assertFalse(entry["switched"])
        self.assertIsNotNone(entry["since"])
        self.assertIn("previous", entry)

    def test_activity_switches_on_scene_posture_change(self):
        """场景注入 falling 姿态 -> 活动 fall，切换事件产生"""
        driver = make_driver(["fall_suspected"])
        driver.tick()  # 激活 fall_suspected 场景（phase=started -> falling）
        cam = CameraAdapter("EDGE-W01-B01", "B01", scenario_driver=driver)
        entry = self._activity(cam)
        self.assertEqual(entry["label"], "fall")
        self.assertTrue(entry["switched"])
        self.assertEqual(entry["previous"], "sit")

    def test_activity_stable_when_posture_stable(self):
        """连续读取同姿态 -> 活动不变、switched=False、since 不刷新"""
        e1 = self._activity()
        e2 = self._activity()
        self.assertEqual(e1["label"], e2["label"])
        self.assertFalse(e2["switched"])
        # since 为活动起始时间，稳定持续
        self.assertLessEqual(e1["since"], e2["since"])

    def test_posture_activity_mapping(self):
        """姿态映射表覆盖主要姿态"""
        cases = {
            "standing": "stand",
            "lying": "lie",
            "lying_edge": "lie",
            "curled": "bend",
            "falling": "fall",
            "unknown": "unknown",
        }
        for posture, expect in cases.items():
            with self.subTest(posture=posture):
                fake_scenario = SimpleNamespace(get_camera_state=lambda p=posture: {
                    "presence": True, "person_count": 1, "posture": p,
                    "fall_score": 0.0, "tremor_score": 0.0,
                })
                cam = CameraAdapter("EDGE-W01-B01", "B01",
                                    scenario_driver=fake_scenario)
                self.assertEqual(cam.read().data["activity"]["label"], expect)

    def test_mock_activity_passthrough_to_fusion_event(self):
        """mock camera 活动贯通融合事件 details（与 yolo 链路一致）"""
        driver = make_driver(["fall_suspected"])
        driver.tick()
        cam = CameraAdapter("EDGE-W01-B01", "B01", scenario_driver=driver)
        cam_obs = cam.read()
        bed_obs = make_observation("bed_sensor", {
            "occupied": False, "absence_seconds": 10})
        inf_result = InferenceResult(
            model_name="yolo-nano-pose", model_version="1.0.0-mock",
            confidence=0.85, inference_ms=45,
            predictions={"posture": "falling", "fall_score": 0.85,
                         "presence": True, "person_count": 1},
        )
        fusion = FusionEngine("W-01", "EDGE-W01-B01", "B01")
        events = fusion.fuse([cam_obs, bed_obs], inf_result)
        self.assertTrue(events)
        for event in events:
            self.assertEqual(event.details["activity"]["label"], "fall")
            self.assertTrue(event.details["activity"]["switched"])


if __name__ == "__main__":
    unittest.main()
