"""采集适配器基类

定义 BaseAdapter 抽象接口。所有适配器（Camera/BedSensor/Environment）
必须实现 read()，返回标准化的 Observation 结构。

Observation 结构对齐 contracts/observation.json 中的 source 定义：
    {
        "source_type": "camera" | "bed_sensor" | "environment",
        "data": {...},          # 源特有数据
        "quality": {            # 数据质量标签
            "confidence": 0.0~1.0,
            "latency_ms": int,
            "degraded": bool
        }
    }
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict


@dataclass
class Quality:
    """数据质量标签"""
    confidence: float = 1.0          # 置信度 0~1
    latency_ms: int = 0              # 采集/推理耗时
    degraded: bool = False           # 是否降级（遮挡/低照度/传感器故障）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confidence": round(self.confidence, 3),
            "latency_ms": self.latency_ms,
            "degraded": self.degraded,
        }


@dataclass
class Observation:
    """标准化观测结构"""
    source_type: str                  # camera / bed_sensor / environment
    data: Dict[str, Any] = field(default_factory=dict)
    quality: Quality = field(default_factory=Quality)
    timestamp: str = ""               # ISO 8601 UTC

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "data": self.data,
            "quality": self.quality.to_dict(),
            "timestamp": self.timestamp,
        }


class BaseAdapter(ABC):
    """采集适配器抽象基类

    真实硬件适配器和模拟器适配器共用此接口。
    接入真实摄像头/传感器时，新建子类并实现 read()，
    在 main.py 中注入替换即可。
    """

    SOURCE_TYPE = "base"

    def __init__(self, node_id: str, bed_id: str):
        """
        Args:
            node_id: 边缘节点 ID，如 EDGE-W01-B01
            bed_id: 床位 ID，如 B01
        """
        self.node_id = node_id
        self.bed_id = bed_id

    @abstractmethod
    def read(self) -> Observation:
        """读取一次观测数据，返回标准化的 Observation

        Returns:
            Observation: 包含 source_type/data/quality/timestamp
        """
        raise NotImplementedError

    def health(self) -> Dict[str, Any]:
        """返回适配器健康状态（可选实现，默认 healthy）"""
        return {"source_type": self.SOURCE_TYPE, "healthy": True}
