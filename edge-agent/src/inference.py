"""模型推理引擎

为边缘端识别模型预留统一接口。接入真实 ONNX/OpenVINO/TensorRT 模型时，
只需替换 InferenceEngine.run() 内部实现，不改动 fusion/mqtt_client/main。

输出强制包含方案书 §3.3 验收要求的字段：
    model_name / model_version / confidence / inference_ms / evidence_refs

注意 evidence_refs（复数）对齐 contracts/safety_event.json 契约字段，
云端 database.py / mqtt_handler.py 与 fusion.py 均使用复数，此处保持一致。

模型版本管理：
    - load_model() 接收云端下发的新版本（model/deploy）
    - rollback() 回退到上一稳定版本（model/rollback）
    - 加载失败自动回退并标记，health 心跳上报当前 model_version
"""

import os
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from adapters.base import Observation


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class InferenceResult:
    """模型推理结果

    predictions 字段对齐 CameraAdapter 输出，包含 fusion 所有规则用到的字段：
        presence / person_count / posture / fall_score / tremor_score /
        position_duration / pose_keypoints / bbox

    真实模型接入时，predictions 由前向推理填充；当前模拟版透传适配器数据。
    """

    def __init__(
        self,
        model_name: str,
        model_version: str,
        confidence: float,
        inference_ms: int,
        evidence_refs: List[Dict[str, Any]] = None,
        predictions: Dict[str, Any] = None,
    ):
        self.model_name = model_name
        self.model_version = model_version
        self.confidence = confidence
        self.inference_ms = inference_ms
        self.evidence_refs = evidence_refs or []
        self.predictions = predictions or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "confidence": round(self.confidence, 3),
            "inference_ms": self.inference_ms,
            "evidence_refs": self.evidence_refs,
            "predictions": self.predictions,
        }


