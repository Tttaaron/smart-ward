"""日常活动识别评测脚本（离线跑标注视频片段 -> 混淆矩阵报告）。

背景：7 类日常活动（walking/eating/playing_phone/sleeping/sitting/standing/lying）
此前没有任何量化评测。本脚本把标注片段喂进与生产完全一致的识别链路
（parse_yolo_result -> IoUTracker -> BehaviorAnalyzer -> ActivityRecognizer ->
build_activity_entry），输出每类精确率/召回率/F1 与混淆矩阵，作为
docs/27 评测方案的配套工具。

片段命名约定（双下划线分隔）::

    {label}__{subject}__{take}.mp4     例：sitting__subjectA__01.mp4

label 取以下之一；subject/take 用于区分被摄者与重复录制::

    walking eating playing_phone sleeping sitting standing lying

注意：sleeping 的判定规则是"躺姿持续 >=60 秒"，sleeping 片段必须包含
至少 60 秒真实时长的躺姿（fps 与帧数按实际视频计算，不受 stride 影响）。

用法::

    python edge-agent/scripts/eval_activity.py --clips-dir data/activity_eval \
        --model yolo11n-pose.pt --out docs/evidence/activity-eval-report.json

依赖：pip install -r edge-agent/requirements-yolo.txt（ultralytics + opencv）
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "edge-agent" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from adapters.yolo_camera import build_activity_entry, parse_yolo_result  # noqa: E402
from activity_tracker import ActivityRecognizer  # noqa: E402
from behavior import BehaviorAnalyzer  # noqa: E402
from tracking import IoUTracker  # noqa: E402

LABELS = ["walking", "eating", "playing_phone",
          "sleeping", "sitting", "standing", "lying"]


def parse_clip_name(path: Path) -> Tuple[Optional[str], str]:
    """从文件名解析 (真值标签, 片段名)；不合规命名返回 (None, 原名)"""
    stem = path.stem
    parts = stem.split("__")
    if parts and parts[0] in LABELS:
        return parts[0], stem
    return None, stem


class ClipRunner:
    """按生产链路逐帧处理一个视频片段，收集每帧主活动标签"""

    def __init__(self, model, conf: float, device: Optional[str]):
        self.model = model
        self.conf = conf
        self.device = device

    def run(self, video_path: Path, stride: int) -> List[str]:
        import cv2  # 延迟导入：无 opencv 时给出可读错误

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError(f"无法打开视频: {video_path}")
        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0

        tracker = IoUTracker()
        analyzer = BehaviorAnalyzer()
        recognizer = ActivityRecognizer()
        labels: List[str] = []
        frame_index = 0
        last_activity: Optional[str] = None
        activity_since = 0.0

        try:
            while True:
                ok, frame = capture.read()
                if not ok or frame is None:
                    break
                if frame_index % stride != 0:
                    frame_index += 1
                    continue

                height, width = frame.shape[:2]
                kwargs = {
                    "source": frame,
                    "conf": self.conf,
                    "classes": [0],
                    "verbose": False,
                }
                if self.device:
                    kwargs["device"] = self.device
                results = self.model.predict(**kwargs)
                result = results[0] if isinstance(results, (list, tuple)) else results

                # 与 adapters/yolo_camera.YoloCameraAdapter.read() 完全一致的处理顺序
                detections = parse_yolo_result(result, width, height)
                tracked = tracker.update(detections)
                for detection in tracked:
                    detection.pop("backend_track_id", None)

                # 时间戳用帧号/fps 折算的真实时长：保证 sleeping(>=60s)、
                # standing/sitting(>=5s) 等时长型规则与真实时间同尺度
                now = frame_index / fps
                behavior = analyzer.update(tracked, timestamp=now)
                behavior_tracks = behavior.get("tracks") or []
                recognizer.update(behavior_tracks, timestamp=now)
                activity_entry, last_activity, activity_since = build_activity_entry(
                    behavior_tracks, last_activity, activity_since, now)
                if activity_entry:
                    labels.append(activity_entry["label"])
                frame_index += 1
        finally:
            capture.release()
        return labels


def majority_label(labels: List[str]) -> str:
    """帧级标签投票：忽略 unknown，取出现最多者；全 unknown 则 unknown"""
    counted = Counter(label for label in labels if label != "unknown")
    if not counted:
        return "unknown"
    return counted.most_common(1)[0][0]


def evaluate(clips_dir: Path, runner: ClipRunner, stride: int,
             min_frames: int) -> Tuple[List[Tuple[str, str, str]], List[str]]:
    """返回 (逐片段结果, 警告列表)；逐片段为 (truth, predicted, clip_name)"""
    videos = sorted(
        p for p in clips_dir.iterdir()
        if p.suffix.lower() in (".mp4", ".avi", ".mov", ".mkv")
    )
    if not videos:
        raise SystemExit(f"{clips_dir} 下没有找到视频文件")

    rows: List[Tuple[str, str, str]] = []
    warnings: List[str] = []
    for video in videos:
        truth, name = parse_clip_name(video)
        if truth is None:
            warnings.append(f"跳过（命名不符合 {{label}}__... 约定）: {video.name}")
            continue
        started = time.perf_counter()
        frame_labels = runner.run(video, stride)
        elapsed = time.perf_counter() - started
        if len(frame_labels) < min_frames:
            warnings.append(
                f"{name}: 有效帧仅 {len(frame_labels)} (<{min_frames})，结果不可信")
        predicted = majority_label(frame_labels)
        rows.append((truth, predicted, name))
        mark = "✅" if truth == predicted else "❌"
        print(f"{mark} {name}: truth={truth} pred={predicted} "
              f"frames={len(frame_labels)} ({elapsed:.1f}s)")
    return rows, warnings


def build_report(rows: List[Tuple[str, str, str]]) -> Dict:
    """混淆矩阵 + 每类 P/R/F1 + 总体准确率"""
    matrix = defaultdict(Counter)  # truth -> Counter(predicted)
    for truth, predicted, _ in rows:
        matrix[truth][predicted] += 1

    per_class = {}
    for label in LABELS:
        tp = sum(1 for t, p, _ in rows if t == label and p == label)
        fp = sum(1 for t, p, _ in rows if t != label and p == label)
        fn = sum(1 for t, p, _ in rows if t == label and p != label)
        support = sum(1 for t, _, _ in rows if t == label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if precision + recall else 0.0)
        per_class[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }

    correct = sum(1 for t, p, _ in rows if t == p)
    return {
        "overall": {
            "accuracy": round(correct / len(rows), 4) if rows else 0.0,
            "clips": len(rows),
        },
        "per_class": per_class,
        "confusion_matrix": {
            truth: dict(counter) for truth, counter in sorted(matrix.items())
        },
        "per_clip": [
            {"clip": name, "truth": truth, "predicted": predicted}
            for truth, predicted, name in rows
        ],
    }


def print_report(report: Dict) -> None:
    overall = report["overall"]
    print(f"\n===== 总体：accuracy={overall['accuracy']:.2%} "
          f"({overall['clips']} clips) =====")
    print(f"{'label':<15}{'P':>8}{'R':>8}{'F1':>8}{'support':>9}")
    for label, stats in report["per_class"].items():
        if stats["support"]:
            print(f"{label:<15}{stats['precision']:>8.2%}{stats['recall']:>8.2%}"
                  f"{stats['f1']:>8.2%}{stats['support']:>9}")
        else:
            print(f"{label:<15}{'-':>8}{'-':>8}{'-':>8}{stats['support']:>9}"
                  f"   (该类没有片段)")
    print("\n混淆矩阵（行=真值 列=预测）:")
    for truth, preds in report["confusion_matrix"].items():
        print(f"  {truth}: {preds}")


def main() -> int:
    parser = argparse.ArgumentParser(description="日常活动识别评测")
    parser.add_argument("--clips-dir", required=True,
                        help="标注片段目录，命名 {label}__{subject}__{take}.mp4")
    parser.add_argument("--model", default="yolo11n-pose.pt",
                        help="YOLO-Pose 模型路径（默认 yolo11n-pose.pt）")
    parser.add_argument("--conf", type=float, default=0.25,
                        help="检测置信阈值（默认 0.25，与实时链路对齐）")
    parser.add_argument("--stride", type=int, default=1,
                        help="每 N 帧取 1 帧（默认 1；>1 可加速但注意时长规则）")
    parser.add_argument("--device", default=None, help="推理设备，如 cpu/0")
    parser.add_argument("--min-frames", type=int, default=10,
                        help="有效帧数下限，低于则告警（默认 10）")
    parser.add_argument("--out", help="JSON 报告输出路径")
    args = parser.parse_args()

    try:
        from ultralytics import YOLO  # noqa: F401
    except ModuleNotFoundError:
        print("缺少 ultralytics：pip install -r edge-agent/requirements-yolo.txt")
        return 2

    clips_dir = Path(args.clips_dir)
    if not clips_dir.is_dir():
        print(f"目录不存在: {clips_dir}")
        return 2

    model = YOLO(args.model)
    runner = ClipRunner(model, conf=args.conf, device=args.device)
    started = time.perf_counter()
    rows, warnings = evaluate(clips_dir, runner, args.stride, args.min_frames)

    for warning in warnings:
        print(f"⚠️  {warning}")
    report = build_report(rows)
    report["meta"] = {
        "model": args.model, "conf": args.conf, "stride": args.stride,
        "device": args.device, "elapsed_seconds": round(time.perf_counter() - started, 1),
        "pipeline": "parse_yolo_result -> IoUTracker -> BehaviorAnalyzer "
                    "-> ActivityRecognizer -> build_activity_entry",
    }
    print_report(report)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(f"\n报告已写入 {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
