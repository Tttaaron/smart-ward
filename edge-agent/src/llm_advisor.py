"""LLM 智能决策顾问模块

将轻量 LLM 能力嵌入边缘代理主循环，提供三大核心功能：
  1. 事件语义增强 (enhance_event)：为规则引擎产出的事件补充自然语言描述与处置建议
  2. 实时护理建议 (nursing_advice)：基于当前事件上下文生成即时护理指导
  3. 离线自治决策 (offline_decision)：断网时对多事件进行优先级排序与应急处置

设计原则：
  - 非阻塞：LLM 推理失败不阻塞主循环，降级为无增强模式
  - 可观测：每次推理记录 TTFT/内存/耗时，health 心跳上报
  - 可替换：通过 LLMEngine 抽象，mock/real 无缝切换

对齐赛题要求：
  - 边缘端毫秒级感知与初步决策
  - 离线/弱网环境下业务基本可用性
  - TTFT < 200ms，内存 ≤ 1.5GB
"""

import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from llm_engine import LLMEngine, LLMResponse


# 系统提示词：定义 LLM 在病房场景中的角色
SYSTEM_PROMPT = """你是智慧病房护理助手。根据事件快速输出：状况、紧急程度（紧急/警告/提醒）、最多3条护理建议。总字数不超过60字。只做护理建议，不做诊断。"""

# 事件类型中文映射
EVENT_TYPE_CN = {
    "fall_suspected": "疑似跌倒",
    "nurse_call": "护士呼叫",
    "bed_leave": "离床",
    "door_departure": "门区异常离开",
    "night_wandering": "夜间徘徊",
    "environment_anomaly": "环境异常",
    "node_offline": "节点失联",
    "fall_prediction": "坠床预警",
    "long_still": "长时间静止",
    "abnormal_posture": "异常体态",
    "seizure": "抽搐检测",
    "bedsore_risk": "压疮风险",
    "device_fault": "设备故障",
}

# 事件优先级中文
PRIORITY_CN = {"P1": "紧急", "P2": "高优先级", "P3": "提醒"}


@dataclass
class EventEnhancement:
    """事件语义增强结果"""
    event_id: str
    summary: str = ""              # 一句话状况描述
    advice: str = ""               # 处置建议
    urgency: str = ""              # 紧急程度
    llm_response: Optional[LLMResponse] = None
    enhanced: bool = False         # 是否成功增强
    latency_ms: float = 0.0       # 增强耗时

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "event_id": self.event_id,
            "summary": self.summary,
            "advice": self.advice,
            "urgency": self.urgency,
            "enhanced": self.enhanced,
            "latency_ms": round(self.latency_ms, 1),
        }
        if self.llm_response:
            d["llm_metrics"] = self.llm_response.to_dict()
        return d


@dataclass
class OfflineDecision:
    """离线自治决策结果"""
    prioritized_events: List[Dict[str, Any]] = field(default_factory=list)
    emergency_actions: List[str] = field(default_factory=list)
    reasoning: str = ""
    llm_response: Optional[LLMResponse] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prioritized_events": self.prioritized_events,
            "emergency_actions": self.emergency_actions,
            "reasoning": self.reasoning,
        }


