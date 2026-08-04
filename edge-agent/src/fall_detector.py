"""ShuffleNetV2 + Self-Attention 跌倒二分类器。

任务书指定方案：YOLOv8 检测 person 后截取人体区域，送 ShuffleNetV2+SA
做 fall/non-fall 二分类（论文在 UR Fall Detection Dataset 上 95.85%）。

模型未训练时回退到规则判定（保持系统可用），训练后加载权重即可切换到
神经网络判定，不影响 activity_tracker / behavior 的其他维度。
"""

from __future__ import annotations

import os
import math
from typing import Optional, Tuple

import numpy as np


class SAChannelAttention:
    """Self-Attention 通道注意力（论文 SA 模块）。

    对 ShuffleNetV2 输出特征图做通道级 self-attention 加权，提升跌倒判别特征。
    """

    def __init__(self, channels: int, reduction: int = 8) -> None:
        self.channels = channels
        import torch.nn as nn
        self.fc1 = nn.Conv2d(channels, max(channels // reduction, 1), 1)
        self.fc2 = nn.Conv2d(max(channels // reduction, 1), channels, 1)

    def __call__(self, x):
        import torch
        b, c, _, _ = x.shape
        q = x.mean(dim=(2, 3), keepdim=True)
        k = x
        v = x
        attn = torch.softmax(
            (q * k).mean(dim=1, keepdim=True) / math.sqrt(c), dim=1)
        out = v * attn
        out = self.fc2(torch.relu(self.fc1(out)))
        return x + out


class ShuffleNetV2SA:
    """ShuffleNetV2 + SA 二分类网络（fall / non-fall）。

    在默认未加载权重时进入 fallback 模式，用规则判定（朝向变化+下落速度），
    保证系统在模型权重缺失时仍可用。
    """

    INPUT_SIZE = (224, 224)
    MODEL_NAME = "shufflenetv2-sa-fall"
    MODEL_VERSION = "0.1.0-mock"

    def __init__(self, device: Optional[str] = None) -> None:
        import torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._torch = torch
        self._model = None
        self._weights_loaded = False
        self._transform = None
        weights = os.getenv("FALL_MODEL_PATH", "")
        if weights:
            self._load_weights(weights)

    def _load_weights(self, path: str) -> None:
        """加载训练好的 ShuffleNetV2+SA 权重（.pt/.pth）。

        架构与 train_fall_detector.py 完全一致（命名子模块保证 state_dict key 匹配）：
          backbone（ShuffleNetV2 去 fc）→ SA → GAP → Dropout → Linear(2)
        """
        try:
            import torch
            import torchvision.models as tv_models
            import torch.nn as nn

            # 与训练脚本完全一致的 SA 模块
            class SAChannelAttention(nn.Module):
                def __init__(self, channels, reduction=8):
                    super().__init__()
                    self.fc1 = nn.Conv2d(channels, max(channels // reduction, 1), 1)
                    self.fc2 = nn.Conv2d(max(channels // reduction, 1), channels, 1)
                def forward(self, x):
                    b, c, _, _ = x.shape
                    q = x.mean(dim=(2, 3), keepdim=True)
                    k = x
                    v = x
                    attn = torch.softmax(
                        (q * k).mean(dim=1, keepdim=True) / max(c**0.5, 1), dim=1)
                    out = v * attn
                    out = self.fc2(torch.relu(self.fc1(out)))
                    return x + out

            # 与训练脚本完全一致的模型类（命名子模块，state_dict key 匹配）
            class Model(nn.Module):
                def __init__(self, num_classes=2):
                    super().__init__()
                    base = tv_models.shufflenet_v2_x1_0(weights=None)
                    self.backbone = nn.Sequential(
                        *list(base.children())[:-1])
                    self.sa = SAChannelAttention(1024)
                    self.gap = nn.AdaptiveAvgPool2d(1)
                    self.dropout = nn.Dropout(0.3)
                    self.fc = nn.Linear(1024, num_classes)
                def forward(self, x):
                    x = self.backbone(x)
                    x = self.sa(x)
                    x = self.gap(x).flatten(1)
                    x = self.dropout(x)
                    return self.fc(x)

            model = Model(num_classes=2)
            state = self._torch.load(path, map_location=self.device)
            model.load_state_dict(state)
            model = model.to(self.device).eval()
            self._model = model
            self._weights_loaded = True
            from torchvision import transforms
            self._transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize(self.INPUT_SIZE),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ])
            print(f"[FallDetector] 模型加载成功: {path}")
        except Exception as exc:
            print(f"[FallDetector] 模型加载失败，回退规则判定: {exc}")
            self._model = None
            self._weights_loaded = False

    @property
    def is_real_mode(self) -> bool:
        return self._weights_loaded

    def classify(self, crop_bgr) -> Tuple[str, float]:
        """对裁剪的人体区域 BGR 帧做跌倒二分类。

        Args:
            crop_bgr: numpy 数组 (H,W,3) BGR uint8，来自摄像头帧的 bbox 区域

        Returns:
            (label, confidence): label="fall" | "non_fall",
            confidence=0.0~1.0
        """
        if self._model is None:
            return self._rule_fallback(crop_bgr)

        try:
            import cv2
            rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
            tensor = self._transform(rgb).unsqueeze(0).to(self.device)
            with self._torch.no_grad():
                logits = self._model(tensor)
                probs = self._torch.softmax(logits, dim=1)[0]
                fall_idx = 1  # 约定：index 1 = fall
                nonfall_idx = 0
                if probs[fall_idx] >= probs[nonfall_idx]:
                    return "fall", float(probs[fall_idx])
                return "non_fall", float(probs[nonfall_idx])
        except Exception as exc:
            print(f"[FallDetector] 推理异常，回退规则: {exc}")
            return self._rule_fallback(crop_bgr)

    @staticmethod
    def _rule_fallback(crop_bgr) -> Tuple[str, float]:
        """无权重时用 bbox 宽高比粗判（向后兼容）。

        跌倒时人体 bbox 横向展宽（宽 > 高），正常站立时纵向拉长（高 > 宽）。
        """
        h, w = crop_bgr.shape[:2]
        if w <= 0 or h <= 0:
            return "non_fall", 0.5
        aspect = w / h
        if aspect >= 1.3:
            return "fall", min(0.95, 0.6 + (aspect - 1.3) * 0.5)
        return "non_fall", min(0.95, 0.7 + (1.3 - aspect) * 0.3)

    def get_status(self) -> dict:
        return {
            "model_name": self.MODEL_NAME,
            "model_version": self.MODEL_VERSION,
            "weights_loaded": self._weights_loaded,
            "device": self.device,
            "mode": "neural" if self._weights_loaded else "rule_fallback",
        }


class FallDetector:
    """跌倒检测器：从 YOLO 检测帧 + bbox 出发，调用 ShuffleNetV2+SA 分类。

    封装为统一接口：输入原始帧 + 检测框，输出 fall_score（0.0~1.0）
    与 action（"falling" / "suspected_fall" / 其他），可直接并入
    BehaviorAnalyzer 的 _summarize_track 输出。
    """

    def __init__(self, device: Optional[str] = None) -> None:
        self.classifier = ShuffleNetV2SA(device=device)
        self._frame_cache = {}  # track_id -> 上一帧 fall 状态，用于 suspected_fall 检测

    def detect(self, frame_bgr, bbox_xyxy) -> Tuple[float, str]:
        """对单个检测框做跌倒分类。

        Args:
            frame_bgr: 原始摄像头帧 (H,W,3) BGR
            bbox_xyxy: [x1, y1, x2, y2] 像素坐标

        Returns:
            (fall_score, action): fall_score 0~1，action 标签
        """
        x1, y1, x2, y2 = [int(v) for v in bbox_xyxy]
        h, w = frame_bgr.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            return 0.0, "non_fall"
        crop = frame_bgr[y1:y2, x1:x2]
        label, conf = self.classifier.classify(crop)

        if label == "fall":
            fall_score = conf
            action = "falling"
        else:
            fall_score = 1.0 - conf  # non_fall 置信越高，fall_score 越低
            action = "non_fall"
        return fall_score, action

    def detect_track(self, track_id: int, frame_bgr,
                     bbox_xyxy) -> Tuple[float, str]:
        """带 track_id 的检测：用前后帧状态判断 suspected_fall（站->倒）。

        当上一帧 non_fall 且当前帧 fall 时，标记 suspected_fall，
        对应 BehaviorAnalyzer 原 transition 语义。
        """
        score, action = self.detect(frame_bgr, bbox_xyxy)
        prev = self._frame_cache.get(track_id)
        if action == "falling" and prev and prev[1] != "falling":
            action = "suspected_fall"
        self._frame_cache[track_id] = (score, action)
        return score, action

    def get_status(self) -> dict:
        return self.classifier.get_status()
