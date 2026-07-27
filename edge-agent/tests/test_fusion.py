"""事件融合引擎冒烟测试

验证 FusionEngine 对各类场景的识别能力。
覆盖 contracts/safety_event.json 中的主要 event_type。

使用 unittest.TestCase 以便 `python -m unittest discover` 能自动发现，
同时保留 `python test_fusion.py` 直接运行的能力。
"""

import os
import sys
import unittest

# 将 src/ 加入 sys.path，使 src 下的扁平导入（from adapters.base import ...）生效
SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
SRC_DIR = os.path.abspath(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from adapters.base import Observation, Quality
from adapters.camera import CameraAdapter
from adapters.bed_sensor import BedSensorAdapter
from adapters.infusion import InfusionAdapter
from adapters.environment import EnvironmentAdapter
from inference import InferenceEngine, InferenceResult
from fusion import FusionEngine
from scenario import ScenarioDriver


def make_observation(source_type, data, confidence=0.9):
    return Observation(
        source_type=source_type,
        data=data,
        quality=Quality(confidence=confidence, latency_ms=10, degraded=False),
    )


class AdaptersSmokeTest(unittest.TestCase):
    """适配器冒烟测试"""

    def test_adapters_smoke(self):
        """read() 应返回合法 Observation"""
        cam = CameraAdapter("EDGE-W01-B01", "B01")
        obs = cam.read()
        self.assertEqual(obs.source_type, "camera")
        self.assertIn("presence", obs.data)
        self.assertIn("posture", obs.data)

        bed = BedSensorAdapter("EDGE-W01-B01", "B01")
        obs = bed.read()
        self.assertEqual(obs.source_type, "bed_sensor")
        self.assertIn("occupied", obs.data)

        inf = InfusionAdapter("EDGE-W01-B01", "B01")
        obs = inf.read()
        self.assertEqual(obs.source_type, "infusion")
        self.assertIn("anomaly", obs.data)

        env = EnvironmentAdapter("EDGE-W01-B01", "B01")
        obs = env.read()
        self.assertEqual(obs.source_type, "environment")
        self.assertIn("temperature", obs.data)


class InferenceEngineTest(unittest.TestCase):
    """推理引擎输出字段测试"""

    def test_inference_engine_output_fields(self):
        """推理引擎输出应包含方案书 §3.3 验收要求的字段"""
        engine = InferenceEngine()
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "sitting", "fall_score": 0.0
        })
        result = engine.run(cam)
        d = result.to_dict()
        # 对齐契约 contracts/safety_event.json 的 evidence_refs（复数）字段
        for field in ["model_name", "model_version", "confidence", "inference_ms", "evidence_refs"]:
            self.assertIn(field, d, f"推理输出缺失字段: {field}")


