"""Cloud LLM adapter.

The service can run in a deterministic mock mode for integration tests, or call
an OpenAI-compatible vLLM endpoint for Qwen2.5-14B.
"""

import json
import logging
import os
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


ADVICE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "fall_suspected": {
        "confirm": "检测到患者疑似跌倒，建议立即前往床位检查伤情，必要时启动急救流程。",
        "reject": "二次研判认为该姿态变化不符合真实跌倒特征，建议继续观察并保留现场证据。",
        "escalate": "跌倒检测置信度不足但存在风险因素，建议升级给护士人工复核。",
    },
    "fall_prediction": {
        "confirm": "患者处于床沿危险位置，坠床风险较高，建议立即协助调整体位。",
        "reject": "患者姿态处于安全范围，暂未达到坠床预警条件。",
        "escalate": "患者长时间停留在床沿附近，建议提前干预并加强巡视。",
    },
    "seizure": {
        "confirm": "检测到疑似癫痫发作特征，请立即前往病房评估并呼叫医生。",
        "reject": "动作模式更接近正常翻身或睡眠动作，暂不判定为病理性抽搐。",
        "escalate": "不排除轻微异常动作，请持续观察并记录持续时间。",
    },
    "bed_leave": {
        "confirm": "患者已离床，请确认是否由护理人员协助下床活动。",
        "reject": "离床行为符合正常活动状态，暂不需要升级处置。",
        "escalate": "患者离床时间较长且状态不明确，建议确认患者去向。",
    },
    "night_wandering": {
        "confirm": "患者夜间活动异常，建议护士尽快查看并评估跌倒风险。",
        "reject": "夜间活动未达到异常阈值，建议继续监测。",
        "escalate": "夜间活动存在不确定风险，建议人工复核。",
    },
    "long_still": {
        "confirm": "患者长时间未变换体位，存在压疮或意识状态改变风险，建议唤醒检查。",
        "reject": "患者处于正常休息状态，当前监测指标未见明显异常。",
        "escalate": "静息时间偏长，建议增加巡视频率。",
    },
    "environment_anomaly": {
        "confirm": "病房环境指标异常，请检查温湿度、烟雾或设备状态。",
        "reject": "环境指标波动较小，暂不构成异常事件。",
        "escalate": "环境指标接近阈值，建议人工确认传感器状态。",
    },
    "door_departure": {
        "confirm": "检测到患者或人员异常离开门区，请尽快确认身份和去向。",
        "reject": "门区活动符合正常通行场景。",
        "escalate": "门区离开事件信息不足，建议护士站人工复核。",
    },
    "abnormal_posture": {
        "confirm": "患者体态异常，可能为急症早期信号，建议立即评估。",
        "reject": "异常体态为短暂姿势调整，已恢复正常。",
        "escalate": "体态轻微异常，建议纳入交接班重点关注。",
    },
}


