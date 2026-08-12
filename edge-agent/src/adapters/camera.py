"""摄像头适配器（模拟版）

模拟 RGB 摄像头输出，含人体/床位/区域检测 + 姿态关键点。
真实硬件接入时，替换 read() 为 ONNX/OpenVINO/TensorRT 推理调用，
输出结构保持一致，不改动 fusion/inference/main。

模拟数据由 ScenarioDriver 注入（scenario.py），
适配器仅负责将场景状态映射为标准 Observation。

模拟版也产出与真实 YOLO 模式一致的 ``activity`` 字段
（{label, since, switched, previous}），使前端活动日志面板在
mock 全栈演示中同样可驱动。
"""

import time
from typing import Any, Dict, Optional
from .base import BaseAdapter, Observation, Quality

# 姿势 -> 活动标签映射（对齐 activity_tracker.py 词汇表）。
# 活动标签：walking / eating / playing_phone / sleeping /
#           sitting / standing / lying / unknown
_POSTURE_TO_ACTIVITY: Dict[str, str] = {
    "standing": "standing",
    "sitting": "sitting",
    "lying": "lying",
    "lying_edge": "lying",
    "curled": "sitting",
    "leaning": "sitting",
    "grabbing_chest": "sitting",
    "falling": "lying",
    "seizing": "lying",
}


class CameraAdapter(BaseAdapter):
    """摄像头适配器（模拟）

    data 字段结构：
        {
            "presence": bool,           # 是否检测到人
            "person_count": int,        # 人数
            "posture": str,             # standing/sitting/lying/lying_edge/
                                         # falling/curled/leaning/grabbing_chest/
                                         # seizing/unknown
            "bbox": [x, y, w, h],       # 人体边界框（图像坐标系，归一化 0~1）
            "pose_keypoints": [...],    # 17 个关键点 [x, y, conf]（COCO 格式）
            "fall_score": float,        # 跌倒置信度（0~1）
            "tremor_score": float,      # 抽搐幅度（0~1），基于关键点高频抖动
            "position_duration": int,   # 同一体位持续秒数
            "activity": dict            # 活动条目 {label, since, switched, previous}
        }
    """

    SOURCE_TYPE = "camera"

    def __init__(self, node_id: str, bed_id: str, scenario_driver=None):
        super().__init__(node_id, bed_id)
        self.scenario = scenario_driver
        # 体位持续时长跟踪（模拟）
        self._posture = "sitting"
        self._posture_since = None
        # 活动状态跟踪（与 yolo_camera.py 模式一致，供 switched/previous/since 判定）
        self._last_activity: Optional[str] = None
        self._activity_since: float = time.time()

    @staticmethod
    def _activity_for_posture(posture: str) -> str:
        """将姿势映射为活动标签（unknown 兜底）。"""
        return _POSTURE_TO_ACTIVITY.get(posture, "unknown")

    def _build_activity_entry(self, posture: str, now: float) -> dict:
        """构建活动条目 {label, since, switched, previous}。

        姿势映射的活动标签变化时标记 switched，并重置 since；
        否则沿用当前活动起始时间，供前端面板计算持续时长。
        """
        label = self._activity_for_posture(posture)
        entry: Dict[str, Any] = {
            "label": label,
            "since": round(self._activity_since, 2),
            "switched": False,
            "previous": self._last_activity,
        }
        if label != self._last_activity:
            entry["switched"] = True
            entry["since"] = round(now, 2)
            self._last_activity = label
            self._activity_since = now
        return entry

    def read(self) -> Observation:
        # 默认状态：床位有人静坐
        presence = True
        person_count = 1
        posture = "sitting"
        fall_score = 0.0
        tremor_score = 0.0
        position_duration = 0
        degraded = False
        call_requested = False  # 护士呼叫按钮（场景注入或真实按钮）

        # 场景驱动：若 scenario_driver 注入了摄像头状态，覆盖默认值
        if self.scenario is not None:
            cam_state = self.scenario.get_camera_state()
            if cam_state:
                presence = cam_state.get("presence", presence)
                person_count = cam_state.get("person_count", person_count)
                posture = cam_state.get("posture", posture)
                fall_score = cam_state.get("fall_score", fall_score)
                tremor_score = cam_state.get("tremor_score", tremor_score)
                position_duration = cam_state.get("position_duration", position_duration)
                degraded = cam_state.get("degraded", degraded)
                call_requested = cam_state.get("call_requested", call_requested)

        # 体位持续时长自维护（场景未注入时按实际累积）
        if position_duration == 0:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            if posture != self._posture:
                self._posture = posture
                self._posture_since = now
                position_duration = 0
            elif self._posture_since:
                position_duration = int((now - self._posture_since).total_seconds())

        # 活动标签（仿真实 YOLO 模式产出，供前端活动日志面板与 LLM 摘要使用）
        activity_entry = self._build_activity_entry(posture, time.time())

        data: Dict[str, Any] = {
            "presence": presence,
            "person_count": person_count,
            "posture": posture,
            "bbox": [0.3, 0.4, 0.2, 0.5] if presence else None,
            "pose_keypoints": [],  # 模拟版留空，真实模型填充 17 个关键点
            "fall_score": fall_score,
            "tremor_score": tremor_score,
            "position_duration": position_duration,
            "call_requested": call_requested,
            "activity": activity_entry,
        }

        # 跌倒或抽搐时置信度降低（模拟模型不确定性）
        conf = 0.95 if not degraded else 0.6
        quality = Quality(confidence=conf, latency_ms=45, degraded=degraded)

        return Observation(
            source_type=self.SOURCE_TYPE,
            data=data,
            quality=quality,
        )
