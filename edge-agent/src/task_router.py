"""云边协同任务路由器

实现赛题要求的"云边协同推理与任务调度"核心能力：
  - 多维感知：网络状态、任务复杂度、边缘负载、云端可用性
  - 动态路由：为每个推理任务寻优最佳计算路径（边缘/云端）
  - 不确定性处理：网络波动时自动降级到边缘自治
  - 策略调整：基于历史延迟与成功率动态调整路由阈值

路由决策模型：
  score_edge = w1*confidence + w2*(1-complexity) + w3*network_penalty
  score_cloud = 1 - score_edge

  当 score_edge > threshold 时本地处理，否则卸载到云端。
  网络不可用时强制本地处理（保障业务连续性）。

对齐赛题指标：
  - 网络波动期间基本业务功能保持率 ≥ 90%
  - 端到端时延 ≤ 0.2s（边缘路径）
  - 决策冲突比例 ≤ 5%
"""

import os
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from collections import deque


class ComputeTarget(str, Enum):
    """计算目标"""
    EDGE = "edge"          # 边缘端本地处理
    CLOUD = "cloud"        # 卸载到云端大模型
    HYBRID = "hybrid"      # 边缘初筛 + 云端复核


class NetworkState(str, Enum):
    """网络状态"""
    CONNECTED = "connected"        # 正常连接
    DEGRADED = "degraded"          # 高延迟/丢包
    DISCONNECTED = "disconnected"  # 完全断开


@dataclass
class RoutingDecision:
    """路由决策结果"""
    target: ComputeTarget
    reason: str
    confidence: float              # 事件置信度
    complexity_score: float        # 任务复杂度 0~1
    network_state: NetworkState
    edge_score: float              # 边缘处理得分
    estimated_latency_ms: float    # 预估延迟
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "complexity_score": round(self.complexity_score, 3),
            "network_state": self.network_state.value,
            "edge_score": round(self.edge_score, 3),
            "estimated_latency_ms": round(self.estimated_latency_ms, 1),
        }


@dataclass
class RouterMetrics:
    """路由器累计指标"""
    total_decisions: int = 0
    edge_decisions: int = 0
    cloud_decisions: int = 0
    hybrid_decisions: int = 0
    cloud_offload_failed: int = 0     # 云端卸载失败（回退边缘）
    cloud_offload_succeeded: int = 0
    avg_edge_latency_ms: float = 0.0
    avg_cloud_latency_ms: float = 0.0
    network_uptime_ratio: float = 1.0  # 网络可用率
    _edge_latency_sum: float = field(default=0.0, repr=False)
    _cloud_latency_sum: float = field(default=0.0, repr=False)
    _cloud_result_count: int = field(default=0, repr=False)
    _connected_ticks: int = field(default=0, repr=False)
    _total_ticks: int = field(default=0, repr=False)

    def record_decision(self, decision: RoutingDecision) -> None:
        self.total_decisions += 1
        if decision.target == ComputeTarget.EDGE:
            self.edge_decisions += 1
        elif decision.target == ComputeTarget.CLOUD:
            self.cloud_decisions += 1
        else:
            self.hybrid_decisions += 1

    def record_latency(self, target: ComputeTarget, latency_ms: float) -> None:
        if target == ComputeTarget.EDGE:
            self._edge_latency_sum += latency_ms
            if self.edge_decisions > 0:
                self.avg_edge_latency_ms = self._edge_latency_sum / self.edge_decisions
        elif target == ComputeTarget.CLOUD:
            self._cloud_latency_sum += latency_ms
            self._cloud_result_count += 1
            self.avg_cloud_latency_ms = self._cloud_latency_sum / self._cloud_result_count

    def record_network_tick(self, connected: bool) -> None:
        self._total_ticks += 1
        if connected:
            self._connected_ticks += 1
        if self._total_ticks > 0:
            self.network_uptime_ratio = self._connected_ticks / self._total_ticks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_decisions": self.total_decisions,
            "edge_decisions": self.edge_decisions,
            "cloud_decisions": self.cloud_decisions,
            "hybrid_decisions": self.hybrid_decisions,
            "cloud_offload_failed": self.cloud_offload_failed,
            "cloud_offload_succeeded": self.cloud_offload_succeeded,
            "avg_edge_latency_ms": round(self.avg_edge_latency_ms, 1),
            "avg_cloud_latency_ms": round(self.avg_cloud_latency_ms, 1),
            "network_uptime_ratio": round(self.network_uptime_ratio, 4),
        }


