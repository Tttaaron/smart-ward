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
            "posture": str,             # standing / sitting / lying / falling / unknown
            "bbox": [x, y, w, h],       # 人体边界框（图像坐标系，归一化 0~1）
            "pose_keypoints": [...],    # 17 个关键点 [x, y, conf]（COCO 格式）
            "fall_score": float         # 跌倒置信度（0~1）
        }
    """

    SOURCE_TYPE = "camera"

    def __init__(self, node_id: str, bed_id: str, scenario_driver=None):
        super().__init__(node_id, bed_id)
        self.scenario = scenario_driver

    def read(self) -> Observation:
        # 默认状态：床位有人静坐
        presence = True
        person_count = 1
        posture = "sitting"
        fall_score = 0.0
        degraded = False

        # 场景驱动：若 scenario_driver 注入了摄像头状态，覆盖默认值
        if self.scenario is not None:
            cam_state = self.scenario.get_camera_state()
            if cam_state:
                presence = cam_state.get("presence", presence)
                person_count = cam_state.get("person_count", person_count)
                posture = cam_state.get("posture", posture)
                fall_score = cam_state.get("fall_score", fall_score)
                degraded = cam_state.get("degraded", degraded)

        data: Dict[str, Any] = {
            "presence": presence,
            "person_count": person_count,
            "posture": posture,
            "bbox": [0.3, 0.4, 0.2, 0.5] if presence else None,
            "pose_keypoints": [],  # 模拟版留空，真实模型填充 17 个关键点
            "fall_score": fall_score,
        }

        # 跌倒时置信度降低（模拟模型不确定性）
        conf = 0.95 if not degraded else 0.6
        quality = Quality(confidence=conf, latency_ms=45, degraded=degraded)

        return Observation(
            source_type=self.SOURCE_TYPE,
            data=data,
            quality=quality,
        )
