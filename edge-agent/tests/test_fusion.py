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
from adapters.environment import EnvironmentAdapter
from inference import InferenceEngine, InferenceResult
from fusion import FusionEngine
from behavior import BehaviorAnalyzer
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

    def test_inference_predictions_cover_all_fusion_fields(self):
        """predictions 应覆盖 fusion 所有规则用到的字段

        覆盖：presence/person_count/posture/fall_score/tremor_score/
        position_duration/pose_keypoints/bbox
        """
        engine = InferenceEngine()
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "seizing",
            "fall_score": 0.0, "tremor_score": 0.85,
            "position_duration": 5, "pose_keypoints": [[0.1, 0.2, 0.9]],
            "bbox": [0.3, 0.4, 0.2, 0.5],
        })
        result = engine.run(cam)
        p = result.predictions
        for field in ["presence", "person_count", "posture", "fall_score",
                      "tremor_score", "position_duration", "pose_keypoints", "bbox"]:
            self.assertIn(field, p, f"predictions 缺失字段: {field}")
        self.assertEqual(p["tremor_score"], 0.85)
        self.assertEqual(p["position_duration"], 5)

    def test_inference_evidence_refs_for_high_risk(self):
        """高风险事件（seizing）应在 evidence_refs 附加脱敏截图指针"""
        engine = InferenceEngine()
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "seizing",
            "fall_score": 0.0, "tremor_score": 0.85,
            "pose_keypoints": [[0.1, 0.2, 0.9]],
        })
        result = engine.run(cam)
        # seizing 是高风险，应有 image + pose_keypoints 两个证据
        kinds = [e["kind"] for e in result.evidence_refs]
        self.assertIn("image", kinds, "高风险事件应附加脱敏截图指针")
        # 证据引用结构应符合契约
        for ref in result.evidence_refs:
            self.assertIn("kind", ref)
            self.assertIn("ref", ref)
            self.assertIn("taken_at", ref)

    def test_inference_evidence_refs_empty_for_normal(self):
        """正常坐姿无 pose_keypoints 时 evidence_refs 应为空"""
        engine = InferenceEngine()
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "sitting",
            "fall_score": 0.0, "tremor_score": 0.0, "pose_keypoints": [],
        })
        result = engine.run(cam)
        self.assertEqual(result.evidence_refs, [])

    def test_model_load_and_rollback(self):
        """模型版本管理：load_model 切换版本，rollback 回退"""
        engine = InferenceEngine()
        original_version = engine.model_version
        self.assertEqual(engine.model_status, "ok")

        # 部署新版本
        ok = engine.load_model("yolo-nano-pose", "1.0.0-int8")
        self.assertTrue(ok)
        self.assertEqual(engine.model_name, "yolo-nano-pose")
        self.assertEqual(engine.model_version, "1.0.0-int8")

        # 回滚到上一版本
        ok = engine.rollback()
        self.assertTrue(ok)
        self.assertEqual(engine.model_version, original_version)

        # 无更早版本可回滚时返回 False
        ok = engine.rollback()
        self.assertFalse(ok)

    def test_behavior_summary_survives_inference_and_fusion(self):
        """真实视觉管线摘要应进入安全事件，供 LLM 使用。"""
        analyzer = BehaviorAnalyzer(history_size=8)
        analyzer.update(
            [{"track_id": 7, "bbox": [0.4, 0.1, 0.1, 0.55], "confidence": 0.95}],
            timestamp="2026-08-02T08:30:00Z",
        )
        behavior = analyzer.update(
            [{"track_id": 7, "bbox": [0.3, 0.55, 0.45, 0.16], "confidence": 0.94}],
            timestamp="2026-08-02T08:30:01Z",
        )
        camera = make_observation("camera", {
            "presence": True,
            "person_count": 1,
            "posture": behavior["posture"],
            "fall_score": behavior["fall_score"],
            "bbox": behavior["bbox"],
            "behavior": behavior,
        })
        bed = make_observation("bed_sensor", {"occupied": False, "absence_seconds": 7})
        result = InferenceEngine().run(camera)
        events = FusionEngine("W-01", "EDGE-W01-B01", "B01").fuse([camera, bed], result)
        fall_events = [event for event in events if event.event_type == "fall_suspected"]
        self.assertEqual(len(fall_events), 1)
        self.assertEqual(fall_events[0].details["behavior"]["track_id"], 7)
        self.assertEqual(
            fall_events[0].details["behavior"]["posture_sequence"],
            ["standing", "lying"],
        )


