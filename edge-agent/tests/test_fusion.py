"""事件融合引擎冒烟测试

验证 FusionEngine 对各类场景的识别能力。
覆盖 contracts/safety_event.json 中的主要 event_type。
"""

import os
import sys

# 将 src/ 加入 sys.path，使 src 下的扁平导入（from adapters.base import ...）生效
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

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


def test_fall_suspected():
    """跌倒疑似：摄像头 posture=falling + fall_score>0.5 + 床位离床"""
    fusion = FusionEngine("W-01", "EDGE-W01-B01", "B01")
    fusion.dedupe_seconds = 0  # 测试时关闭去重

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
    assert len(fall_events) == 1, f"应触发 1 个 fall_suspected，实际 {len(fall_events)}"
    assert fall_events[0].priority == "P1"
    assert fall_events[0].state == "new"
    assert fall_events[0].model["model_name"] == "yolo-nano-pose"
    print("✓ test_fall_suspected 通过")


def test_bed_leave():
    """离床：床位 absence_seconds 超阈值"""
    fusion = FusionEngine("W-01", "EDGE-W01-B01", "B01")
    fusion.dedupe_seconds = 0
    fusion.BED_LEAVE_THRESHOLD = 30  # 显式设阈值

    bed = make_observation("bed_sensor", {"occupied": False, "absence_seconds": 45})
    events = fusion.fuse([bed])
    leave_events = [e for e in events if e.event_type == "bed_leave"]
    assert len(leave_events) == 1, f"应触发 1 个 bed_leave，实际 {len(leave_events)}"
    assert leave_events[0].priority == "P2"
    assert leave_events[0].details["absence_seconds"] == 45
    print("✓ test_bed_leave 通过")


def test_bed_leave_below_threshold():
    """离床未超阈值：不应触发"""
    fusion = FusionEngine("W-01", "EDGE-W01-B01", "B01")
    fusion.dedupe_seconds = 0
    fusion.BED_LEAVE_THRESHOLD = 30

    bed = make_observation("bed_sensor", {"occupied": False, "absence_seconds": 10})
    events = fusion.fuse([bed])
    leave_events = [e for e in events if e.event_type == "bed_leave"]
    assert len(leave_events) == 0, f"未超阈值不应触发，实际 {len(leave_events)}"
    print("✓ test_bed_leave_below_threshold 通过")


def test_infusion_anomaly():
    """输液异常：anomaly != normal"""
    fusion = FusionEngine("W-01", "EDGE-W01-B01", "B01")
    fusion.dedupe_seconds = 0

    inf = make_observation("infusion", {
        "flow_rate": 100.0, "volume_pct": 3.0, "remaining_minutes": 5, "anomaly": "low_volume"
    })
    events = fusion.fuse([inf])
    inf_events = [e for e in events if e.event_type == "infusion_anomaly"]
    assert len(inf_events) == 1, f"应触发 1 个 infusion_anomaly，实际 {len(inf_events)}"
    assert inf_events[0].priority == "P2"
    assert inf_events[0].details["anomaly"] == "low_volume"
    print("✓ test_infusion_anomaly 通过")


def test_environment_anomaly():
    """环境异常：温度/CO₂/光照超阈值"""
    fusion = FusionEngine("W-01", "EDGE-W01-B01", "B01")
    fusion.dedupe_seconds = 0
    fusion.TEMP_HIGH = 29.0
    fusion.CO2_HIGH = 1000
    fusion.LIGHT_LOW = 50

    env = make_observation("environment", {
        "temperature": 29.5, "humidity": 78.0, "light": 40, "co2": 1250, "door_open": False, "air_quality": "bad"
    })
    events = fusion.fuse([env])
    env_events = [e for e in events if e.event_type == "environment_anomaly"]
    assert len(env_events) == 1, f"应触发 1 个 environment_anomaly，实际 {len(env_events)}"
    assert env_events[0].priority == "P3"
    # 应命中温度、CO₂、光照三条规则
    assert len(env_events[0].rule_hits) == 3
    print("✓ test_environment_anomaly 通过")


