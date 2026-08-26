"""视觉语义验证器

用视觉语言模型（默认 MiniCPM-V，OpenAI 兼容 API）对扩散生成的样本做
语义级筛选：像素级 QualityCurator 判断"清晰不清晰"，本模块判断
"内容是否真的像目标事件场景"。

配置：
    VISION_ENDPOINT  视觉模型 API 地址（如 http://127.0.0.1:1234/v1），为空则禁用
    VISION_MODEL     模型名（默认 minicpm-v-4.6）
    VISION_TIMEOUT   单张验证超时秒（默认 60）
"""

import base64
import json
import os
import urllib.request

from .logger import get_logger

logger = get_logger(__name__)

# 各事件类型的场景判定标准（中文，喂给视觉模型）
EVENT_SCENE_DESC = {
    "fall_suspected": "患者摔倒在地上，或正在从床上坠落",
    "seizure": "患者在抽搐、痉挛发作（肢体不自然扭动）",
    "abnormal_posture": "患者蜷缩、前倾、抓胸等异常体态",
    "fall_prediction": "患者坐在床边沿，身体前倾有坠落风险",
    "bed_leave": "床铺上没有人",
    "night_wandering": "夜间患者离开床位走动",
    "long_still": "患者长时间保持同一姿势静止不动",
    "bedsore_risk": "患者卧床长时间不动",
    "nurse_call": "患者按呼叫器求助",
    "infusion_anomaly": "输液瓶/输液管状态异常",
    "door_departure": "患者从门区域离开",
    "environment_anomaly": "病房环境异常（温湿度/灯光等）",
    "device_fault": "医疗设备异常",
}


class VisionValidator:
    """视觉语义验证器（OpenAI 兼容接口）"""

    def __init__(self, endpoint: str = None, model: str = None):
        self.endpoint = (endpoint or os.getenv("VISION_ENDPOINT", "")).rstrip("/")
        self.model = model or os.getenv("VISION_MODEL", "minicpm-v-4.6")
        self.timeout = int(os.getenv("VISION_TIMEOUT", "60"))
        self.enabled = bool(self.endpoint)

    def validate(self, image, event_type: str) -> dict:
        """验证单张图像是否语义符合目标事件

        Args:
            image: PIL Image
            event_type: 事件类型（fall_suspected 等）

        Returns:
            {"passed": bool, "reason": str, "error": str|None}
        """
        if not self.enabled:
            return {"passed": True, "reason": "vision disabled", "error": None}

        scene = EVENT_SCENE_DESC.get(event_type)
        if not scene:
            return {"passed": True, "reason": f"no scene desc for {event_type}", "error": None}

        try:
            import io
            buf = io.BytesIO()
            image.convert("RGB").save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode()

            prompt = (
                f"这是一张智慧病房监控画面。请判断画面内容是否符合以下场景："
                f"「{scene}」。只回答两个部分：第一行：符合/不符合/不确定；"
                f"第二行：一句话理由。"
            )
            payload = {
                "model": self.model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }],
                "max_tokens": 200,
            }
            req = urllib.request.Request(
                f"{self.endpoint}/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            resp = json.loads(urllib.request.urlopen(req, timeout=self.timeout).read())
            msg = resp["choices"][0]["message"]
            # MiniCPM-V 4.6 有思维链：content 为空时用 reasoning_content 兜底
            content = (msg.get("content") or "").strip()
            if not content:
                content = (msg.get("reasoning_content") or "").strip()

            passed = content.startswith("符合") or "符合" in content.split("\n")[0]
            return {"passed": passed, "reason": content[:100], "error": None}
        except Exception as e:
            logger.warning(f"视觉验证失败（放行）: {e}")
            return {"passed": True, "reason": f"vision error: {e}", "error": str(e)}

    def filter_semantic(self, results: list, event_type: str) -> tuple[list, dict]:
        """对通过像素筛选的结果做语义过滤

        Args:
            results: curator 通过的结果列表（含 image 键）
            event_type: 事件类型

        Returns:
            (passed, report)
        """
        if not self.enabled or not results:
            return results, {"passed": len(results), "rejected": 0, "reasons": []}

        passed = []
        rejected = []
        for i, r in enumerate(results):
            v = self.validate(r["image"], event_type)
            if v["passed"]:
                passed.append(r)
            else:
                rejected.append({"index": i, "reason": v["reason"]})
                logger.info(f"语义筛选剔除样本 #{i}: {v['reason']}")

        report = {
            "passed": len(passed),
            "rejected": len(rejected),
            "reasons": rejected,
        }
        logger.info(
            f"Vision semantic filter: {report['passed']}/{len(results)} passed "
            f"({report['passed'] / max(len(results), 1):.1%})"
        )
        return passed, report
