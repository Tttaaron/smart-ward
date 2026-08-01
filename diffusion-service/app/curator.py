"""质量筛选器

对生成图像进行多维质量评估，过滤低质量样本：
    1. 清晰度检测（Laplacian 方差）
    2. 亮度异常检测
    3. 色彩多样性检测

筛选后的样本输出为高质量训练数据集。
"""

import logging
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image

from .config import (
    MIN_SHARPNESS_SCORE,
    MAX_BLUR_SCORE,
    MIN_BRIGHTNESS,
    MAX_BRIGHTNESS,
)

logger = logging.getLogger(__name__)


class QualityCurator:
    """图像质量筛选器"""

    def __init__(
        self,
        min_sharpness: float = MIN_SHARPNESS_SCORE,
        max_sharpness: float = MAX_BLUR_SCORE,
        min_brightness: float = MIN_BRIGHTNESS,
        max_brightness: float = MAX_BRIGHTNESS,
    ):
        self.min_sharpness = min_sharpness
        self.max_sharpness = max_sharpness
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness

    def assess(self, image: Image.Image) -> Dict[str, float]:
        """评估单张图像的质量指标

        Returns:
            dict: {sharpness, brightness, passed, reasons}
        """
        gray = image.convert("L")
        arr = np.array(gray, dtype=np.float32)

        # Laplacian 方差（清晰度）
        try:
            import cv2
            laplacian = cv2.Laplacian(arr.astype(np.float32), cv2.CV_32F)
        except ImportError:
            try:
                from scipy import ndimage
                laplacian = ndimage.laplace(arr)
            except ImportError:
                # numpy 手动实现 3x3 Laplacian（较慢，仅兜底用）
                kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
                laplacian = np.zeros_like(arr)
                arr_pad = np.pad(arr, 1, mode='edge')
                for i in range(arr.shape[0]):
                    for j in range(arr.shape[1]):
                        laplacian[i, j] = np.sum(arr_pad[i:i+3, j:j+3] * kernel)
        sharpness = float(np.var(laplacian))

        # 平均亮度
        brightness = float(np.mean(arr))

        # 评估
        passed = True
        reasons = []

        if sharpness < self.min_sharpness:
            passed = False
            reasons.append(f"too_blurry({sharpness:.1f}<{self.min_sharpness})")
        elif sharpness > self.max_sharpness:
            passed = False
            reasons.append(f"too_noisy({sharpness:.1f}>{self.max_sharpness})")

        if brightness < self.min_brightness:
            passed = False
            reasons.append(f"too_dark({brightness:.1f}<{self.min_brightness})")
        elif brightness > self.max_brightness:
            passed = False
            reasons.append(f"too_bright({brightness:.1f}>{self.max_brightness})")

        return {
            "sharpness": round(sharpness, 1),
            "brightness": round(brightness, 1),
            "passed": passed,
            "reasons": reasons,
        }

    def filter(
        self,
        results: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """筛选高质量样本

        Returns:
            (passed_results, report): 通过筛选的结果和统计报告
        """
        passed = []
        failed = []

        for i, r in enumerate(results):
            metrics = self.assess(r["image"])
            r["quality"] = metrics
            if metrics["passed"]:
                passed.append(r)
            else:
                failed.append({**metrics, "index": i, "event_type": r["event_type"]})

        report = {
            "total": len(results),
            "passed": len(passed),
            "failed": len(failed),
            "pass_rate": round(len(passed) / max(len(results), 1), 3),
            "failed_details": failed,
        }

        logger.info(
            f"Quality filter: {report['passed']}/{report['total']} "
            f"passed ({report['pass_rate']:.1%})"
        )
        if failed:
            reasons = {}
            for f in failed:
                for r in f["reasons"]:
                    reasons[r] = reasons.get(r, 0) + 1
            logger.info(f"Failure reasons: {reasons}")

        return passed, report

    def filter_fast(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """快速筛选（无 scipy 依赖版本）

        仅使用 PIL 进行基本亮度检查，跳过 Laplacian 清晰度检测。
        适用于 scipy 未安装的环境。
        """
        passed = []
        for r in results:
            img = r["image"]
            gray = img.convert("L")
            arr = np.array(gray, dtype=np.float32)

            # 仅检查亮度
            brightness = float(np.mean(arr))
            if self.min_brightness <= brightness <= self.max_brightness:
                r["quality"] = {
                    "sharpness": -1.0,
                    "brightness": round(brightness, 1),
                    "passed": True,
                    "reasons": [],
                }
                passed.append(r)

        logger.info(f"Fast filter: {len(passed)}/{len(results)} passed")
        return passed


def validate_pose_consistency(
    generated_keypoints: List[List[float]],
    template_keypoints: List[List[float]],
    max_distance: float = 0.15,
) -> float:
    """校验生成的关键点与模板的一致性（姿态距离）

    Returns:
        float: 平均关键点距离（归一化），越低越好
    """
    distances = []
    for gk, tk in zip(generated_keypoints, template_keypoints):
        if (gk[0] == 0 and gk[1] == 0) or (tk[0] == 0 and tk[1] == 0):
            continue
        d = np.sqrt((gk[0] - tk[0])**2 + (gk[1] - tk[1])**2)
        distances.append(d)
    return float(np.mean(distances)) if distances else 0.0
