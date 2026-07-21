"""环境传感器适配器（模拟版）

模拟温湿度/光照/CO₂/门磁传感器。
真实硬件接入时替换为 Modbus/BLE/LoRa/MQTT 网关读取。
"""

import math
import random
from typing import Any, Dict
from .base import BaseAdapter, Observation, Quality


class EnvironmentAdapter(BaseAdapter):
    """环境传感器适配器（模拟）

    data 字段结构：
        {
            "temperature": float,    # ℃
            "humidity": float,       # %
            "light": int,            # lux
            "co2": int,              # ppm
            "door_open": bool,       # 门磁状态
            "air_quality": str       # good / moderate / bad
        }
    """

    SOURCE_TYPE = "environment"

    def __init__(self, node_id: str, bed_id: str, scenario_driver=None, tick: int = 0):
        super().__init__(node_id, bed_id)
        self.scenario = scenario_driver
        self.tick = tick

    def read(self) -> Observation:
        self.tick += 1

        # 基线 + 正弦波动 + 噪声
        temperature = round(24.0 + 2 * math.sin(self.tick / 50) + random.uniform(-0.3, 0.3), 1)
        humidity = round(55.0 + 10 * math.sin(self.tick / 60) + random.uniform(-2, 2), 1)
        light = int(max(0, 450 + 150 * math.sin(self.tick / 40) + random.uniform(-30, 30)))
        co2 = int(450 + 80 * math.sin(self.tick / 70) + random.uniform(-20, 20))
        door_open = False

        # 场景驱动覆盖
        if self.scenario is not None:
            env_state = self.scenario.get_environment_state()
            if env_state:
                temperature = env_state.get("temperature", temperature)
                humidity = env_state.get("humidity", humidity)
                light = env_state.get("light", light)
                co2 = env_state.get("co2", co2)
                door_open = env_state.get("door_open", door_open)

        # 空气质量分级
        if co2 < 600:
            air_quality = "good"
        elif co2 < 1000:
            air_quality = "moderate"
        else:
            air_quality = "bad"

        data: Dict[str, Any] = {
            "temperature": temperature,
            "humidity": humidity,
            "light": light,
            "co2": co2,
            "door_open": door_open,
            "air_quality": air_quality,
        }

        quality = Quality(confidence=0.97, latency_ms=5, degraded=False)

        return Observation(
            source_type=self.SOURCE_TYPE,
            data=data,
            quality=quality,
        )