def test_dedupe():
    """同类事件去重：dedupe_seconds 内不应重复触发"""
    fusion = FusionEngine("W-01", "EDGE-W01-B01", "B01")
    fusion.dedupe_seconds = 60  # 60 秒去重

    inf = make_observation("infusion", {
        "flow_rate": 100.0, "volume_pct": 3.0, "remaining_minutes": 5, "anomaly": "low_volume"
    })
    events1 = fusion.fuse([inf])
    events2 = fusion.fuse([inf])  # 立即第二次，应被去重
    assert len(events1) == 1
    assert len(events2) == 0, f"去重期内不应触发，实际 {len(events2)}"
    print("✓ test_dedupe 通过")


def test_event_payload_matches_contract():
    """事件 payload 结构应符合 contracts/safety_event.json 的必需字段"""
    fusion = FusionEngine("W-01", "EDGE-W01-B01", "B01")
    fusion.dedupe_seconds = 0

    inf = make_observation("infusion", {
        "flow_rate": 100.0, "volume_pct": 3.0, "remaining_minutes": 5, "anomaly": "low_volume"
    })
    events = fusion.fuse([inf])
    assert len(events) == 1
    payload = events[0].to_dict()
    # 校验契约必需字段
    required = ["event_id", "ward_id", "node_id", "bed_id", "event_type", "priority",
                "state", "occurred_at", "detected_at", "confidence", "model", "evidence_refs"]
    for field in required:
        assert field in payload, f"缺失契约必需字段: {field}"
    assert "model_name" in payload["model"]
    assert "model_version" in payload["model"]
    assert "inference_ms" in payload["model"]
    print("✓ test_event_payload_matches_contract 通过")


def test_scenario_driver_advance():
    """场景驱动器状态机推进"""
    os.environ["SCENARIO_PROFILE"] = "fall_suspected"
    os.environ["TICK_SECONDS"] = "3"
    driver = ScenarioDriver()
    assert "fall_suspected" in driver.scene_types

    # tick 1: 启动
    driver.tick()
    assert driver._current_scene is not None
    assert driver._current_scene.phase == "started"

    # tick 2: 进入 sustained
    driver.tick()
    assert driver._current_scene.phase == "sustained"
    cam_state = driver.get_camera_state()
    assert cam_state["posture"] == "falling"

    # 持续到 duration_ticks 后进入 recovering
    # fall_suspected duration_ticks=3：tick2 后还需 (duration_ticks-1)=2 次到达 recovering
    sc = driver._current_scene
    for _ in range(sc.duration_ticks - 1):
        driver.tick()
    assert sc.phase == "recovering"

    # 再 tick 一次后场景结束，_current_scene 被清空
    driver.tick()
    assert driver._current_scene is None
    print("✓ test_scenario_driver_advance 通过")


def test_adapters_smoke():
    """适配器冒烟：read() 应返回合法 Observation"""
    cam = CameraAdapter("EDGE-W01-B01", "B01")
    obs = cam.read()
    assert obs.source_type == "camera"
    assert "presence" in obs.data
    assert "posture" in obs.data

    bed = BedSensorAdapter("EDGE-W01-B01", "B01")
    obs = bed.read()
    assert obs.source_type == "bed_sensor"
    assert "occupied" in obs.data

    inf = InfusionAdapter("EDGE-W01-B01", "B01")
    obs = inf.read()
    assert obs.source_type == "infusion"
    assert "anomaly" in obs.data

    env = EnvironmentAdapter("EDGE-W01-B01", "B01")
    obs = env.read()
    assert obs.source_type == "environment"
    assert "temperature" in obs.data
    print("✓ test_adapters_smoke 通过")


def test_inference_engine_output_fields():
    """推理引擎输出应包含方案书 §3.3 验收要求的字段"""
    engine = InferenceEngine()
    cam = make_observation("camera", {
        "presence": True, "person_count": 1, "posture": "sitting", "fall_score": 0.0
    })
    result = engine.run(cam)
    d = result.to_dict()
    for field in ["model_name", "model_version", "confidence", "inference_ms", "evidence_ref"]:
        assert field in d, f"推理输出缺失字段: {field}"
    print("✓ test_inference_engine_output_fields 通过")


if __name__ == "__main__":
    test_adapters_smoke()
    test_inference_engine_output_fields()
    test_fall_suspected()
    test_bed_leave()
    test_bed_leave_below_threshold()
    test_infusion_anomaly()
    test_environment_anomaly()
    test_dedupe()
    test_event_payload_matches_contract()
    test_scenario_driver_advance()
    print("\n全部测试通过 ✓")
