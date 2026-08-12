"""摄像头适配器（模拟版）

模拟 RGB 摄像头输出，含人体/床位/区域检测 + 姿态关键点。
真实硬件接入时，替换 read() 为 ONNX/OpenVINO/TensorRT 推理调用，
输出结构保持一致，不改动 fusion/inference/main。

模拟数据由 ScenarioDriver 注入（scenario.py），
适配器仅负责将场景状态映射为标准 Observation。
"""

from typing import Any, Dict
from .base import BaseAdapter, Observation, Quality


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
            "position_duration": int    # 同一体位持续秒数
        }
    """

    SOURCE_TYPE = "camera"

    # 姿态 -> 日常活动映射（mock 无关键点，用姿态近似；
    # 与 yolo 模式 activity entry 字段同构：label/since/switched/previous）
    POSTURE_ACTIVITY_MAP = {
        "sitting": "sit",
        "standing": "stand",
        "lying": "lie",
        "lying_edge": "lie",
        "falling": "fall",
        "curled": "bend",
        "leaning": "bend",
        "grabbing_chest": "bend",
        "seizing": "unknown",
        "unknown": "unknown",
    }

    def __init__(self, node_id: str, bed_id: str, scenario_driver=None):
        super().__init__(node_id, bed_id)
        self.scenario = scenario_driver
        # 体位持续时长跟踪（模拟）
        self._posture = "sitting"
        self._posture_since = None
        # 模拟活动状态（姿态映射 + 切换事件跟踪）
        self._activity = "sit"
        self._activity_since = None

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

        # 日常活动模拟：姿态 -> 活动标签，姿态变化时产生切换事件
        from datetime import datetime, timezone
        activity_label = self.POSTURE_ACTIVITY_MAP.get(posture, "unknown")
        now = datetime.now(timezone.utc)
        if self._activity_since is None:
            self._activity_since = now
        activity_entry = {
            "label": activity_label,
            "since": self._activity_since.timestamp(),
            "switched": False,
            "previous": self._activity,
        }
        if activity_label != self._activity:
            # 切换：entry.previous 已在构造时记录旧活动，此处更新状态与时间
            self._activity = activity_label
            self._activity_since = now
            activity_entry["switched"] = True
            activity_entry["since"] = now.timestamp()

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
