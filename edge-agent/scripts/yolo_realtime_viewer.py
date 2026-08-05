"""Real-time YOLO/YOLO-Pose viewer for local camera validation.

This is intentionally separate from the edge-agent MQTT loop.  It provides a
visual acceptance tool for the camera pipeline before connecting it to ward
events.

Examples (PowerShell):
    $env:KMP_DUPLICATE_LIB_OK = "TRUE"  # only for affected Anaconda installs
    $env:PYTHONPATH = "E:\\CODE\\CODE\\smart classroom\\smart-ward\\edge-agent\\src"
    python edge-agent/scripts/yolo_realtime_viewer.py --camera 0 --device 0

Keys:
    Q / ESC: quit
    Space: pause/resume
    S: save the current annotated frame
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


WINDOW_TITLE = "Smart Ward - YOLO Realtime Monitor"


def parse_source(value: str) -> Any:
    return int(value) if str(value).isdigit() else value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart-ward real-time YOLO monitor")
    parser.add_argument(
        "--camera", "--source", dest="source", default="0",
        help="camera index or video/image path; default 0",
    )
    parser.add_argument(
        "--model", default="edge-agent/models/yolo11n-pose.pt",
        help="YOLO/YOLO-Pose model path",
    )
    parser.add_argument("--device", default="0", help="Ultralytics device, e.g. 0 or cpu")
    parser.add_argument("--conf", type=float, default=0.35, help="person confidence threshold")
    parser.add_argument("--width", type=int, default=1280, help="window width")
    parser.add_argument("--height", type=int, default=720, help="window height")
    parser.add_argument(
        "--screenshot-dir", default="edge-agent/data/yolo-viewer",
        help="directory for S screenshots",
    )
    parser.add_argument(
        "--log-dir", default="edge-agent/data/yolo-logs",
        help="directory for real-time TXT activity logs",
    )
    parser.add_argument(
        "--log-interval", type=float, default=0.5,
        help="minimum seconds between regular frame log lines",
    )
    return parser.parse_args()


class SessionLogger:
    """Write a compact, flush-on-write TXT record for one viewer session."""

    def __init__(self, log_dir: Path, args: argparse.Namespace):
        log_dir.mkdir(parents=True, exist_ok=True)
        # 毫秒粒度文件名，避免同一秒内多次重启覆盖上一份日志
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        self.path = log_dir / f"yolo_session_{stamp}.txt"
        self.handle = self.path.open("w", encoding="utf-8")
        self.started_at = time.time()
        self.last_regular_log_at = 0.0
        self.last_signature: Optional[str] = None
        self.fall_active = False
        self.frame_count = 0
        self.event_count = 0
        self.log_interval = max(0.1, float(args.log_interval))
        self.write("SMART WARD YOLO SESSION LOG")
        self.write(f"started_at={datetime.now().isoformat(timespec='seconds')}")
        self.write(f"source={args.source}")
        self.write(f"model={args.model}")
        self.write(f"device={args.device}")
        self.write("format=timestamp | type | details")
        self.write("-" * 80)

    def write(self, message: str) -> None:
        line = f"{datetime.now().isoformat(timespec='milliseconds')} | {message}\n"
        self.handle.write(line)
        self.handle.flush()

    def record_frame(
        self,
        frame_id: int,
        inference_ms: float,
        fps: float,
        behavior: Dict[str, Any],
    ) -> None:
        self.frame_count = frame_id
        tracks = behavior.get("tracks", []) or []
        track_text = ", ".join(
            f"ID={item.get('track_id', '?')}"
            f" posture={item.get('posture', 'unknown')}"
            f" action={item.get('action', 'unknown')}"
            f" fall={float(item.get('fall_score', 0.0) or 0.0):.2f}"
            for item in tracks
        ) or "none"
        sequence = "->".join(behavior.get("posture_sequence", [])[-8:]) or "none"
        action = behavior.get("action", "none")
        activity = behavior.get("activity", "unknown")
        fall_score = float(behavior.get("fall_score", 0.0) or 0.0)
        signature = f"{behavior.get('track_count', 0)}|{action}|{activity}|{sequence}|{fall_score:.2f}"
        now = time.monotonic()
        state_changed = signature != self.last_signature
        fall_now = action in {"falling", "suspected_fall"} or fall_score >= 0.6

        # Always record state changes and fall transitions; regular snapshots
        # are throttled so a long session does not produce an unusable file.
        should_log = state_changed or (now - self.last_regular_log_at >= self.log_interval)
        if should_log:
            kind = "BEHAVIOR_CHANGE" if state_changed else "FRAME"
            self.write(
                f"{kind} frame={frame_id} fps={fps:.1f} inference_ms={inference_ms:.1f} "
                f"persons={behavior.get('track_count', 0)} action={action} "
                f"activity={activity} sequence={sequence} "
                f"duration={float(behavior.get('position_duration', 0.0) or 0.0):.1f}s "
                f"fall_score={fall_score:.2f} tracks=[{track_text}]"
            )
            self.last_regular_log_at = now
            self.last_signature = signature

        if fall_now and not self.fall_active:
            self.event_count += 1
            self.write(
                f"EVENT type=fall_suspected frame={frame_id} "
                f"confidence={fall_score:.2f} sequence={sequence} "
                f"duration={float(behavior.get('position_duration', 0.0) or 0.0):.1f}s"
            )
        elif not fall_now and self.fall_active:
            self.write(f"EVENT type=fall_recovered frame={frame_id}")
        self.fall_active = fall_now

    def pause(self, frame_id: int) -> None:
        self.write(f"CONTROL type=pause frame={frame_id}")

    def resume(self, frame_id: int) -> None:
        self.write(f"CONTROL type=resume frame={frame_id}")

    def close(self, reason: str, frame_id: int) -> None:
        elapsed = max(0.0, time.time() - self.started_at)
        self.write(
            f"SESSION_END reason={reason} frames={frame_id} "
            f"fall_events={self.event_count} elapsed_seconds={elapsed:.1f}"
        )
        self.handle.close()


def _gpu_memory_mb(torch_module: Any, device: str) -> float:
    try:
        if str(device).lower() == "cpu" or not torch_module.cuda.is_available():
            return 0.0
        return torch_module.cuda.memory_allocated(0) / 1024 / 1024
    except Exception:
        return 0.0


def _color_for_behavior(behavior: Dict[str, Any]) -> tuple:
    action = behavior.get("action", "")
    fall_score = float(behavior.get("fall_score", 0.0) or 0.0)
    if action in {"falling", "suspected_fall"} or fall_score >= 0.6:
        return (40, 40, 230)  # red, BGR
    if action == "edge_lying":
        return (0, 165, 255)  # orange
    return (50, 205, 50)  # green


def _draw_panel(frame: Any, lines: List[str], cv2_module: Any) -> None:
    overlay = frame.copy()
    height, width = frame.shape[:2]
    panel_height = min(height, 126 + len(lines) * 23)
    cv2_module.rectangle(overlay, (0, 0), (width, panel_height), (15, 22, 30), -1)
    cv2_module.addWeighted(overlay, 0.82, frame, 0.18, 0, frame)
    y = 28
    for index, line in enumerate(lines):
        scale = 0.72 if index == 0 else 0.58
        thickness = 2 if index == 0 else 1
        color = (90, 220, 255) if index == 0 else (230, 240, 245)
        cv2_module.putText(
            frame, line, (18, y), cv2_module.FONT_HERSHEY_SIMPLEX,
            scale, color, thickness, cv2_module.LINE_AA,
        )
        y += 23


def _draw_tracks(frame: Any, tracks: List[Dict[str, Any]], cv2_module: Any) -> None:
    height, width = frame.shape[:2]
    for track in tracks:
        bbox = track.get("bbox") or []
        if len(bbox) != 4:
            continue
        x, y, box_width, box_height = bbox
        left = max(0, int(float(x) * width))
        top = max(0, int(float(y) * height))
        right = min(width - 1, int(float(x + box_width) * width))
        bottom = min(height - 1, int(float(y + box_height) * height))
        color = _color_for_behavior(track)
        cv2_module.rectangle(frame, (left, top), (right, bottom), color, 2)
        label = (
            f"ID {track.get('track_id', '?')} "
            f"{track.get('posture', 'unknown')} "
            f"fall={float(track.get('fall_score', 0.0) or 0.0):.2f}"
        )
        (label_width, label_height), baseline = cv2_module.getTextSize(
            label, cv2_module.FONT_HERSHEY_SIMPLEX, 0.52, 1,
        )
        label_top = max(0, top - label_height - baseline - 4)
        cv2_module.rectangle(
            frame, (left, label_top), (left + label_width + 8, top), color, -1,
        )
        cv2_module.putText(
            frame, label, (left + 4, max(label_height + 1, top - 5)),
            cv2_module.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1,
            cv2_module.LINE_AA,
        )


def run() -> int:
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    source_dir = repo_root / "edge-agent" / "src"
    if str(source_dir) not in sys.path:
        sys.path.insert(0, str(source_dir))

    try:
        import cv2
        import torch
        from ultralytics import YOLO
        from adapters.yolo_camera import parse_yolo_result
        from behavior import BehaviorAnalyzer
        from tracking import IoUTracker
        from activity_tracker import ActivityRecognizer
    except ImportError as exc:
        print(f"Missing dependency: {exc}")
        print("Install with: python -m pip install -r edge-agent/requirements-yolo.txt")
        return 2

    model_path = Path(args.model)
    if not model_path.is_absolute():
        model_path = repo_root / model_path
    if not model_path.exists():
        print(f"Model not found: {model_path}")
        return 2

    source = parse_source(args.source)
    camera = cv2.VideoCapture(source)
    if not camera.isOpened():
        print(f"Cannot open camera/source: {source}")
        return 3
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    print(f"Loading model: {model_path}")
    print(f"Device: {args.device}; CUDA available: {torch.cuda.is_available()}")
    model = YOLO(str(model_path))
    tracker = IoUTracker()
    behavior_analyzer = BehaviorAnalyzer()
    activity_recognizer = ActivityRecognizer()
    screenshot_dir = Path(args.screenshot_dir)
    if not screenshot_dir.is_absolute():
        screenshot_dir = repo_root / screenshot_dir
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    log_dir = Path(args.log_dir)
    if not log_dir.is_absolute():
        log_dir = repo_root / log_dir
    logger = SessionLogger(log_dir, args)
    print(f"Log file: {logger.path}")

    cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_TITLE, args.width, args.height)

    frame_times = deque(maxlen=30)
    frame_count = 0
    paused = False
    last_frame = None
    last_behavior: Dict[str, Any] = {"active": False, "action": "none"}
    stop_reason = "user_exit"

    try:
        while True:
            if not paused:
                ok, frame = camera.read()
                if not ok or frame is None:
                    print("Camera/source read failed")
                    stop_reason = "camera_read_failed"
                    break
                frame_count += 1

                started = time.perf_counter()
                results = model.predict(
                    source=frame,
                    conf=max(0.05, min(0.99, args.conf)),
                    classes=[0],
                    device=args.device,
                    verbose=False,
                )
                inference_ms = (time.perf_counter() - started) * 1000
                result = results[0] if results else None
                if result is not None:
                    annotated = result.plot(conf=True, labels=True, boxes=True)
                    frame_height, frame_width = annotated.shape[:2]
                    detections = parse_yolo_result(result, frame_width, frame_height)
                else:
                    annotated = frame.copy()
                    detections = []

                tracked = tracker.update(detections)
                behavior = behavior_analyzer.update(tracked, timestamp=time.time())
                activity_recognizer.update(behavior.get("tracks", []), timestamp=time.time())
                tracks = behavior.get("tracks", [])
                primary_activity = "unknown"
                if tracks:
                    primary_track = max(tracks, key=lambda t: (t.get("confidence", 0), t.get("track_id", 0)))
                    primary_activity = primary_track.get("activity", "unknown")
                behavior["activity"] = primary_activity
                last_behavior = behavior
                _draw_tracks(annotated, behavior.get("tracks", []), cv2)

                frame_times.append(time.perf_counter())
                fps = (
                    (len(frame_times) - 1) /
                    max(frame_times[-1] - frame_times[0], 1e-6)
                    if len(frame_times) > 1 else 0.0
                )
                logger.record_frame(frame_count, inference_ms, fps, behavior)
                sequence = " -> ".join(behavior.get("posture_sequence", [])[-5:]) or "none"
                lines = [
                    "SMART WARD YOLO REALTIME MONITOR",
                    f"Model: {model_path.name} | Device: {args.device} | CUDA: {torch.cuda.is_available()}",
                    f"FPS: {fps:.1f} | Inference: {inference_ms:.1f} ms | GPU memory: {_gpu_memory_mb(torch, args.device):.0f} MB",
                    f"Persons: {behavior.get('track_count', 0)} | Action: {behavior.get('action', 'none')} | Fall: {float(behavior.get('fall_score', 0.0) or 0.0):.2f}",
                    f"Activity: {behavior.get('activity', 'unknown')} | Posture sequence: {sequence} | Duration: {float(behavior.get('position_duration', 0.0) or 0.0):.1f}s",
                    "Q/ESC quit | SPACE pause | S screenshot",
                ]
                _draw_panel(annotated, lines, cv2)
                last_frame = annotated

            if last_frame is not None:
                display = last_frame.copy()
                if paused:
                    cv2.putText(
                        display, "PAUSED", (20, display.shape[0] - 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 215, 255), 2,
                        cv2.LINE_AA,
                    )
                cv2.imshow(WINDOW_TITLE, display)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            if key == ord(" "):
                paused = not paused
                if paused:
                    logger.pause(frame_count)
                else:
                    logger.resume(frame_count)
            elif key in (ord("s"), ord("S")) and last_frame is not None:
                output = screenshot_dir / f"yolo_{int(time.time() * 1000)}.jpg"
                cv2.imwrite(str(output), last_frame)
                print(f"Screenshot saved: {output}")
    except KeyboardInterrupt:
        # Ctrl+C 是正常主动中断，与 Q/ESC 同样写明确结束原因
        stop_reason = "keyboard_interrupt"
        logger.write("CONTROL type=keyboard_interrupt")
    except Exception as exc:
        stop_reason = f"error:{type(exc).__name__}"
        logger.write(f"ERROR message={str(exc)}")
        raise
    finally:
        camera.release()
        cv2.destroyAllWindows()
        logger.close(stop_reason, frame_count)

    print(f"Stopped. Processed frames: {frame_count}")
    print(f"TXT log saved: {logger.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