class FusionEngineTest(unittest.TestCase):
    """融合引擎规则识别测试"""

    def _make_fusion(self):
        """构造一个关闭去重的融合引擎，便于测试

        同时把夜间时段配置为空（START==END），使 `_is_night()` 恒为 False，
        避免测试在 22:00~06:00 之间运行时 bed_leave 被升级为 night_wandering
        导致断言失败（时间敏感测试问题）。
        """
        fusion = FusionEngine("W-01", "EDGE-W01-B01", "B01")
        fusion.dedupe_seconds = 0  # 测试时关闭去重
        fusion.NIGHT_WANDLING_START = fusion.NIGHT_WANDLING_END = 0  # 禁用夜间判定
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

    def test_activity_passthrough_to_event_details(self):
        """活动识别结果应随事件 details 上报（activity_tracker → observation → event）"""
        fusion = self._make_fusion()
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "falling", "fall_score": 0.85,
            "activity": {"label": "walking", "switched": True, "previous": "sleeping", "since": 12.5},
        })
        bed = make_observation("bed_sensor", {"occupied": False, "absence_seconds": 10})
        inf_result = InferenceResult(
            model_name="yolo-nano-pose", model_version="1.0.0-mock",
            confidence=0.85, inference_ms=45,
            predictions={"posture": "falling", "fall_score": 0.85, "presence": True, "person_count": 1},
        )
        events = fusion.fuse([cam, bed], inf_result)
        self.assertTrue(events, "应至少触发一个事件")
        for event in events:
            self.assertEqual(event.details["activity"]["label"], "walking")
            self.assertTrue(event.details["activity"]["switched"])
            self.assertEqual(event.details["activity"]["previous"], "sleeping")

    def test_no_activity_keeps_details_unchanged(self):
        """摄像头无 activity 字段时，事件 details 不应被污染"""
        fusion = self._make_fusion()
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "falling", "fall_score": 0.85,
        })
        bed = make_observation("bed_sensor", {"occupied": False, "absence_seconds": 10})
        inf_result = InferenceResult(
            model_name="yolo-nano-pose", model_version="1.0.0-mock",
            confidence=0.85, inference_ms=45,
            predictions={"posture": "falling", "fall_score": 0.85, "presence": True, "person_count": 1},
        )
        events = fusion.fuse([cam, bed], inf_result)
        fall_events = [e for e in events if e.event_type == "fall_suspected"]
        self.assertEqual(len(fall_events), 1)
        self.assertNotIn("activity", fall_events[0].details)

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

    def test_bed_leave_camera_confirmed(self):
        """离床双源一致：床垫离床 + bbox 中心在床区外 -> 高置信 0.92"""
        fusion = self._make_fusion()
        fusion.BED_LEAVE_THRESHOLD = 30
        # 床区多边形：左上(0.2,0.3) 右上(0.8,0.3) 右下(0.8,0.8) 左下(0.2,0.8)
        fusion.BED_REGION_POLYGON = [(0.2, 0.3), (0.8, 0.3), (0.8, 0.8), (0.2, 0.8)]
        # bbox=[x,y,w,h]，中心点 (0.9, 0.4) 落在床区外（人已离床）
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "standing",
            "fall_score": 0.0, "bbox": [0.85, 0.3, 0.1, 0.2],  # 中心 (0.9, 0.4)
        })
        bed = make_observation("bed_sensor", {"occupied": False, "absence_seconds": 45})
        events = fusion.fuse([bed, cam])
        leave_events = [e for e in events if e.event_type == "bed_leave"]
        self.assertEqual(len(leave_events), 1)
        self.assertAlmostEqual(leave_events[0].confidence, 0.92, places=2)
        self.assertIn("camera_bbox_outside_bed_region", leave_events[0].rule_hits)
        self.assertEqual(leave_events[0].details["cam_cross_check"], "confirmed")

    def test_bed_leave_camera_disputed(self):
        """床垫误报：床垫报离床但 bbox 中心在床区内 -> 低置信 0.5"""
        fusion = self._make_fusion()
        fusion.BED_LEAVE_THRESHOLD = 30
        fusion.BED_REGION_POLYGON = [(0.2, 0.3), (0.8, 0.3), (0.8, 0.8), (0.2, 0.8)]
        # bbox 中心 (0.5, 0.5) 落在床区内（人其实还在床上，床垫可能误报）
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "sitting",
            "fall_score": 0.0, "bbox": [0.4, 0.4, 0.2, 0.2],  # 中心 (0.5, 0.5)
        })
        bed = make_observation("bed_sensor", {"occupied": False, "absence_seconds": 45})
        events = fusion.fuse([bed, cam])
        leave_events = [e for e in events if e.event_type == "bed_leave"]
        self.assertEqual(len(leave_events), 1)
        self.assertAlmostEqual(leave_events[0].confidence, 0.50, places=2)
        self.assertIn("camera_bbox_inside_bed_region", leave_events[0].rule_hits)
        self.assertEqual(leave_events[0].details["cam_cross_check"], "disputed")

    def test_bed_leave_no_polygon_fallback(self):
        """未配床区多边形：退化为纯床垫判定，置信度保持 0.85（向后兼容）"""
        fusion = self._make_fusion()
        fusion.BED_LEAVE_THRESHOLD = 30
        fusion.BED_REGION_POLYGON = []  # 未配置
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "standing",
            "fall_score": 0.0, "bbox": [0.85, 0.3, 0.1, 0.2],
        })
        bed = make_observation("bed_sensor", {"occupied": False, "absence_seconds": 45})
        events = fusion.fuse([bed, cam])
        leave_events = [e for e in events if e.event_type == "bed_leave"]
        self.assertEqual(len(leave_events), 1)
        self.assertAlmostEqual(leave_events[0].confidence, 0.85, places=2)
        # 未校验时不应有 cam_cross_check 字段
        self.assertNotIn("cam_cross_check", leave_events[0].details)

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
        env = make_observation("environment", {
            "temperature": 29.5, "humidity": 78.0, "light": 40, "co2": 1250, "door_open": False
        })
        events1 = fusion.fuse([env])
        events2 = fusion.fuse([env])  # 立即第二次，应被去重
        self.assertEqual(len(events1), 1)
        self.assertEqual(len(events2), 0, f"去重期内不应触发，实际 {len(events2)}")

    def test_event_payload_matches_contract(self):
        """事件 payload 结构应符合 contracts/safety_event.json 的必需字段"""
        fusion = self._make_fusion()
        env = make_observation("environment", {
            "temperature": 29.5, "humidity": 78.0, "light": 40, "co2": 1250, "door_open": False
        })
        events = fusion.fuse([env])
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

    def test_nurse_call_passthrough(self):
        """护士呼叫透传：camera.call_requested=True 时生成 nurse_call（P1）"""
        fusion = self._make_fusion()
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "sitting",
            "fall_score": 0.0, "call_requested": True,
        })
        events = fusion.fuse([cam])
        call_events = [e for e in events if e.event_type == "nurse_call"]
        self.assertEqual(len(call_events), 1, f"应触发 1 个 nurse_call，实际 {len(call_events)}")
        self.assertEqual(call_events[0].priority, "P1")
        self.assertIn("call_requested=true", call_events[0].rule_hits)

    def test_nurse_call_not_triggered_when_no_request(self):
        """无 call_requested 标志时不应触发 nurse_call"""
        fusion = self._make_fusion()
        cam = make_observation("camera", {
            "presence": True, "person_count": 1, "posture": "sitting",
            "fall_score": 0.0, "call_requested": False,
        })
        events = fusion.fuse([cam])
        call_events = [e for e in events if e.event_type == "nurse_call"]
        self.assertEqual(len(call_events), 0, f"无呼叫请求不应触发，实际 {len(call_events)}")


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

    def test_scenario_nurse_call_passthrough_e2e(self):
        """端到端：nurse_call 场景 -> scenario 注入 -> camera 读取 -> fusion 透传

        验证整条透传链路：场景激活时 call_requested=True，
        CameraAdapter 透传该字段，FusionEngine 生成 nurse_call 事件。
        """
        os.environ["SCENARIO_PROFILE"] = "nurse_call"
        driver = ScenarioDriver()

        # tick 启动场景
        driver.tick()
        cam_state = driver.get_camera_state()
        self.assertTrue(cam_state.get("call_requested"), "场景应注入 call_requested=True")

        # CameraAdapter 读取场景状态
        cam_adapter = CameraAdapter("EDGE-W01-B01", "B01", scenario_driver=driver)
        obs = cam_adapter.read()
        self.assertTrue(obs.data.get("call_requested"), "CameraAdapter 应透传 call_requested")

        # FusionEngine 生成 nurse_call 事件
        fusion = FusionEngine("W-01", "EDGE-W01-B01", "B01")
        fusion.dedupe_seconds = 0
        events = fusion.fuse([obs])
        call_events = [e for e in events if e.event_type == "nurse_call"]
        self.assertEqual(len(call_events), 1, "应透传生成 1 个 nurse_call 事件")
        self.assertEqual(call_events[0].priority, "P1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