class LLMClient:
    """Inference client used by the cloud MQTT consumer and debug API."""

    def __init__(self, mode: str = "mock"):
        self.mode = "vllm" if mode == "real" else mode
        self._model_name = os.getenv(
            "CLOUD_LLM_MODEL_NAME",
            "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4",
        )
        self._model_version = os.getenv("CLOUD_LLM_MODEL_VERSION", "gptq-int4")
        logger.info("LLMClient initialized in %s mode", self.mode)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    def infer(self, request: Dict[str, Any]) -> Dict[str, Any]:
        if self.mode == "mock":
            return self._mock_infer(request)
        if self.mode == "vllm":
            return self._vllm_infer(request)
        raise ValueError(f"Unknown LLM_MODE: {self.mode}")

    def _mock_infer(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic nursing-risk judgment for offline integration tests."""

        t0 = time.perf_counter()
        event_type = request.get("event_type", "")
        confidence = float(request.get("confidence", 0.5))
        priority = request.get("priority", "P2")

        if priority in {"P0", "P1"} and confidence >= 0.7:
            judgment = "confirm"
        elif confidence < 0.3:
            judgment = "reject"
        elif confidence < 0.7:
            judgment = "escalate"
        else:
            judgment = "confirm"

        templates = ADVICE_TEMPLATES.get(event_type, {})
        advice = templates.get(
            judgment,
            f"事件类型 {event_type or 'unknown'} 需要人工复核，请结合床位状态和历史记录处理。",
        )

        return {
            "event_id": request.get("event_id", ""),
            "trace_id": request.get("trace_id", ""),
            "judgment": judgment,
            "confidence": round(max(0.0, min(1.0, confidence)), 3),
            "advice": advice,
            "latency_ms": round(max((time.perf_counter() - t0) * 1000, 0.1), 1),
            "model_name": self._model_name,
            "model_version": self._model_version,
        }

    def _vllm_infer(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call an OpenAI-compatible vLLM chat/completions endpoint."""

        import httpx

        t0 = time.perf_counter()
        prompt = request.get("llm_prompt") or self._build_prompt(request)

        try:
            resp = httpx.post(
                os.getenv("VLLM_ENDPOINT", "http://localhost:8501/v1/chat/completions"),
                json={
                    "model": self._model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": int(os.getenv("VLLM_MAX_TOKENS", "128")),
                    "temperature": float(os.getenv("VLLM_TEMPERATURE", "0.1")),
                },
                timeout=float(os.getenv("VLLM_TIMEOUT", "30")),
            )
            resp.raise_for_status()
            result = resp.json()
            text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as exc:
            logger.error("vLLM inference failed, falling back to mock: %s", exc)
            return self._mock_infer(request)

        judgment, confidence, advice = self._parse_llm_output(text, request)
        return {
            "event_id": request.get("event_id", ""),
            "trace_id": request.get("trace_id", ""),
            "judgment": judgment,
            "confidence": round(confidence, 3),
            "advice": advice,
            "latency_ms": round(max((time.perf_counter() - t0) * 1000, 0.1), 1),
            "model_name": self._model_name,
            "model_version": self._model_version,
        }

    def _build_prompt(self, request: Dict[str, Any]) -> str:
        details = json.dumps(request.get("details", {}), ensure_ascii=False)
        return (
            "你是智慧病房云端护理安全研判助手。请对边缘节点上报的事件做二次研判。\n"
            "只能输出 JSON，格式为："
            '{"judgment":"confirm|reject|escalate","confidence":0.0-1.0,"advice":"护理建议"}。\n\n'
            f"事件类型: {request.get('event_type', 'unknown')}\n"
            f"优先级: {request.get('priority', 'P2')}\n"
            f"边缘置信度: {request.get('confidence', 0.0)}\n"
            f"病区: {request.get('ward_id', 'W-01')}\n"
            f"床位: {request.get('bed_id', '')}\n"
            f"详情: {details}\n"
        )

    def _parse_llm_output(self, text: str, request: Dict[str, Any]) -> tuple[str, float, str]:
        """Parse JSON or legacy pipe-delimited LLM output."""

        text = (text or "").strip()
        if text:
            try:
                parsed = json.loads(text)
                judgment = str(parsed.get("judgment", "")).strip().lower()
                confidence = float(parsed.get("confidence", request.get("confidence", 0.5)))
                advice = str(parsed.get("advice", "")).strip()
                if judgment in {"confirm", "reject", "escalate"} and advice:
                    return judgment, max(0.0, min(1.0, confidence)), advice
            except (TypeError, ValueError, json.JSONDecodeError):
                pass

            parts = text.split("|")
            if len(parts) >= 2:
                judgment = parts[0].strip().lower()
                if judgment not in {"confirm", "reject", "escalate"}:
                    judgment = "escalate"
                try:
                    confidence = float(parts[1])
                except ValueError:
                    confidence = float(request.get("confidence", 0.5))
                advice = parts[2].strip() if len(parts) >= 3 and parts[2].strip() else text
                return judgment, max(0.0, min(1.0, confidence)), advice

        fallback = self._mock_infer(request)
        return fallback["judgment"], fallback["confidence"], fallback["advice"]
