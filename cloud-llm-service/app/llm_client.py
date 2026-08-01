"""LLM客户端 - 支持 mock 和真实 vLLM 两种模式

Mock 模式: 基于规则的事件研判，无需GPU，即时可用
Real 模式: 调用 Qwen2.5-14B via vLLM API
"""

import logging
import os
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ─── 护理建议模板 ───

ADVICE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "fall_suspected": {
        "confirm": "检测到患者跌倒，建议立即前往床位检查伤情，必要时启动急救流程。",
        "reject": "经过二次研判，患者姿态变化非真实跌倒，可能为弯腰捡物或摄像头误判。",
        "escalate": "跌倒检测置信度不足，但存在高风险因素，建议升级为主管医生关注。",
    },
    "fall_prediction": {
        "confirm": "患者处于床沿危险位置，坠床风险高，建议立即协助调整体位。",
        "reject": "患者正常坐于床边，无坠床风险，姿势在安全范围内。",
        "escalate": "患者长时间停留床沿，虽未达到预警阈值，建议提前干预。",
    },
    "seizure": {
        "confirm": "检测到疑似癫痫发作特征，请立即前往病房评估，必要时呼叫神经内科会诊。",
        "reject": "肢体动作属正常翻身或睡眠动作，非病理性抽搐。",
        "escalate": "不排除轻微震颤可能，建议持续观察并记录发作时长。",
    },
    "bed_leave": {
        "confirm": "患者已离床，需确认是否由护理人员协助下床活动。",
        "reject": "离床为正常活动，患者状态良好。",
        "escalate": "离床时间较长未返回，建议确认患者去向。",
    },
    "long_still": {
        "confirm": "患者长时间未变换体位，存在压疮风险或意识状态改变，建议唤醒检查。",
        "reject": "患者处于正常睡眠状态，生命体征监测正常。",
        "escalate": "静息时间超出常规，建议增加巡视频率。",
    },
    "abnormal_posture": {
        "confirm": "患者体态异常，可能为急症早期信号，建议立即评估。",
        "reject": "异常体态为短暂姿势调整，已恢复正常。",
        "escalate": "体态轻微异常，建议纳入交接班重点关注。",
    },
}


class LLMClient:
    """LLM推理客户端"""

    def __init__(self, mode: str = "mock"):
        self.mode = mode
        self._model_name = "qwen2.5-14b"
        self._model_version = "awq-int4"
        logger.info(f"LLMClient initialized in {mode} mode")

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    def infer(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """执行推理并返回研判结果"""
        if self.mode == "mock":
            return self._mock_infer(request)
        elif self.mode == "vllm":
            return self._vllm_infer(request)
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

    def _mock_infer(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """基于规则的模拟推理

        根据事件类型和置信度给出合理判断：
        - 高置信度 P1 事件 → confirm
        - 低置信度事件 → reject（可能误报）
        - 模糊区间 → escalate
        """
        t0 = time.time()
        event_type = request.get("event_type", "")
        confidence = float(request.get("confidence", 0.5))
        priority = request.get("priority", "P2")

        # 判断逻辑
        if priority == "P1" and confidence >= 0.7:
            judgment = "confirm"
        elif confidence < 0.3:
            judgment = "reject"
        elif 0.3 <= confidence < 0.7:
            judgment = "escalate"
        elif priority == "P1":
            judgment = "escalate"
        else:
            judgment = "confirm"

        # 获取护理建议
        templates = ADVICE_TEMPLATES.get(event_type, {})
        advice = templates.get(judgment, f"事件类型 {event_type}，建议进行人工复核。")

        latency_ms = (time.time() - t0) * 1000

        return {
            "event_id": request.get("event_id", ""),
            "trace_id": request.get("trace_id", ""),
            "judgment": judgment,
            "confidence": round(confidence, 3),
            "advice": advice,
            "latency_ms": round(latency_ms, 1),
            "model_name": self._model_name,
            "model_version": self._model_version,
        }

    def _vllm_infer(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """调用 vLLM API 推理

        vLLM 部署后可通过 OpenAI-compatible API 调用:
          POST http://localhost:8000/v1/completions
        """
        import httpx

        t0 = time.time()
        event_type = request.get("event_type", "")
        event_details = request.get("details", {})
        llm_prompt = request.get("llm_prompt", "")

        prompt = llm_prompt or self._build_prompt(request)

        try:
            resp = httpx.post(
                os.getenv("VLLM_ENDPOINT", "http://localhost:8000/v1/completions"),
                json={
                    "model": "qwen2.5-14b-awq",
                    "prompt": prompt,
                    "max_tokens": 256,
                    "temperature": 0.1,
                },
                timeout=float(os.getenv("VLLM_TIMEOUT", "30")),
            )
            resp.raise_for_status()
            result = resp.json()
            text = result.get("choices", [{}])[0].get("text", "")
        except Exception as e:
            logger.error(f"vLLM inference failed: {e}, falling back to mock")
            return self._mock_infer(request)

        # 解析 LLM 输出（预期格式: judgment|confidence|advice）
        judgment, confidence, advice = self._parse_llm_output(text, request)

        latency_ms = (time.time() - t0) * 1000
        return {
            "event_id": request.get("event_id", ""),
            "trace_id": request.get("trace_id", ""),
            "judgment": judgment,
            "confidence": round(confidence, 3),
            "advice": advice,
            "latency_ms": round(latency_ms, 1),
            "model_name": self._model_name,
            "model_version": self._model_version,
        }

    def _build_prompt(self, request: Dict[str, Any]) -> str:
        """构建 LLM 提示词"""
        event_type = request.get("event_type", "unknown")
        priority = request.get("priority", "P2")
        confidence = request.get("confidence", 0.0)
        bed_id = request.get("bed_id", "")
        details = request.get("details", {})

        return (
            f"你是智慧病房的AI护理助手。边缘端报告了一起安全事件，请研判其真实性。\n\n"
            f"事件类型: {event_type}\n"
            f"优先级: {priority}\n"
            f"置信度: {confidence}\n"
            f"床位: {bed_id}\n"
            f"详情: {details}\n\n"
            f"请给出研判结果，格式为: judgment|confidence|advice\n"
            f"judgment 取值为 confirm(确认)/reject(误报)/escalate(升级)\n"
            f"advice 为针对此事件的护理建议。\n"
        )

    def _parse_llm_output(self, text: str, request: Dict[str, Any]) -> tuple:
        """解析 LLM 输出文本"""
        text = text.strip()
        parts = text.split("|")
        if len(parts) >= 2:
            judgment = parts[0].strip().lower()
            if judgment not in ("confirm", "reject", "escalate"):
                judgment = "escalate"
            try:
                confidence = float(parts[1])
            except ValueError:
                confidence = request.get("confidence", 0.5)
            advice = parts[2].strip() if len(parts) >= 3 else ""
        else:
            judgment = "escalate"
            confidence = request.get("confidence", 0.5)
            advice = text
        return judgment, max(0.0, min(1.0, confidence)), advice
