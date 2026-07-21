"""输液监测适配器（模拟版）

模拟输液滴速/液位传感器，输出滴速、液位百分比、剩余时间。
真实硬件接入时替换为串口/BLE/RS-485/MQTT 网关读取。
"""

from typing import Any, Dict
from .base import BaseAdapter, Observation, Quality


class InfusionAdapter(BaseAdapter):
    """输液监测适配器（模拟）

    data 字段结构：
        {
            "flow_rate": float,         # 滴速 滴/分钟
            "volume_pct": float,        # 剩余液位百分比 0~100
            "remaining_minutes": int,   # 预计剩余分钟
            "anomaly": str              # normal / fast / slow / low_volume / completed / interrupted
        }
    """

    SOURCE_TYPE = "infusion"

    # 正常滴速范围（滴/分钟）
    FLOW_NORMAL_MIN = 40
    FLOW_NORMAL_MAX = 60

    def __init__(self, node_id: str, bed_id: str, scenario_driver=None):
        super().__init__(node_id, bed_id)
        self.scenario = scenario_driver
        self._volume_pct = 100.0  # 模拟液位衰减

    def read(self) -> Observation:
        flow_rate = 50.0
        volume_pct = self._volume_pct

        if self.scenario is not None:
            inf_state = self.scenario.get_infusion_state()
            if inf_state:
                flow_rate = inf_state.get("flow_rate", flow_rate)
                volume_pct = inf_state.get("volume_pct", volume_pct)

        # 模拟液位自然衰减（按滴速推算）
        if self._volume_pct > 0 and flow_rate > 0:
            # 简化：每周期衰减 0.5%
            self._volume_pct = max(0.0, self._volume_pct - 0.5)
            volume_pct = self._volume_pct

        # 异常判定
        if volume_pct <= 5:
            anomaly = "low_volume"
        elif flow_rate > self.FLOW_NORMAL_MAX * 1.5:
            anomaly = "fast"
        elif flow_rate < self.FLOW_NORMAL_MIN * 0.5:
            anomaly = "slow"
        elif volume_pct <= 0:
            anomaly = "completed"
        else:
            anomaly = "normal"

        remaining_minutes = int(volume_pct / 100 * 250) if flow_rate > 0 else 0

        data: Dict[str, Any] = {
            "flow_rate": flow_rate,
            "volume_pct": round(volume_pct, 1),
            "remaining_minutes": remaining_minutes,
            "anomaly": anomaly,
        }

        quality = Quality(confidence=0.95, latency_ms=15, degraded=False)

        return Observation(
            source_type=self.SOURCE_TYPE,
            data=data,
            quality=quality,
        )