class TaskRouter:
    """云边协同任务路由器

    每个周期根据当前网络状态、事件特征和系统负载，
    决定推理事件在边缘端处理还是卸载到云端。

    环境变量：
      ROUTER_EDGE_THRESHOLD   边缘处理阈值（默认 0.65）
      ROUTER_CLOUD_TIMEOUT_S  云端响应超时秒数（默认 2.0）
      ROUTER_DEGRADED_LATENCY_MS  网络降级延迟阈值（默认 500）
    """

    # 事件复杂度权重（越复杂越需要云端）
    EVENT_COMPLEXITY = {
        "fall_suspected": 0.7,
        "seizure": 0.85,
        "fall_prediction": 0.8,
        "abnormal_posture": 0.75,
        "bed_leave": 0.3,
        "night_wandering": 0.4,
        "door_departure": 0.35,
        "environment_anomaly": 0.2,
        "nurse_call": 0.1,
        "long_still": 0.3,
        "bedsore_risk": 0.6,
        "device_fault": 0.15,
        "node_offline": 0.1,
    }

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.edge_threshold = float(os.getenv("ROUTER_EDGE_THRESHOLD", "0.65"))
        self.cloud_timeout_s = float(os.getenv("ROUTER_CLOUD_TIMEOUT_S", "2.0"))
        self.degraded_latency_ms = float(os.getenv("ROUTER_DEGRADED_LATENCY_MS", "500"))

        # 网络状态追踪
        self._network_state = NetworkState.CONNECTED
        self._last_heartbeat_ok = True
        self._consecutive_failures = 0
        self._latency_window: deque = deque(maxlen=20)  # 最近 20 次延迟

        # 冲突检测
        self._recent_events: deque = deque(maxlen=10)  # 最近事件窗口
        self._conflict_count = 0
        self._total_event_count = 0

        # 指标
        self.metrics = RouterMetrics()

        print(f"[{self.node_id}] TaskRouter 初始化 (threshold={self.edge_threshold})")

    def update_network_state(self, mqtt_connected: bool, latency_ms: float = 0) -> None:
        """更新网络状态（每个 tick 由主循环调用）

        Args:
            mqtt_connected: MQTT 连接状态
            latency_ms: 最近一次通信延迟
        """
        self.metrics.record_network_tick(mqtt_connected)

        if not mqtt_connected:
            self._consecutive_failures += 1
            if self._consecutive_failures >= 3:
                self._network_state = NetworkState.DISCONNECTED
            else:
                self._network_state = NetworkState.DEGRADED
        else:
            self._consecutive_failures = 0
            if latency_ms > 0:
                self._latency_window.append(latency_ms)
            # 判断是否降级
            avg_latency = (sum(self._latency_window) / len(self._latency_window)
                          if self._latency_window else 0)
            if avg_latency > self.degraded_latency_ms:
                self._network_state = NetworkState.DEGRADED
            else:
                self._network_state = NetworkState.CONNECTED

    def route(self, event_dict: Dict[str, Any]) -> RoutingDecision:
        """为事件做路由决策

        Args:
            event_dict: SafetyEvent.to_dict() 输出

        Returns:
            RoutingDecision: 路由决策（目标、原因、预估延迟）
        """
        confidence = event_dict.get("confidence", 0.5)
        event_type = event_dict.get("event_type", "")
        priority = event_dict.get("priority", "P3")

        # 计算任务复杂度
        complexity = self.EVENT_COMPLEXITY.get(event_type, 0.5)

        # 网络惩罚因子（网络差时倾向边缘）
        network_penalty = self._network_penalty()

        # 边缘处理得分
        # 高置信度 + 低复杂度 + 网络差 → 倾向边缘
        edge_score = (
            0.4 * confidence +
            0.3 * (1 - complexity) +
            0.3 * network_penalty
        )

        # 记录冲突检测
        self._total_event_count += 1
        self._recent_events.append(event_dict)

        # 路由决策
        if self._network_state == NetworkState.DISCONNECTED:
            # 断网：强制边缘
            decision = RoutingDecision(
                target=ComputeTarget.EDGE,
                reason="网络断开，边缘自治",
                confidence=confidence,
                complexity_score=complexity,
                network_state=self._network_state,
                edge_score=1.0,
                estimated_latency_ms=50.0,
            )
        elif edge_score >= self.edge_threshold:
            # 边缘处理
            est_latency = 30 + complexity * 70  # 30-100ms
            decision = RoutingDecision(
                target=ComputeTarget.EDGE,
                reason=f"边缘得分{edge_score:.2f}≥阈值{self.edge_threshold}",
                confidence=confidence,
                complexity_score=complexity,
                network_state=self._network_state,
                edge_score=edge_score,
                estimated_latency_ms=est_latency,
            )
        elif priority == "P1" and confidence < 0.85:
            # P1 低置信度：混合模式（边缘先响应，云端复核）
            decision = RoutingDecision(
                target=ComputeTarget.HYBRID,
                reason=f"P1事件置信度{confidence:.2f}<0.85，边缘+云端复核",
                confidence=confidence,
                complexity_score=complexity,
                network_state=self._network_state,
                edge_score=edge_score,
                estimated_latency_ms=150.0,
            )
        else:
            # 云端处理
            est_latency = 100 + complexity * 200  # 100-300ms
            decision = RoutingDecision(
                target=ComputeTarget.CLOUD,
                reason=f"边缘得分{edge_score:.2f}<阈值{self.edge_threshold}，复杂度高",
                confidence=confidence,
                complexity_score=complexity,
                network_state=self._network_state,
                edge_score=edge_score,
                estimated_latency_ms=est_latency,
            )

        self.metrics.record_decision(decision)
        return decision

    def detect_conflict(self, new_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """检测多事件决策冲突

        冲突场景：
          - 同一床位短时间内矛盾事件（如"离床"和"长时间静止"同时存在）
          - 相邻床位事件关联性（如多人同时跌倒→可能是设备故障）

        Returns:
            冲突信息 dict 或 None（无冲突）
        """
        if not self._recent_events:
            return None

        new_type = new_event.get("event_type", "")
        new_bed = new_event.get("bed_id", "")

        # 矛盾事件对
        CONFLICT_PAIRS = {
            frozenset({"bed_leave", "long_still"}),
            frozenset({"fall_suspected", "abnormal_posture"}),
            frozenset({"night_wandering", "long_still"}),
        }

        for recent in self._recent_events:
            recent_type = recent.get("event_type", "")
            recent_bed = recent.get("bed_id", "")

            # 同床位矛盾事件
            if recent_bed == new_bed:
                pair = frozenset({new_type, recent_type})
                if pair in CONFLICT_PAIRS:
                    self._conflict_count += 1
                    return {
                        "type": "contradiction",
                        "event_a": recent_type,
                        "event_b": new_type,
                        "bed_id": new_bed,
                        "resolution": "以高置信度事件为准，建议云端复核",
                    }

        return None

    def get_conflict_ratio(self) -> float:
        """获取决策冲突比例（对齐赛题 ≤5% 指标）"""
        if self._total_event_count == 0:
            return 0.0
        return self._conflict_count / self._total_event_count

    def record_cloud_result(self, event_id: str, success: bool, latency_ms: float) -> None:
        """记录云端处理结果（用于动态调整策略）"""
        if success:
            self.metrics.cloud_offload_succeeded += 1
            self.metrics.record_latency(ComputeTarget.CLOUD, latency_ms)
        else:
            self.metrics.cloud_offload_failed += 1
            # 连续失败时提高边缘阈值（更倾向本地处理）
            if self.metrics.cloud_offload_failed >= 3:
                self.edge_threshold = max(0.4, self.edge_threshold - 0.05)
                print(f"[{self.node_id}] 云端连续失败，降低边缘阈值至 {self.edge_threshold:.2f}")

    def get_status(self) -> Dict[str, Any]:
        """获取路由器状态（用于 health 上报）"""
        return {
            "network_state": self._network_state.value,
            "edge_threshold": self.edge_threshold,
            "conflict_ratio": round(self.get_conflict_ratio(), 4),
            "conflict_count": self._conflict_count,
            "metrics": self.metrics.to_dict(),
        }

    # ─── 内部方法 ───

    def _network_penalty(self) -> float:
        """网络惩罚因子：网络越差，越倾向边缘（返回 0~1）"""
        if self._network_state == NetworkState.DISCONNECTED:
            return 1.0
        elif self._network_state == NetworkState.DEGRADED:
            return 0.7
        else:
            # 根据平均延迟微调
            if self._latency_window:
                avg = sum(self._latency_window) / len(self._latency_window)
                if avg > 200:
                    return 0.5
            return 0.2