class LLMAdvisor:
    """LLM 智能决策顾问

    嵌入 EdgeAgent 主循环，在事件融合后提供语义增强与决策支持。
    """

    def __init__(self, node_id: str, bed_id: str, ward_id: str):
        self.node_id = node_id
        self.bed_id = bed_id
        self.ward_id = ward_id
        self.engine = LLMEngine()

        # 统计
        self.total_enhancements = 0
        self.successful_enhancements = 0
        self.total_advice_ms = 0.0

        print(f"[{self.node_id}] LLMAdvisor 初始化 (mode={self.engine.mode})")

    @property
    def is_ready(self) -> bool:
        return self.engine.is_ready

    def enhance_event(self, event_dict: Dict[str, Any],
                      observations: List[Dict[str, Any]] = None) -> EventEnhancement:
        """事件语义增强：为安全事件补充自然语言描述与处置建议

        Args:
            event_dict: SafetyEvent.to_dict() 的输出
            observations: 当前周期的观测数据摘要

        Returns:
            EventEnhancement: 增强结果（失败时 enhanced=False，不阻塞主流程）
        """
        t0 = time.time()
        event_id = event_dict.get("event_id", "unknown")
        event_type = event_dict.get("event_type", "unknown")
        confidence = event_dict.get("confidence", 0.0)
        priority = event_dict.get("priority", "P3")

        enhancement = EventEnhancement(event_id=event_id)

        try:
            # 构造 prompt
            prompt = self._build_event_prompt(event_dict, observations)

            # 调用 LLM
            resp = self.engine.generate(prompt, system=SYSTEM_PROMPT, max_tokens=64)

            # 解析响应
            enhancement.summary = self._extract_summary(resp.text)
            enhancement.advice = resp.text
            enhancement.urgency = PRIORITY_CN.get(priority, "提醒")
            enhancement.llm_response = resp
            enhancement.enhanced = True
            enhancement.latency_ms = (time.time() - t0) * 1000

            self.successful_enhancements += 1

        except Exception as e:
            # LLM 失败不阻塞主流程
            enhancement.enhanced = False
            enhancement.latency_ms = (time.time() - t0) * 1000
            enhancement.summary = f"{EVENT_TYPE_CN.get(event_type, event_type)}（置信度{confidence:.0%}）"
            enhancement.advice = "建议人工查看"
            enhancement.urgency = PRIORITY_CN.get(priority, "提醒")

        self.total_enhancements += 1
        self.total_advice_ms += enhancement.latency_ms
        return enhancement

    def nursing_advice(self, event_dict: Dict[str, Any],
                       patient_context: Dict[str, Any] = None) -> str:
        """实时护理建议生成

        Args:
            event_dict: 当前触发的事件
            patient_context: 患者上下文（病史、用药等，演示阶段为空）

        Returns:
            str: 护理建议文本
        """
        try:
            event_type = event_dict.get("event_type", "")
            event_cn = EVENT_TYPE_CN.get(event_type, event_type)
            bed_id = event_dict.get("bed_id", self.bed_id)

            prompt = (
                f"床位{bed_id}触发【{event_cn}】事件，"
                f"置信度{event_dict.get('confidence', 0):.0%}，"
                f"优先级{event_dict.get('priority', 'P3')}。"
            )
            if patient_context:
                prompt += f"患者信息：{patient_context}。"
            prompt += "请给出处置建议。"

            resp = self.engine.generate(prompt, system=SYSTEM_PROMPT, max_tokens=48)
            return resp.text
        except Exception:
            return "建议立即查看患者情况。"

    def offline_decision(self, pending_events: List[Dict[str, Any]]) -> OfflineDecision:
        """离线自治决策：断网时对积压事件进行智能排序与应急处置

        Args:
            pending_events: 离线积压的事件列表

        Returns:
            OfflineDecision: 优先级排序 + 应急动作列表
        """
        decision = OfflineDecision()

        if not pending_events:
            return decision

        try:
            # 构造多事件决策 prompt
            events_desc = []
            for i, evt in enumerate(pending_events[:5], 1):  # 最多取 5 条
                evt_cn = EVENT_TYPE_CN.get(evt.get("event_type", ""), evt.get("event_type", ""))
                events_desc.append(
                    f"{i}. [{evt.get('priority', 'P3')}]{evt_cn} "
                    f"置信度{evt.get('confidence', 0):.0%} "
                    f"时间{evt.get('occurred_at', '未知')}"
                )

            prompt = (
                f"当前处于离线模式，有以下{len(pending_events)}个待处理事件：\n"
                + "\n".join(events_desc) +
                "\n请按紧急程度排序并给出处置优先级和应急动作。"
            )

            resp = self.engine.generate(prompt, system=SYSTEM_PROMPT, max_tokens=64)
            decision.reasoning = resp.text
            decision.llm_response = resp

            # 基于规则的优先级排序（LLM 建议作为补充）
            decision.prioritized_events = self._rule_based_priority(pending_events)
            decision.emergency_actions = self._extract_emergency_actions(pending_events)

        except Exception as e:
            # 降级为纯规则排序
            decision.prioritized_events = self._rule_based_priority(pending_events)
            decision.emergency_actions = self._extract_emergency_actions(pending_events)
            decision.reasoning = f"LLM 不可用，使用规则排序: {e}"

        return decision

    def should_offload_to_cloud(self, event_dict: Dict[str, Any]) -> bool:
        """判断事件是否应卸载到云端大模型处理

        路由策略（对齐赛题"云边协同推理"要求）：
          - 置信度 < 0.7 → 需要云端二次研判
          - P1 事件且置信度 < 0.85 → 云端复核
          - 多事件冲突 → 云端全局决策
          - 新型/罕见事件 → 云端全量模型分析

        Returns:
            bool: True 表示应卸载到云端
        """
        confidence = event_dict.get("confidence", 1.0)
        priority = event_dict.get("priority", "P3")
        event_type = event_dict.get("event_type", "")

        # 低置信度 → 云端
        if confidence < 0.7:
            return True

        # P1 高优但置信度不够高 → 云端复核
        if priority == "P1" and confidence < 0.85:
            return True

        # 罕见事件类型 → 云端
        rare_events = {"seizure", "bedsore_risk", "abnormal_posture"}
        if event_type in rare_events and confidence < 0.8:
            return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """获取 Advisor 状态（用于 health 上报）"""
        avg_ms = (self.total_advice_ms / self.total_enhancements
                  if self.total_enhancements > 0 else 0)
        return {
            "engine": self.engine.get_status(),
            "total_enhancements": self.total_enhancements,
            "successful_enhancements": self.successful_enhancements,
            "avg_enhancement_ms": round(avg_ms, 1),
        }

    # ─── 内部方法 ───

    def _build_event_prompt(self, event_dict: Dict[str, Any],
                            observations: List[Dict[str, Any]] = None) -> str:
        """构造事件增强 prompt"""
        event_type = event_dict.get("event_type", "unknown")
        event_cn = EVENT_TYPE_CN.get(event_type, event_type)
        confidence = event_dict.get("confidence", 0)
        priority = event_dict.get("priority", "P3")
        bed_id = event_dict.get("bed_id", self.bed_id)
        details = event_dict.get("details", {})
        rule_hits = event_dict.get("rule_hits", [])

        prompt = f"床位{bed_id}检测到【{event_cn}】事件。\n"
        prompt += f"置信度: {confidence:.0%}，优先级: {priority}\n"

        if rule_hits:
            prompt += f"触发规则: {', '.join(rule_hits)}\n"

        if details:
            detail_str = "; ".join(f"{k}={v}" for k, v in list(details.items())[:5])
            prompt += f"详细数据: {detail_str}\n"

        if observations:
            obs_summary = []
            for obs in observations[:3]:
                src = obs.get("source_type", "")
                data = obs.get("data", {})
                # 只取关键字段
                if src == "camera":
                    obs_summary.append(f"摄像头: 姿态={data.get('posture', 'N/A')}")
                elif src == "bed_sensor":
                    obs_summary.append(f"床垫: 在床={data.get('on_bed', 'N/A')}")
                elif src == "environment":
                    obs_summary.append(f"环境: 温度={data.get('temperature', 'N/A')}°C")
            if obs_summary:
                prompt += f"传感器: {'; '.join(obs_summary)}\n"

        prompt += "请给出一句话状况描述和处置建议。"
        return prompt

    def _extract_summary(self, text: str) -> str:
        """从 LLM 响应中提取一句话摘要"""
        # 取第一行或第一个句号前的内容
        lines = text.strip().split("\n")
        first_line = lines[0] if lines else text
        # 去掉可能的前缀标记
        for prefix in ["【紧急】", "【警告】", "【提醒】", "【决策】"]:
            if first_line.startswith(prefix):
                return first_line
        # 截取前 50 字符
        return first_line[:50]

    def _rule_based_priority(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """基于规则的优先级排序"""
        priority_order = {"P1": 0, "P2": 1, "P3": 2}
        sorted_events = sorted(
            events,
            key=lambda e: (
                priority_order.get(e.get("priority", "P3"), 3),
                -e.get("confidence", 0),
            )
        )
        return [{"event_id": e.get("event_id"), "event_type": e.get("event_type"),
                 "priority": e.get("priority"), "confidence": e.get("confidence")}
                for e in sorted_events]

    def _extract_emergency_actions(self, events: List[Dict[str, Any]]) -> List[str]:
        """提取应急动作列表"""
        actions = []
        for evt in events:
            evt_type = evt.get("event_type", "")
            if evt_type in ("fall_suspected", "seizure"):
                actions.append(f"立即前往{evt.get('bed_id', '')}查看患者")
            elif evt_type == "nurse_call":
                actions.append(f"响应{evt.get('bed_id', '')}呼叫")
            elif evt_type == "door_departure":
                actions.append(f"确认{evt.get('bed_id', '')}患者去向")
        return actions[:3]  # 最多 3 条
