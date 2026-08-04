"""UR Fall Detection Dataset 评测脚本。

任务书要求：在 UR Fall Detection Dataset（公开数据集）上跑一遍，交出
初步准确率数字。

数据集结构（标准发布格式）::

    UR Fall Detection Dataset/
    ├── fall/                      跌倒视频
    │   ├── fall-01.avi
    │   ├── fall-01.txt            标签：跌倒事件帧号范围
    │   ├── fall-02.avi
    │   ├── fall-02.txt
    │   └── ...
    └── adl/                       日常生活（非跌倒）
        ├── adl-01.avi
        ├── adl-01.txt
        └── ...

标签文件格式（每行一个事件，帧号）::

    0    50    fall       # 从第 0 帧开始，第 50 帧结束，是 fall 事件
    100  150   fall       # 同一视频可能多次跌倒

用法::

    python edge-agent/scripts/eval_ur_fall.py --dataset "/path/to/UR Fall Detection Dataset/"

输出：准确率、召回率、F1，每个视频的 TP/FP/FN 明细，以及汇总报告。

注意：默认使用 FallDetector 的规则回退（bbox 宽高比），用于出基线准确率。
设置 FALL_MODEL_PATH 环境变量后会加载 ShuffleNetV2+SA 权重做神经判定。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 让 edge-agent/src 可导入
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "edge-agent" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def parse_label_file(label_path: Path) -> List[Tuple[int, int]]:
    """解析标签文件，返回 [(fall_start_frame, fall_end_frame), ...]。

    支持多种常见格式：
    - 每行: start end [type]
    - 每行: frame_number label（CSV）
    未识别时返回空列表（按帧标签无法解析时跳过该视频）。
    """
    events: List[Tuple[int, int]] = []
    if not label_path.exists():
        return events

    with label_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            parts = line.replace(",", " ").split()
            # 格式: start end [type]
            if len(parts) >= 2 and parts[0].lstrip("-").isdigit() and parts[1].lstrip("-").isdigit():
                start = int(parts[0])
                end = int(parts[1])
                if end < start:
                    start, end = end, start
                events.append((start, end))
    return events


def ground_truth_labels(total_frames: int,
                        fall_events: List[Tuple[int, int]]) -> List[int]:
    """生成逐帧 ground truth：1=fall, 0=non-fall。"""
    labels = [0] * total_frames
    for start, end in fall_events:
        for frame_idx in range(start, min(end + 1, total_frames)):
            labels[frame_idx] = 1
    return labels


def evaluate_video(video_path: Path, label_path: Path,
                   fall_detector, conf_threshold: float = 0.6) -> Tuple[List[int], List[int]]:
    """跑一个视频，返回 (ground_truth, predictions) 逐帧标签列表。

    pred=1 表示检测到 fall（fall_score >= conf_threshold）。
    """
    import cv2

    fall_events = parse_label_file(label_path)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  ⚠ 无法打开视频: {video_path.name}")
        return [], []

    ground_truth: List[int] = []
    predictions: List[int] = []
    frame_idx = 0

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            break

        height, width = frame.shape[:2]
        # 用 YOLO 简化：这里只取全图送 FallDetector（无 YOLO 时的人体裁剪）。
        # 完整流程应当先 YOLO 检测 person，这里评测聚焦 FallDetector 准确率。
        try:
            fall_score, action = fall_detector.detect(
                frame, [0, 0, width, height])
        except Exception:
            fall_score, action = 0.0, "non_fall"

        pred = 1 if fall_score >= conf_threshold else 0
        # ground truth：当前帧是否在 fall 事件区间内
        is_fall = any(start <= frame_idx <= end
                      for start, end in fall_events)
        ground_truth.append(1 if is_fall else 0)
        predictions.append(pred)
        frame_idx += 1

    cap.release()
    return ground_truth, predictions


def compute_metrics(ground_truth: List[int], predictions: List[int]) -> Dict:
    """计算准确率/召回率/F1/混淆矩阵。"""
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


def run(dataset_dir: Path, output: Optional[Path] = None,
        conf_threshold: float = 0.6) -> None:
    """跑整个数据集评测。"""
    from fall_detector import FallDetector

    detector = FallDetector()
    print(f"FallDetector 模式: {detector.get_status().get('mode', 'unknown')}")
    print(f"置信阈值: {conf_threshold}")
    print(f"数据集目录: {dataset_dir}")
    print("-" * 60)

    all_gt: List[int] = []
    all_pred: List[int] = []
    per_video: List[Dict] = []

    for subdir in ["fall", "adl"]:
        sub = dataset_dir / subdir
        if not sub.exists():
            print(f"⚠ 跳过不存在的目录: {sub}")
            continue

        videos = sorted(sub.glob("*.avi"))
        # 也支持其他常见视频格式
        for ext in [".mp4", ".mov", ".mkv"]:
            videos.extend(sorted(sub.glob(f"*{ext}")))

        for video_path in videos:
            label_path = video_path.with_suffix(".txt")
            stem = video_path.stem
            t0 = time.time()
            gt, pred = evaluate_video(
                video_path, label_path, detector, conf_threshold)
            elapsed = time.time() - t0
            if not gt:
                continue
            metrics = compute_metrics(gt, pred)
            per_video.append({
                "video": f"{subdir}/{stem}",
                "frames": metrics["total_frames"],
                **metrics,
                "seconds": round(elapsed, 1),
            })
            print(f"  {subdir}/{stem}: frames={metrics['total_frames']} "
                  f"acc={metrics['accuracy']:.2%} "
                  f"TP/FP/TN/FN={metrics['tp']}/{metrics['fp']}/{metrics['tn']}/{metrics['fn']} "
                  f"({elapsed:.1f}s)")
            all_gt.extend(gt)
            all_pred.extend(pred)

    if not all_gt:
        print("\n❌ 没有评测到任何视频，请检查数据集目录结构。")
        return

    overall = compute_metrics(all_gt, all_pred)
    print("\n" + "=" * 60)
    print("汇总指标（UR Fall Detection Dataset）")
    print("=" * 60)
    print(f"总帧数:        {overall['total_frames']}")
    print(f"准确率 Accuracy: {overall['accuracy']:.4f} ({overall['accuracy']:.2%})")
    print(f"精确率 Precision: {overall['precision']:.4f}")
    print(f"召回率 Recall:    {overall['recall']:.4f}")
    print(f"F1 分数:          {overall['f1']:.4f}")
    print(f"混淆矩阵: TP={overall['tp']} FP={overall['fp']} "
          f"TN={overall['tn']} FN={overall['fn']}")
    print(f"模型模式: {detector.get_status().get('mode', 'unknown')}")

    report = {
        "dataset": str(dataset_dir),
        "detector_status": detector.get_status(),
        "confidence_threshold": conf_threshold,
        "overall": overall,
        "per_video": per_video,
    }
    if output:
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\n报告已保存: {output}")
    else:
        default_out = REPO_ROOT / "edge-agent" / "data" / "ur-fall-eval-report.json"
        default_out.parent.mkdir(parents=True, exist_ok=True)
        default_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\n报告已保存: {default_out}")


def main() -> int:
    parser = argparse.ArgumentParser(description="UR Fall Detection Dataset 评测")
    parser.add_argument("--dataset", required=True,
                        help="UR Fall Detection Dataset 根目录（含 fall/ 和 adl/）")
    parser.add_argument("--conf", type=float, default=0.6,
                        help="fall_score 判定为 fall 的阈值（默认 0.6）")
    parser.add_argument("--out", help="报告输出路径（默认 edge-agent/data/）")
    args = parser.parse_args()
    dataset_dir = Path(args.dataset)
    if not dataset_dir.exists():
        print(f"数据集目录不存在: {dataset_dir}")
        return 2
    run(dataset_dir, Path(args.out) if args.out else None, args.conf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
