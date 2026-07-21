"""模型推理空壳

为边缘端识别模型预留统一接口。亚伦后续接入真实 ONNX/OpenVINO/TensorRT 模型时，
只需替换 InferenceEngine.run() 内部实现，不改动 fusion/mqtt_client/main。

输出强制包含方案书 §3.3 验收要求的字段：
    model_name / model_version / confidence / inference_ms / evidence_ref
"""

import os
import time
from typing import Any, Dict, List

from adapters.base import Observation
from adapters.camera import CameraAdapter


class InferenceResult:
    """模型推理结果"""

    def __init__(
        self,
        model_name: str,
        model_version: str,
        confidence: float,
        inference_ms: int,
        evidence_ref: List[Dict[str, Any]] = None,
        predictions: Dict[str, Any] = None,
    ):
        self.model_name = model_name
        self.model_version = model_version
        self.confidence = confidence
        self.inference_ms = inference_ms
        self.evidence_ref = evidence_ref or []
        self.predictions = predictions or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "confidence": round(self.confidence, 3),
            "inference_ms": self.inference_ms,
            "evidence_ref": self.evidence_ref,
            "predictions": self.predictions,
        }


class InferenceEngine:
    """模型推理引擎（空壳）

    当前版本：透传适配器数据，不做真实推理。
    后续接入真实模型时：
        1. 加载 ONNX/OpenVINO/TensorRT 模型
        2. 在 run() 中对 camera_obs.data 做前向推理
        3. 返回检测结果 + 姿态关键点 + 跌倒置信度
    """

    def __init__(self):
        self.model_name = os.getenv("MODEL_NAME", "rule-fusion-v1")
        self.model_version = os.getenv("MODEL_VERSION", "0.1.0-mock")

    def run(self, camera_obs: Observation = None) -> InferenceResult:
        """对摄像头观测做推理

        Args:
            camera_obs: CameraAdapter 输出的观测数据

        Returns:
            InferenceResult: 含模型信息与推理结果
        """
        t0 = time.time()
        # 模拟推理耗时
        time.sleep(0.005)
        inference_ms = int((time.time() - t0) * 1000)

        if camera_obs is None:
            return InferenceResult(
                model_name=self.model_name,
                model_version=self.model_version,
                confidence=0.0,
                inference_ms=inference_ms,
            )

        data = camera_obs.data
        # 透传适配器已计算的字段（模拟版不做真实推理）
        predictions = {
            "presence": data.get("presence", False),
            "person_count": data.get("person_count", 0),
            "posture": data.get("posture", "unknown"),
            "fall_score": data.get("fall_score", 0.0),
        }

        confidence = camera_obs.quality.confidence

        return InferenceResult(
            model_name=self.model_name,
            model_version=self.model_version,
            confidence=confidence,
            inference_ms=inference_ms,
            evidence_ref=[],  # 真实模型在此填充脱敏截图/片段引用
            predictions=predictions,
        )