class FusionEngineTest(unittest.TestCase):
    """融合引擎规则识别测试"""

    def _make_fusion(self):
        """构造一个关闭去重的融合引擎，便于测试"""
        fusion = FusionEngine("W-01", "EDGE-W01-B01", "B01")
        fusion.dedupe_seconds = 0  # 测试时关闭去重
        return fusion

    def test_fall_suspected(self):
        """跌倒疑似：摄像头 posture=falling + fall_score>0.5 + 床位离床"""
        fusion = self._make_fusion()
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "falling", "fall_score": 0.85
        })
        bed = make_observation("bed_sensor", {"occupied": False, "absence_seconds": 10})
        inf_result = InferenceResult(
            model_name="yolo-nano-pose", model_version="1.0.0-mock",
            confidence=0.85, inference_ms=45,
            predictions={"posture": "falling", "fall_score": 0.85, "presence": True, "person_count": 1},
        )
        events = fusion.fuse([cam, bed], inf_result)
        fall_events = [e for e in events if e.event_type == "fall_suspected"]
        self.assertEqual(len(fall_events), 1, f"应触发 1 个 fall_suspected，实际 {len(fall_events)}")
        self.assertEqual(fall_events[0].priority, "P1")
        self.assertEqual(fall_events[0].state, "new")
        self.assertEqual(fall_events[0].model["model_name"], "yolo-nano-pose")

    def test_bed_leave(self):
        """离床：床位 absence_seconds 超阈值"""
        fusion = self._make_fusion()
        fusion.BED_LEAVE_THRESHOLD = 30
        bed = make_observation("bed_sensor", {"occupied": False, "absence_seconds": 45})
        events = fusion.fuse([bed])
        leave_events = [e for e in events if e.event_type == "bed_leave"]
        self.assertEqual(len(leave_events), 1, f"应触发 1 个 bed_leave，实际 {len(leave_events)}")
        self.assertEqual(leave_events[0].priority, "P2")
        self.assertEqual(leave_events[0].details["absence_seconds"], 45)

    def test_bed_leave_below_threshold(self):
        """离床未超阈值：不应触发"""
        fusion = self._make_fusion()
        fusion.BED_LEAVE_THRESHOLD = 30
        bed = make_observation("bed_sensor", {"occupied": False, "absence_seconds": 10})
        events = fusion.fuse([bed])
        leave_events = [e for e in events if e.event_type == "bed_leave"]
        self.assertEqual(len(leave_events), 0, f"未超阈值不应触发，实际 {len(leave_events)}")

    def test_infusion_anomaly(self):
        """输液异常：anomaly != normal"""
        fusion = self._make_fusion()
        inf = make_observation("infusion", {
            "flow_rate": 100.0, "volume_pct": 3.0, "remaining_minutes": 5, "anomaly": "low_volume"
        })
        events = fusion.fuse([inf])
        inf_events = [e for e in events if e.event_type == "infusion_anomaly"]
        self.assertEqual(len(inf_events), 1, f"应触发 1 个 infusion_anomaly，实际 {len(inf_events)}")
        self.assertEqual(inf_events[0].priority, "P2")
        self.assertEqual(inf_events[0].details["anomaly"], "low_volume")

    def test_environment_anomaly(self):
        """环境异常：温度/CO₂/光照超阈值"""
        fusion = self._make_fusion()
        fusion.TEMP_HIGH = 29.0
        fusion.CO2_HIGH = 1000
        fusion.LIGHT_LOW = 50
        env = make_observation("environment", {
            "temperature": 29.5, "humidity": 78.0, "light": 40, "co2": 1250,
            "door_open": False, "air_quality": "bad"
        })
        events = fusion.fuse([env])
        env_events = [e for e in events if e.event_type == "environment_anomaly"]
        self.assertEqual(len(env_events), 1, f"应触发 1 个 environment_anomaly，实际 {len(env_events)}")
        self.assertEqual(env_events[0].priority, "P3")
        # 应命中温度、CO₂、光照三条规则
        self.assertEqual(len(env_events[0].rule_hits), 3)

    def test_dedupe(self):
        """同类事件去重：dedupe_seconds 内不应重复触发"""
        fusion = self._make_fusion()
        fusion.dedupe_seconds = 60  # 60 秒去重
        inf = make_observation("infusion", {
            "flow_rate": 100.0, "volume_pct": 3.0, "remaining_minutes": 5, "anomaly": "low_volume"
        })
        events1 = fusion.fuse([inf])
        events2 = fusion.fuse([inf])  # 立即第二次，应被去重
        self.assertEqual(len(events1), 1)
        self.assertEqual(len(events2), 0, f"去重期内不应触发，实际 {len(events2)}")

    def test_event_payload_matches_contract(self):
        """事件 payload 结构应符合 contracts/safety_event.json 的必需字段"""
        fusion = self._make_fusion()
        inf = make_observation("infusion", {
            "flow_rate": 100.0, "volume_pct": 3.0, "remaining_minutes": 5, "anomaly": "low_volume"
        })
        events = fusion.fuse([inf])
        self.assertEqual(len(events), 1)
        payload = events[0].to_dict()
        required = ["event_id", "ward_id", "node_id", "bed_id", "event_type", "priority",
                    "state", "occurred_at", "detected_at", "confidence", "model", "evidence_refs"]
        for field in required:
            self.assertIn(field, payload, f"缺失契约必需字段: {field}")
        self.assertIn("model_name", payload["model"])
        self.assertIn("model_version", payload["model"])
        self.assertIn("inference_ms", payload["model"])

    def test_fall_prediction(self):
        """坠床预警：床位占床 + 姿态=lying_edge + fall_score 超阈值"""
        fusion = self._make_fusion()
        fusion.BED_EDGE_FALL_SCORE = 0.6
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "lying_edge", "fall_score": 0.75,
            "tremor_score": 0.0, "position_duration": 0,
        })
        bed = make_observation("bed_sensor", {"occupied": True, "absence_seconds": 0})
        events = fusion.fuse([cam, bed])
        pred_events = [e for e in events if e.event_type == "fall_prediction"]
        self.assertEqual(len(pred_events), 1, f"应触发 1 个 fall_prediction，实际 {len(pred_events)}")
        self.assertEqual(pred_events[0].priority, "P1")
        self.assertIn("posture=lying_edge", pred_events[0].rule_hits)

    def test_fall_prediction_below_threshold(self):
        """fall_score 低于阈值不应触发"""
        fusion = self._make_fusion()
        fusion.BED_EDGE_FALL_SCORE = 0.6
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "lying_edge", "fall_score": 0.4,
            "tremor_score": 0.0, "position_duration": 0,
        })
        bed = make_observation("bed_sensor", {"occupied": True, "absence_seconds": 0})
        events = fusion.fuse([cam, bed])
        pred_events = [e for e in events if e.event_type == "fall_prediction"]
        self.assertEqual(len(pred_events), 0, f"低于阈值不应触发，实际 {len(pred_events)}")

    def test_long_still(self):
        """长时间静止：position_duration 超阈值"""
        fusion = self._make_fusion()
        fusion.LONG_STILL_SECONDS = 300  # 5 分钟
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "sitting",
            "fall_score": 0.0, "tremor_score": 0.0, "position_duration": 360,
        })
        events = fusion.fuse([cam])
        still_events = [e for e in events if e.event_type == "long_still"]
        self.assertEqual(len(still_events), 1, f"应触发 1 个 long_still，实际 {len(still_events)}")
        self.assertEqual(still_events[0].priority, "P2")
        self.assertEqual(still_events[0].details["position_duration"], 360)

    def test_abnormal_posture(self):
        """异常体态：posture 命中 curled/leaning/grabbing_chest"""
        fusion = self._make_fusion()
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "grabbing_chest",
            "fall_score": 0.0, "tremor_score": 0.0, "position_duration": 10,
        })
        events = fusion.fuse([cam])
        abn_events = [e for e in events if e.event_type == "abnormal_posture"]
        self.assertEqual(len(abn_events), 1, f"应触发 1 个 abnormal_posture，实际 {len(abn_events)}")
        self.assertEqual(abn_events[0].priority, "P2")
        self.assertEqual(abn_events[0].details["posture"], "grabbing_chest")

    def test_seizure(self):
        """抽搐检测：tremor_score 超阈值"""
        fusion = self._make_fusion()
        fusion.TREMOR_THRESHOLD = 0.6
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "seizing",
            "fall_score": 0.0, "tremor_score": 0.85, "position_duration": 5,
        })
        events = fusion.fuse([cam])
        seizure_events = [e for e in events if e.event_type == "seizure"]
        self.assertEqual(len(seizure_events), 1, f"应触发 1 个 seizure，实际 {len(seizure_events)}")
        self.assertEqual(seizure_events[0].priority, "P1")
        self.assertEqual(seizure_events[0].details["tremor_score"], 0.85)

    def test_bedsore_risk(self):
        """压疮预防：position_duration 超阈值（默认 2 小时）"""
        fusion = self._make_fusion()
        fusion.BEDSORE_DURATION = 7200  # 2 小时
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "lying",
            "fall_score": 0.0, "tremor_score": 0.0, "position_duration": 9000,
        })
        events = fusion.fuse([cam])
        bedsore_events = [e for e in events if e.event_type == "bedsore_risk"]
        self.assertEqual(len(bedsore_events), 1, f"应触发 1 个 bedsore_risk，实际 {len(bedsore_events)}")
        self.assertEqual(bedsore_events[0].priority, "P3")
        self.assertEqual(bedsore_events[0].details["position_duration"], 9000)

    def test_device_fault(self):
        """设备故障：传感器 quality.degraded 持续超阈值"""
        fusion = self._make_fusion()
        fusion.DEVICE_FAULT_DEGRADED_SECONDS = 0  # 测试时立即触发
        cam = Observation(
            source_type="camera",
            data={"presence": True},
            quality=Quality(confidence=0.6, latency_ms=45, degraded=True),
        )
        events = fusion.fuse([cam])
        fault_events = [e for e in events if e.event_type == "device_fault"]
        self.assertEqual(len(fault_events), 1, f"应触发 1 个 device_fault，实际 {len(fault_events)}")
        self.assertEqual(fault_events[0].priority, "P3")
        self.assertIn("camera", fault_events[0].details["degraded_sources"])