class InferenceEngine:
    """模型推理引擎

    当前版本：透传适配器数据，不做真实推理。
    后续接入真实模型时：
        1. 在 load_model() 中加载 ONNX/OpenVINO/TensorRT/RKNN 模型
        2. 在 run() 中对 camera_obs.data 做前向推理
        3. 返回检测结果 + 姿态关键点 + 跌倒置信度 + 抽搐分

    模型版本管理（支撑云端 model/deploy 灰度下发）：
        - load_model(name, version)：切换到新版本，保留上一版本以便回退
        - rollback()：回退到上一稳定版本
        - 加载异常时自动回退，degraded=True，confidence 降低
    """

    def __init__(self):
        self.model_name = os.getenv("MODEL_NAME", "rule-fusion-v1")
        self.model_version = os.getenv("MODEL_VERSION", "0.1.0-mock")
        # 上一稳定版本（用于 rollback），初始与当前相同
        self._prev_model_name = self.model_name
        self._prev_model_version = self.model_version
        # 模型加载状态：ok / degraded / loading
        self.model_status = "ok"

    # ─── 模型版本管理（供 main.handle_model_deploy 调用）───

    def load_model(self, model_name: str, model_version: str) -> bool:
        """加载新模型版本（云端 model/deploy 下发）

        Args:
            model_name: 模型名，如 yolo-nano-pose
            model_version: 语义化版本，如 1.0.0-int8

        Returns:
            bool: 加载是否成功。失败时自动回退到上一版本并标记 degraded。

        真实模型接入时此处应：
            1. 下载 artifact_url 指向的模型制品
            2. 校验 checksum（SHA256）
            3. 加载到对应 runtime（ONNX/OpenVINO/RKNN）
            4. 验证推理可用后切换；任一步失败则回退
        """
        try:
            # 记录上一版本以便回退
            self._prev_model_name = self.model_name
            self._prev_model_version = self.model_version
            self.model_name = model_name
            self.model_version = model_version
            self.model_status = "ok"
            return True
        except Exception as e:
            # 加载失败：回退到上一版本
            print(f"[inference] 模型加载失败，回退到 {self._prev_model_version}: {e}")
            self.model_name = self._prev_model_name
            self.model_version = self._prev_model_version
            self.model_status = "degraded"
            return False

    def rollback(self) -> bool:
        """回滚到上一稳定模型版本（云端 model/rollback 下发）

        Returns:
            bool: 回滚是否成功。无上一版本记录时返回 False。
        """
        if self.model_version == self._prev_model_version:
            return False
        current = self.model_version
        self.model_name = self._prev_model_name
        self.model_version = self._prev_model_version
        self.model_status = "ok"
        print(f"[inference] 模型回滚: {current} -> {self.model_version}")
        return True

    # ─── 推理主流程 ───

    def run(self, camera_obs: Observation = None) -> InferenceResult:
        """对摄像头观测做推理

        Args:
            camera_obs: CameraAdapter 输出的观测数据

        Returns:
            InferenceResult: 含模型信息与推理结果，predictions 覆盖 fusion
            所有规则用到的字段（posture/fall_score/tremor_score/position_duration 等）

        真实模型接入时替换内部实现为前向推理，输出结构保持一致。
        """
        t0 = time.time()
        # 模拟推理耗时
        time.sleep(0.005)
        inference_ms = int((time.time() - t0) * 1000)

        # 模型降级时置信度降低（传感器故障/模型加载失败的兜底）
        base_confidence = 0.6 if self.model_status == "degraded" else 1.0

        if camera_obs is None:
            return InferenceResult(
                model_name=self.model_name,
                model_version=self.model_version,
                confidence=0.0,
                inference_ms=inference_ms,
            )

        data = camera_obs.data
        # 透传适配器已计算的字段（模拟版不做真实推理）
        # 覆盖 fusion 所有规则用到的字段，真实模型接入时由前向推理填充
        predictions = {
            "presence": data.get("presence", False),
            "person_count": data.get("person_count", 0),
            "posture": data.get("posture", "unknown"),
            "fall_score": data.get("fall_score", 0.0),
            "tremor_score": data.get("tremor_score", 0.0),
            "position_duration": data.get("position_duration", 0),
            "pose_keypoints": data.get("pose_keypoints", []),
            "bbox": data.get("bbox"),
        }

        confidence = camera_obs.quality.confidence * base_confidence

        # 构造证据引用（脱敏，原始数据留边缘端）
        evidence_refs = self._build_evidence_refs(camera_obs, predictions)

        return InferenceResult(
            model_name=self.model_name,
            model_version=self.model_version,
            confidence=confidence,
            inference_ms=inference_ms,
            evidence_refs=evidence_refs,
            predictions=predictions,
        )

    def _build_evidence_refs(
        self, camera_obs: Observation, predictions: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """构造脱敏证据引用列表

        对齐 contracts/safety_event.json 的 evidence_refs 结构：
            kind: image / clip / sensor_dump / pose_keypoints
            ref: 边缘端本地路径或对象存储 key
            taken_at: 拍摄时间 ISO 8601

        演示阶段仅生成指针引用，不真实存储截图/片段。
        真实模型接入时此处应：
            1. 截取脱敏画面（遮蔽面部）保存到本地 /app/evidence/
            2. 保存 pose_keypoints 的 sensor_dump
            3. 返回本地路径作为 ref，云端按需拉取
        """
        refs: List[Dict[str, Any]] = []
        ts = camera_obs.timestamp or _utc_now_iso()
        node_id = getattr(camera_obs, "node_id", "unknown")
        bed_id = getattr(camera_obs, "bed_id", "unknown")

        # 姿态关键点 dump（脱敏，仅关键点坐标不含图像）
        if predictions.get("pose_keypoints"):
            refs.append({
                "kind": "pose_keypoints",
                "ref": f"/app/evidence/{node_id}/{ts}/keypoints.json",
                "taken_at": ts,
            })

        # 高风险事件附加脱敏截图指针（跌倒/坠床/抽搐）
        posture = predictions.get("posture", "unknown")
        fall_score = predictions.get("fall_score", 0.0)
        tremor_score = predictions.get("tremor_score", 0.0)
        if posture in ("falling", "lying_edge", "seizing") or fall_score > 0.5 or tremor_score > 0.6:
            refs.append({
                "kind": "image",
                "ref": f"/app/evidence/{node_id}/{ts}/frame_desensitized.jpg",
                "taken_at": ts,
            })

        return refs
