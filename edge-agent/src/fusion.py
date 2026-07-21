"""事件融合引擎

接收多源观测（camera/bed_sensor/infusion/environment），
按规则融合输出 SafetyEvent。

第一版采用规则融合：
- fall_suspected: 摄像头 posture=falling + fall_score>0.5 + 床位离床
- bed_leave: 床位离床 + absence_seconds > 阈值（夜间加强）
- infusion_anomaly: 输液 anomaly != normal
- environment_anomaly: 温度/CO₂/光照超阈值
- door_departure: 门磁 open + 摄像头检测到人离开区域
- night_wandering: 夜间时段 + 摄像头 standing + 持续时长
- nurse_call: 由前端/按钮触发，边缘端不主动生成（但可透传）

为后续接入 YOLO/姿态模型预留接口：fusion 只消费 InferenceResult + Observation，
模型升级时只替换 inference.py。
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from adapters.base import Observation
from inference import InferenceResult


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class SafetyEvent:
    """安全事件（对齐 contracts/safety_event.json）"""

    def __init__(
        self,
        event_type: str,
        priority: str,
        ward_id: str,
        node_id: str,
        bed_id: str,
        confidence: float,
        model_name: str,
        model_version: str,
        inference_ms: int,
        evidence_refs: List[Dict] = None,
        rule_hits: List[str] = None,
        details: Dict[str, Any] = None,
    ):
        self.event_id = str(uuid4())
        self.ward_id = ward_id
        self.node_id = node_id
        self.bed_id = bed_id
        self.event_type = event_type
        self.priority = priority
        self.state = "new"
        self.occurred_at = utc_now_iso()
        self.detected_at = utc_now_iso()
        self.confidence = confidence
        self.model = {
            "model_name": model_name,
            "model_version": model_version,
            "inference_ms": inference_ms,
        }
        self.evidence_refs = evidence_refs or []
        self.rule_hits = rule_hits or []
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "ward_id": self.ward_id,
            "node_id": self.node_id,
            "bed_id": self.bed_id,
            "event_type": self.event_type,
            "priority": self.priority,
            "state": self.state,
            "occurred_at": self.occurred_at,
            "detected_at": self.detected_at,
            "confidence": round(self.confidence, 3),
            "model": self.model,
            "evidence_refs": self.evidence_refs,
            "rule_hits": self.rule_hits,
            "details": self.details,
        }


class FusionEngine:
    """事件融合引擎

    每周期调用 fuse() 一次，传入本轮所有观测 + 推理结果，
    返回新生成的 SafetyEvent 列表。

    去重：通过 EVENT_DEDUPE_SECONDS 环境变量控制同类事件最小间隔。
    """

    def __init__(self, ward_id: str, node_id: str, bed_id: str):
        self.ward_id = ward_id
        self.node_id = node_id
        self.bed_id = bed_id
        # 同类事件去重：记录上次触发时间
        self._last_fired: Dict[str, datetime] = {}
        self.dedupe_seconds = int(os.getenv("EVENT_DEDUPE_SECONDS", "30"))

        # 规则阈值（可由环境变量覆盖）
        self.BED_LEAVE_THRESHOLD = int(os.getenv("BED_LEAVE_THRESHOLD", "30"))  # 离床秒数
        self.NIGHT_WANDLING_START = int(os.getenv("NIGHT_START", "22"))        # 夜间起始小时
        self.NIGHT_WANDLING_END = int(os.getenv("NIGHT_END", "6"))             # 夜间结束小时
        self.TEMP_HIGH = float(os.getenv("TEMP_ALARM_HIGH", "29.0"))
        self.CO2_HIGH = int(os.getenv("CO2_ALARM_HIGH", "1000"))
        self.LIGHT_LOW = int(os.getenv("LIGHT_ALARM_LOW", "50"))

        # ─── 新增功能阈值（患者安全类）──
        # 坠床预警：床位占床 + 姿态=lying_edge + fall_score 超阈值
        self.BED_EDGE_FALL_SCORE = float(os.getenv("BED_EDGE_FALL_SCORE", "0.6"))
        # 长时间静止：同一体位持续超阈值（默认 5 分钟）
        self.LONG_STILL_SECONDS = int(os.getenv("LONG_STILL_SECONDS", "300"))
        # 异常体态：posture 命中以下任一即告警
        self.ABNORMAL_POSTURE_TYPES = os.getenv(
            "ABNORMAL_POSTURE_TYPES", "curled,leaning,grabbing_chest"
        ).split(",")
        # 抽搐检测：tremor_score 超阈值
        self.TREMOR_THRESHOLD = float(os.getenv("TREMOR_THRESHOLD", "0.6"))
        # 压疮预防：同一体位持续超阈值（默认 2 小时）
        self.BEDSORE_DURATION = int(os.getenv("BEDSORE_DURATION", "7200"))
        # 设备故障：传感器质量 degraded 持续超阈值
        self.DEVICE_FAULT_DEGRADED_SECONDS = int(os.getenv("DEVICE_FAULT_DEGRADED_SECONDS", "60"))

        # ─── 状态历史缓冲（跨周期跟踪）──
        from collections import deque
        self._posture_history: deque = deque(maxlen=20)  # 最近 20 轮姿态
        self._last_posture: Optional[str] = None
        self._last_posture_change_at: Optional[datetime] = None
        self._degraded_since: Optional[datetime] = None  # 传感器降级起始时间

    def _should_fire(self, event_type: str) -> bool:
        """同类事件去重：超过 dedupe_seconds 才允许再次触发"""
        now = datetime.now(timezone.utc)
        last = self._last_fired.get(event_type)
        if last and (now - last).total_seconds() < self.dedupe_seconds:
            return False
        self._last_fired[event_type] = now
        return True

    def _is_night(self) -> bool:
        """判断当前是否为夜间时段（本地时间）"""
        hour = datetime.now().hour
        if self.NIGHT_WANDLING_START > self.NIGHT_WANDLING_END:
            # 跨午夜：如 22 -> 6
            return hour >= self.NIGHT_WANDLING_START or hour < self.NIGHT_WANDLING_END
        return self.NIGHT_WANDLING_START <= hour < self.NIGHT_WANDLING_END

    def fuse(
        self,
        observations: List[Observation],
        inference: Optional[InferenceResult] = None,
    ) -> List[SafetyEvent]:
        """融合多源观测，输出安全事件列表

        Args:
            observations: 本周期所有适配器的观测数据
            inference: 摄像头推理结果（可选）

        Returns:
            List[SafetyEvent]: 新生成的事件列表（可能为空）
        """
        events: List[SafetyEvent] = []

        # 按 source_type 索引
        obs_by_type: Dict[str, Observation] = {o.source_type: o for o in observations}
        cam = obs_by_type.get("camera")
        bed = obs_by_type.get("bed_sensor")
        inf = obs_by_type.get("infusion")
        env = obs_by_type.get("environment")

        model_name = inference.model_name if inference else "rule-fusion-v1"
        model_version = inference.model_version if inference else "0.1.0"
        inference_ms = inference.inference_ms if inference else 0

        # ─── 规则1：跌倒疑似（P1）───
        if cam and inference:
            fall_score = inference.predictions.get("fall_score", 0)
            posture = inference.predictions.get("posture", "unknown")
            if posture == "falling" and fall_score > 0.5:
                if self._should_fire("fall_suspected"):
                    events.append(SafetyEvent(
                        event_type="fall_suspected",
                        priority="P1",
                        ward_id=self.ward_id, node_id=self.node_id, bed_id=self.bed_id,
                        confidence=fall_score,
                        model_name=model_name, model_version=model_version, inference_ms=inference_ms,
                        rule_hits=["posture=falling", f"fall_score={fall_score:.2f}>0.5"],
                        details={"posture": posture, "fall_score": fall_score},
                    ))

        # ─── 规则2：离床（P2）───
        if bed:
            absence_sec = bed.data.get("absence_seconds", 0)
            occupied = bed.data.get("occupied", True)
            if not occupied and absence_sec >= self.BED_LEAVE_THRESHOLD:
                # 夜间离床升级为 night_wandering（若持续徘徊）
                if self._is_night() and self._should_fire("night_wandering"):
                    events.append(SafetyEvent(
                        event_type="night_wandering",
                        priority="P2",
                        ward_id=self.ward_id, node_id=self.node_id, bed_id=self.bed_id,
                        confidence=0.7,
                        model_name=model_name, model_version=model_version, inference_ms=inference_ms,
                        rule_hits=[f"absence={absence_sec}s>={self.BED_LEAVE_THRESHOLD}s", "night_time"],
                        details={"absence_seconds": absence_sec, "period": "night"},
                    ))
                elif self._should_fire("bed_leave"):
                    events.append(SafetyEvent(
                        event_type="bed_leave",
                        priority="P2",
                        ward_id=self.ward_id, node_id=self.node_id, bed_id=self.bed_id,
                        confidence=0.85,
                        model_name=model_name, model_version=model_version, inference_ms=inference_ms,
                        rule_hits=[f"absence={absence_sec}s>={self.BED_LEAVE_THRESHOLD}s"],
                        details={"absence_seconds": absence_sec},
                    ))

        # ─── 规则3：输液异常（P2）───
        if inf:
            anomaly = inf.data.get("anomaly", "normal")
            if anomaly != "normal" and self._should_fire("infusion_anomaly"):
                events.append(SafetyEvent(
                    event_type="infusion_anomaly",
                    priority="P2",
                    ward_id=self.ward_id, node_id=self.node_id, bed_id=self.bed_id,
                    confidence=0.9,
                    model_name=model_name, model_version=model_version, inference_ms=inference_ms,
                    rule_hits=[f"anomaly={anomaly}"],
                    details={
                        "anomaly": anomaly,
                        "flow_rate": inf.data.get("flow_rate"),
                        "volume_pct": inf.data.get("volume_pct"),
                    },
                ))

        # ─── 规则4：环境异常（P3）───
        if env:
            temp = env.data.get("temperature", 24)
            co2 = env.data.get("co2", 450)
            light = env.data.get("light", 450)
            hits = []
            if temp > self.TEMP_HIGH:
                hits.append(f"temp={temp}>{self.TEMP_HIGH}")
            if co2 > self.CO2_HIGH:
                hits.append(f"co2={co2}>{self.CO2_HIGH}")
            if light < self.LIGHT_LOW:
                hits.append(f"light={light}<{self.LIGHT_LOW}")
            if hits and self._should_fire("environment_anomaly"):
                events.append(SafetyEvent(
                    event_type="environment_anomaly",
                    priority="P3",
                    ward_id=self.ward_id, node_id=self.node_id, bed_id=self.bed_id,
                    confidence=0.95,
                    model_name=model_name, model_version=model_version, inference_ms=inference_ms,
                    rule_hits=hits,
                    details={"temperature": temp, "co2": co2, "light": light},
                ))

        # ─── 规则5：门区异常离开（P2）───
        if env and env.data.get("door_open") and cam:
            presence = cam.data.get("presence", False)
            if presence and self._should_fire("door_departure"):
                events.append(SafetyEvent(
                    event_type="door_departure",
                    priority="P2",
                    ward_id=self.ward_id, node_id=self.node_id, bed_id=self.bed_id,
                    confidence=0.65,
                    model_name=model_name, model_version=model_version, inference_ms=inference_ms,
                    rule_hits=["door_open=true", "person_detected_near_door"],
                    details={"door_open": True},
                ))

        # ─── 规则6：坠床预警（P1）───
        # 床位占床 + 姿态=lying_edge（床沿）+ fall_score 超阈值
        # 事前预警，比 fall_suspected 更前置
        if cam and bed:
            posture = cam.data.get("posture", "unknown")
            fall_score = cam.data.get("fall_score", 0)
            occupied = bed.data.get("occupied", False)
            if posture == "lying_edge" and occupied and fall_score >= self.BED_EDGE_FALL_SCORE:
                if self._should_fire("fall_prediction"):
                    events.append(SafetyEvent(
                        event_type="fall_prediction",
                        priority="P1",
                        ward_id=self.ward_id, node_id=self.node_id, bed_id=self.bed_id,
                        confidence=fall_score,
                        model_name=model_name, model_version=model_version, inference_ms=inference_ms,
                        rule_hits=[f"posture=lying_edge", f"fall_score={fall_score:.2f}>={self.BED_EDGE_FALL_SCORE}", "bed_occupied"],
                        details={"posture": posture, "fall_score": fall_score},
                    ))

        # ─── 规则7：长时间静止（P2）───
        # 同一体位持续超 LONG_STILL_SECONDS（默认 5 分钟），可能是昏迷/不适
        if cam:
            posture = cam.data.get("posture", "unknown")
            position_duration = cam.data.get("position_duration", 0)
            # 更新姿态历史
            if posture != self._last_posture:
                self._last_posture = posture
                self._last_posture_change_at = datetime.now(timezone.utc)
            # 场景注入的 position_duration 优先；否则按实际累积
            if position_duration == 0 and self._last_posture_change_at:
                position_duration = int((datetime.now(timezone.utc) - self._last_posture_change_at).total_seconds())
            if position_duration >= self.LONG_STILL_SECONDS and posture not in ("unknown",):
                if self._should_fire("long_still"):
                    events.append(SafetyEvent(
                        event_type="long_still",
                        priority="P2",
                        ward_id=self.ward_id, node_id=self.node_id, bed_id=self.bed_id,
                        confidence=0.75,
                        model_name=model_name, model_version=model_version, inference_ms=inference_ms,
                        rule_hits=[f"posture={posture} unchanged", f"duration={position_duration}s>={self.LONG_STILL_SECONDS}s"],
                        details={"posture": posture, "position_duration": position_duration},
                    ))

        # ─── 规则8：异常体态（P2）───
        # posture 命中 curled/leaning/grabbing_chest，可能是急症早期信号
        if cam:
            posture = cam.data.get("posture", "unknown")
            if posture in self.ABNORMAL_POSTURE_TYPES:
                if self._should_fire("abnormal_posture"):
                    events.append(SafetyEvent(
                        event_type="abnormal_posture",
                        priority="P2",
                        ward_id=self.ward_id, node_id=self.node_id, bed_id=self.bed_id,
                        confidence=0.8,
                        model_name=model_name, model_version=model_version, inference_ms=inference_ms,
                        rule_hits=[f"posture={posture} in abnormal_types"],
                        details={"posture": posture},
                    ))

        # ─── 规则9：抽搐检测（P1）───
        # tremor_score 超阈值，可能是癫痫发作
        if cam:
            tremor_score = cam.data.get("tremor_score", 0)
            if tremor_score >= self.TREMOR_THRESHOLD:
                if self._should_fire("seizure"):
                    events.append(SafetyEvent(
                        event_type="seizure",
                        priority="P1",
                        ward_id=self.ward_id, node_id=self.node_id, bed_id=self.bed_id,
                        confidence=tremor_score,
                        model_name=model_name, model_version=model_version, inference_ms=inference_ms,
                        rule_hits=[f"tremor_score={tremor_score:.2f}>={self.TREMOR_THRESHOLD}"],
                        details={"tremor_score": tremor_score},
                    ))

        # ─── 规则10：压疮预防（P3）───
        # 同一体位持续超 BEDSORE_DURATION（默认 2 小时），提醒翻身
        if cam:
            posture = cam.data.get("posture", "unknown")
            position_duration = cam.data.get("position_duration", 0)
            if position_duration >= self.BEDSORE_DURATION and posture not in ("unknown", "standing"):
                if self._should_fire("bedsore_risk"):
                    events.append(SafetyEvent(
                        event_type="bedsore_risk",
                        priority="P3",
                        ward_id=self.ward_id, node_id=self.node_id, bed_id=self.bed_id,
                        confidence=0.9,
                        model_name=model_name, model_version=model_version, inference_ms=inference_ms,
                        rule_hits=[f"posture={posture} unchanged", f"duration={position_duration}s>={self.BEDSORE_DURATION}s"],
                        details={"posture": posture, "position_duration": position_duration},
                    ))

        # ─── 规则11：设备故障预警（P3）───
        # 任一传感器 quality.degraded 持续超阈值
        now = datetime.now(timezone.utc)
        any_degraded = any(o.quality.degraded for o in observations)
        if any_degraded:
            if self._degraded_since is None:
                self._degraded_since = now
        else:
            self._degraded_since = None
        if self._degraded_since and (now - self._degraded_since).total_seconds() >= self.DEVICE_FAULT_DEGRADED_SECONDS:
            if self._should_fire("device_fault"):
                degraded_sources = [o.source_type for o in observations if o.quality.degraded]
                events.append(SafetyEvent(
                    event_type="device_fault",
                    priority="P3",
                    ward_id=self.ward_id, node_id=self.node_id, bed_id=self.bed_id,
                    confidence=0.85,
                    model_name=model_name, model_version=model_version, inference_ms=inference_ms,
                    rule_hits=[f"degraded_sources={degraded_sources}", f"duration>={self.DEVICE_FAULT_DEGRADED_SECONDS}s"],
                    details={"degraded_sources": degraded_sources},
                ))

        return events