class ScenarioDriverTest(unittest.TestCase):
    """场景驱动器状态机测试"""

    def test_scenario_driver_advance(self):
        """场景驱动器状态机推进"""
        os.environ["SCENARIO_PROFILE"] = "fall_suspected"
        os.environ["TICK_SECONDS"] = "3"
        driver = ScenarioDriver()
        self.assertIn("fall_suspected", driver.scene_types)

        # tick 1: 启动
        driver.tick()
        self.assertIsNotNone(driver._current_scene)
        self.assertEqual(driver._current_scene.phase, "started")

        # tick 2: 进入 sustained
        driver.tick()
        self.assertEqual(driver._current_scene.phase, "sustained")
        cam_state = driver.get_camera_state()
        self.assertEqual(cam_state["posture"], "falling")

        # 持续到 duration_ticks 后进入 recovering
        # fall_suspected duration_ticks=3：tick2 后还需 (duration_ticks-1)=2 次到达 recovering
        sc = driver._current_scene
        for _ in range(sc.duration_ticks - 1):
            driver.tick()
        self.assertEqual(sc.phase, "recovering")

        # 再 tick 一次后场景结束，_current_scene 被清空
        driver.tick()
        self.assertIsNone(driver._current_scene)


if __name__ == "__main__":
    unittest.main(verbosity=2)
