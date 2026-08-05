"""UR Fall Detection Dataset 评测脚本（适配 cam0 RGB 帧序列）。

任务书要求：在 UR Fall Detection Dataset 上跑一遍，交出初步准确率数字。

数据集结构（实际下载的格式）::

    UR_fall_detection_dataset_cam0_rgb/
    ├── labels.txt              标签文件（片段名 跌倒起始帧 跌倒结束帧）
    ├── fall-01-cam0-rgb/
    │   ├── fall-01-cam0-rgb-001.png
    │   ├── fall-01-cam0-rgb-002.png
    │   └── ...
    ├── fall-02-cam0-rgb/
    ├── adl-01-cam0-rgb/
    │   ├── adl-01-cam0-rgb-001.png
    │   └── ...
    └── ...

用法::

    python edge-agent/scripts/eval_ur_fall.py --dataset "UR_fall_detection_dataset_cam0_rgb"

输出：准确率、精确率、召回率、F1，每个片段的 TP/FP/FN 明细，JSON 报告。
默认使用 FallDetector 规则回退（bbox 宽高比）出基线；设 FALL_MODEL_PATH
后用 ShuffleNetV2+SA 神经判定。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "edge-agent" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def parse_labels(label_path: Path) -> Dict[str, List[Tuple[int, int]]]:
    """解析 labels.txt，返回 {片段名: [(fall_start, fall_end), ...]}。

    帧号 1-indexed（与 PNG 文件名编号一致）。
    """
    labels: Dict[str, List[Tuple[int, int]]] = {}
    if not label_path.exists():
        return labels
    with label_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.replace(",", " ").split()
            if len(parts) >= 3 and parts[1].isdigit() and parts[2].isdigit():
                name = parts[0]
                start, end = int(parts[1]), int(parts[2])
                if end < start:
                    start, end = end, start
                labels.setdefault(name, []).append((start, end))
    return labels


def ground_truth_for_clip(clip_name: str, total_frames: int,
                          fall_events: List[Tuple[int, int]]) -> List[int]:
    """生成逐帧 ground truth：1=fall, 0=non-fall（1-indexed 帧号）。"""
    labels = [0] * total_frames
    for start, end in fall_events:
        for frame_idx in range(start - 1, min(end, total_frames)):
            labels[frame_idx] = 1
    return labels


def compute_metrics(ground_truth: List[int], predictions: List[int]) -> Dict:
    tp = sum(1 for g, p in zip(ground_truth, predictions) if g == 1 and p == 1)
    fp = sum(1 for g, p in zip(ground_truth, predictions) if g == 0 and p == 1)
    tn = sum(1 for g, p in zip(ground_truth, predictions) if g == 0 and p == 0)
    fn = sum(1 for g, p in zip(ground_truth, predictions) if g == 1 and p == 0)
    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "total_frames": total,
    }


def evaluate_clip(clip_dir: Path, fall_events: List[Tuple[int, int]],
                  fall_detector, conf_threshold: float,
                  sample_stride: int = 1) -> Tuple[List[int], List[int]]:
    """跑一个片段的 PNG 帧序列，返回 (ground_truth, predictions)。

    采样步长 stride>1 时，只对采样帧计算帧级指标（跳过的帧不参与），
    避免把未推理的 fall 帧强行记为 non-fall、误计入 FN 导致召回率被腰斩。
    """
    import cv2

    frames = sorted(clip_dir.glob("*.png"))
    total = len(frames)
    ground_truth_all = ground_truth_for_clip(clip_dir.name, total, fall_events)
    sample_indices = [i for i in range(total) if i % sample_stride == 0]
    ground_truth = [ground_truth_all[i] for i in sample_indices]
    predictions: List[int] = []

    for idx in sample_indices:
        frame = cv2.imread(str(frames[idx]))
        if frame is None:
            predictions.append(0)
            continue
        height, width = frame.shape[:2]
        try:
            fall_score, _ = fall_detector.detect(frame, [0, 0, width, height])
        except Exception:
            fall_score = 0.0
        predictions.append(1 if fall_score >= conf_threshold else 0)

    return ground_truth, predictions


def run(dataset_dir: Path, output: Optional[Path] = None,
        conf_threshold: float = 0.6, sample_stride: int = 1) -> None:
    from fall_detector import FallDetector

    detector = FallDetector()
    print(f"FallDetector 模式: {detector.get_status().get('mode', 'unknown')}")
    print(f"置信阈值: {conf_threshold}  采样步长: {sample_stride}")
    print(f"数据集: {dataset_dir}")
    print("-" * 70)

    labels = parse_labels(dataset_dir / "labels.txt")
    clip_dirs = sorted([d for d in dataset_dir.iterdir()
                        if d.is_dir() and d.name.endswith("-cam0-rgb")])

    all_gt: List[int] = []
    all_pred: List[int] = []
    per_clip: List[Dict] = []

    for clip_dir in clip_dirs:
        fall_events = labels.get(clip_dir.name, [])
        t0 = time.time()
        gt, pred = evaluate_clip(
            clip_dir, fall_events, detector, conf_threshold, sample_stride)
        elapsed = time.time() - t0
        if not gt:
            continue
        metrics = compute_metrics(gt, pred)
        per_clip.append({
            "clip": clip_dir.name,
            "frames": metrics["total_frames"],
            "is_fall_clip": bool(fall_events),
            **metrics,
            "seconds": round(elapsed, 1),
        })
        tag = "fall" if fall_events else "adl "
        print(f"  [{tag}] {clip_dir.name}: frames={metrics['total_frames']:>4} "
              f"acc={metrics['accuracy']:.2%} "
              f"TP/FP/TN/FN={metrics['tp']}/{metrics['fp']}/{metrics['tn']}/{metrics['fn']} "
              f"({elapsed:.1f}s)")
        all_gt.extend(gt)
        all_pred.extend(pred)

    if not all_gt:
        print("\n没有评测到任何片段，请检查数据集目录。")
        return

    overall = compute_metrics(all_gt, all_pred)
    print("\n" + "=" * 70)
    print("UR Fall Detection Dataset 汇总指标")
    print("=" * 70)
    print(f"片段数:          {len(per_clip)}")
    print(f"总帧数:          {overall['total_frames']}")
    print(f"准确率 Accuracy: {overall['accuracy']:.4f} ({overall['accuracy']:.2%})")
    print(f"精确率 Precision: {overall['precision']:.4f}")
    print(f"召回率 Recall:    {overall['recall']:.4f}")
    print(f"F1 分数:          {overall['f1']:.4f}")
    print(f"混淆矩阵: TP={overall['tp']} FP={overall['fp']} "
          f"TN={overall['tn']} FN={overall['fn']}")
    print(f"模型模式: {detector.get_status().get('mode', 'unknown')}")

    # fall / adl 分别统计
    fall_clips = [c for c in per_clip if c["is_fall_clip"]]
    adl_clips = [c for c in per_clip if not c["is_fall_clip"]]
    if fall_clips:
        fall_tp = sum(c["tp"] for c in fall_clips)
        fall_fn = sum(c["fn"] for c in fall_clips)
        fall_fp = sum(c["fp"] for c in fall_clips)
        fall_recall = fall_tp / (fall_tp + fall_fn) if (fall_tp + fall_fn) > 0 else 0
        print(f"\nfall 片段（{len(fall_clips)} 个）: 召回率={fall_recall:.2%} "
              f"(TP={fall_tp} FN={fall_fn})")
    if adl_clips:
        adl_fp = sum(c["fp"] for c in adl_clips)
        adl_tn = sum(c["tn"] for c in adl_clips)
        adl_spec = adl_tn / (adl_tn + adl_fp) if (adl_tn + adl_fp) > 0 else 0
        print(f"adl 片段（{len(adl_clips)} 个）: 特异度={adl_spec:.2%} "
              f"(FP={adl_fp} TN={adl_tn})")

    report = {
        "dataset": str(dataset_dir),
        "detector_status": detector.get_status(),
        "confidence_threshold": conf_threshold,
        "sample_stride": sample_stride,
        "overall": overall,
        "per_clip": per_clip,
    }
    out_path = output or (REPO_ROOT / "edge-agent" / "data" / "ur-fall-eval-report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n报告已保存: {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="UR Fall Detection Dataset 评测")
    parser.add_argument("--dataset", required=True,
                        help="数据集根目录（含 fall-*/adl-*-cam0-rgb 子目录）")
    parser.add_argument("--conf", type=float, default=0.6,
                        help="fall_score 判定为 fall 的阈值（默认 0.6）")
    parser.add_argument("--stride", type=int, default=1,
                        help="采样步长（默认 1=每帧；3=每 3 帧取 1，加速 3 倍）")
    parser.add_argument("--out", help="报告输出路径")
    args = parser.parse_args()
    dataset_dir = Path(args.dataset)
    if not dataset_dir.exists():
        print(f"数据集目录不存在: {dataset_dir}")
        return 2
    run(dataset_dir, Path(args.out) if args.out else None,
        args.conf, args.stride)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
