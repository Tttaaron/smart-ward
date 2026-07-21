"""场景脚本驱动器

读取环境变量 SCENARIO_PROFILE（逗号分隔的事件类型列表），
按节奏触发对应场景，向适配器注入模拟状态。

docker-compose.yml 已编排：
- B01: fall,nurse_call
- B02: bed_leave,night_wandering
- B03: environment_anomaly,door_departure

场景生命周期：开始 -> 持续 -> 恢复 -> 人工确认
（本骨架仅实现状态注入，景彬后续补充完整 4 阶段脚本）
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SceneState:
    """单个场景的运行时状态"""
    scene_type: str
    phase: str = "idle"             # idle / started / sustained / recovering / confirmed
    started_tick: int = 0
    duration_ticks: int = 5         # 持续周期数
    elapsed_ticks: int = 0

    def is_active(self) -> bool:
        return self.phase in ("started", "sustained")


class ScenarioDriver:
    """场景脚本驱动器

    根据 SCENARIO_PROFILE 环境变量初始化场景列表，
    每 tick 推进场景状态机，并向各适配器提供当前场景状态。

    场景类型（对齐 contracts/safety_event.json 的 event_type）：
        fall_suspected / nurse_call / bed_leave / infusion_anomaly /
        door_departure / night_wandering / environment_anomaly
    """

    # 场景类型 -> 默认持续周期数（每周期 TICK_SECONDS 秒）
    SCENE_DURATIONS = {
        "fall_suspected": 3,
        "nurse_call": 2,
        "bed_leave": 8,
        "infusion_anomaly": 6,
        "door_departure": 4,
        "night_wandering": 10,
        "environment_anomaly": 6,
        # ─── 新增患者安全场景 ───
        "fall_prediction": 4,      # 坠床预警（事前）
        "long_still": 8,           # 长时间静止
        "abnormal_posture": 5,     # 异常体态
        "seizure": 3,              # 抽搐检测
        "bedsore_risk": 10,        # 压疮预防
        "device_fault": 5,         # 设备故障
    }

    def __init__(self):
        profile = os.getenv("SCENARIO_PROFILE", "")
        self.scene_types: List[str] = [s.strip() for s in profile.split(",") if s.strip()]
        self.scenes: Dict[str, SceneState] = {
            st: SceneState(scene_type=st, duration_ticks=self.SCENE_DURATIONS.get(st, 5))
            for st in self.scene_types
        }
        self.tick_count = 0
        # 当前激活的场景（轮转触发，每次只激活一个）
        self._current_idx = 0
        self._current_scene: Optional[SceneState] = None

    def tick(self) -> None:
        """每周期调用一次，推进场景状态机"""
        self.tick_count += 1

        # 无场景配置：返回
        if not self.scenes:
            return

        # 当前无激活场景：尝试启动下一个
        if self._current_scene is None:
            scene_types = list(self.scenes.values())
            self._current_scene = scene_types[self._current_idx % len(scene_types)]
            self._current_scene.phase = "started"
            self._current_scene.started_tick = self.tick_count
            self._current_scene.elapsed_ticks = 0
            self._current_idx += 1
            print(f"[scenario] 启动场景: {self._current_scene.scene_type} (tick={self.tick_count})")
            return

        # 当前场景进行中：推进
        sc = self._current_scene
        sc.elapsed_ticks += 1

        # started -> sustained（第 2 tick 起）
        if sc.phase == "started":
            sc.phase = "sustained"
        # sustained -> recovering（达到持续周期）
        elif sc.phase == "sustained" and sc.elapsed_ticks >= sc.duration_ticks:
            sc.phase = "recovering"
            print(f"[scenario] 场景恢复: {sc.scene_type} (tick={self.tick_count})")
        # recovering -> idle（恢复 1 周期后结束）
        elif sc.phase == "recovering":
            sc.phase = "idle"
            self._current_scene = None

    def _active_scene(self) -> Optional[SceneState]:
        """返回当前激活的场景（started/sustained/recovering）"""
        if self._current_scene and self._current_scene.is_active():
            return self._current_scene
        if self._current_scene and self._current_scene.phase == "recovering":
            return self._current_scene
        return None

    def get_camera_state(self) -> Dict[str, Any]:
        """返回摄像头场景注入状态"""
        sc = self._active_scene()
        if sc is None:
            return {}

        if sc.scene_type == "fall_suspected":
            # 跌倒：姿态 lying + 高跌倒分
            return {
                "presence": True,
                "person_count": 1,
                "posture": "falling" if sc.phase != "recovering" else "sitting",
                "fall_score": 0.85 if sc.phase != "recovering" else 0.1,
                "degraded": False,
            }
        if sc.scene_type == "night_wandering":
            # 夜间徘徊：有人 + standing
            return {
                "presence": True,
                "person_count": 1,
                "posture": "standing" if sc.phase != "recovering" else "lying",
                "fall_score": 0.1,
                "degraded": True,  # 低照度降级
            }
        if sc.scene_type == "nurse_call":
            return {"presence": True, "person_count": 1, "posture": "sitting", "fall_score": 0.0}
        # ─── 坠床预警：床位占床 + 姿态=lying_edge + fall_score ───
        if sc.scene_type == "fall_prediction":
            return {
                "presence": True,
                "person_count": 1,
                "posture": "lying_edge" if sc.phase != "recovering" else "sitting",
                "fall_score": 0.7 if sc.phase != "recovering" else 0.1,
                "tremor_score": 0.0,
                "degraded": False,
            }
        # ─── 长时间静止：同一体位持续 ───
        if sc.scene_type == "long_still":
            # 模拟持续 6 分钟（360s），超过 LONG_STILL_SECONDS 默认 300s
            duration = 360 if sc.phase != "recovering" else 10
            return {
                "presence": True,
                "person_count": 1,
                "posture": "sitting",
                "fall_score": 0.0,
                "tremor_score": 0.0,
                "position_duration": duration,
                "degraded": False,
            }
        # ─── 异常体态：蜷缩 ───
        if sc.scene_type == "abnormal_posture":
            return {
                "presence": True,
                "person_count": 1,
                "posture": "curled" if sc.phase != "recovering" else "sitting",
                "fall_score": 0.0,
                "tremor_score": 0.0,
                "degraded": False,
            }
        # ─── 抽搐检测：tremor_score 高 ───
        if sc.scene_type == "seizure":
            return {
                "presence": True,
                "person_count": 1,
                "posture": "seizing" if sc.phase != "recovering" else "lying",
                "fall_score": 0.0,
                "tremor_score": 0.85 if sc.phase != "recovering" else 0.1,
                "degraded": False,
            }
        # ─── 压疮预防：同一体位持续 2 小时以上 ───
        if sc.scene_type == "bedsore_risk":
            # 模拟持续 2.5 小时（9000s），超过 BEDSORE_DURATION 默认 7200s
            duration = 9000 if sc.phase != "recovering" else 100
            return {
                "presence": True,
                "person_count": 1,
                "posture": "lying",
                "fall_score": 0.0,
                "tremor_score": 0.0,
                "position_duration": duration,
                "degraded": False,
            }
        return {}

    def get_bed_state(self) -> Dict[str, Any]:
        """返回床位传感器场景注入状态"""
        sc = self._active_scene()
        if sc is None:
            return {}

        if sc.scene_type == "bed_leave":
            absence = 0 if sc.phase == "started" else sc.elapsed_ticks * int(os.getenv("TICK_SECONDS", "3"))
            return {
                "occupied": False,
                "absence_seconds": absence,
            }
        if sc.scene_type == "fall_suspected":
            # 跌倒通常伴随离床
            return {"occupied": False, "absence_seconds": sc.elapsed_ticks * 3}
        return {}

    def get_infusion_state(self) -> Dict[str, Any]:
        """返回输液场景注入状态"""
        sc = self._active_scene()
        if sc is None:
            return {}

        if sc.scene_type == "infusion_anomaly":
            # 滴速异常（过快）+ 低液位
            if sc.phase == "recovering":
                return {"flow_rate": 50.0, "volume_pct": 80.0}
            return {"flow_rate": 100.0, "volume_pct": 3.0}
        return {}

    def get_environment_state(self) -> Dict[str, Any]:
        """返回环境场景注入状态"""
        sc = self._active_scene()
        if sc is None:
            return {}

        if sc.scene_type == "environment_anomaly":
            if sc.phase == "recovering":
                return {"temperature": 24.0, "humidity": 55.0, "light": 450, "co2": 450, "door_open": False}
            return {"temperature": 29.5, "humidity": 78.0, "light": 50, "co2": 1250, "door_open": False}
        if sc.scene_type == "door_departure":
            return {"door_open": True if sc.phase != "recovering" else False}
        return {}
