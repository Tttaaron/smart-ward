"""床位压力传感器适配器（模拟版）

模拟床垫压力传感器，输出占床/离床状态与持续时长。
真实硬件接入时替换为 GPIO/BLE/串口/MQTT 网关读取。
"""

from typing import Any, Dict
from .base import BaseAdapter, Observation, Quality


class BedSensorAdapter(BaseAdapter):
    """床位压力传感器适配器（模拟）

    data 字段结构：
        {
            "occupied": bool,           # 是否占床
            "bed_state": str,           # occupied / empty / out_of_bed
            "absence_seconds": int,     # 离床持续秒数（占床时为 0）
            "pressure_raw": float       # 原始压力值（模拟）
        }
    """

    SOURCE_TYPE = "bed_sensor"

    def __init__(self, node_id: str, bed_id: str, scenario_driver=None):
        super().__init__(node_id, bed_id)
        self.scenario = scenario_driver

    def read(self) -> Observation:
        occupied = True
        absence_seconds = 0

        if self.scenario is not None:
            bed_state = self.scenario.get_bed_state()
            if bed_state:
                occupied = bed_state.get("occupied", occupied)
                absence_seconds = bed_state.get("absence_seconds", absence_seconds)

        data: Dict[str, Any] = {
            "occupied": occupied,
            "bed_state": "occupied" if occupied else (
                "out_of_bed" if absence_seconds > 0 else "empty"
            ),
            "absence_seconds": absence_seconds,
            "pressure_raw": 62.5 if occupied else 0.0,
        }

        quality = Quality(confidence=0.98, latency_ms=8, degraded=False)

        return Observation(
            source_type=self.SOURCE_TYPE,
            data=data,
            quality=quality,
        )
