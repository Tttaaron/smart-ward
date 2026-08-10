"""Optional real camera adapter backed by Ultralytics YOLO/YOLO-Pose.

The default project mode remains ``CameraAdapter`` (scenario/mock).  This
adapter is selected with ``CAMERA_MODE=yolo`` and emits the same Observation
shape plus detections, tracks, and temporal behavior features.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from behavior import BehaviorAnalyzer
from tracking import IoUTracker
from fall_detector import FallDetector
from activity_tracker import ActivityRecognizer
from .base import BaseAdapter, Observation, Quality


def _tolist(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _flat_value(values: Any, index: int, default: Any = None) -> Any:
    values = _tolist(values)
    if values is None:
        return default
    try:
        return values[index]
    except (IndexError, TypeError):
        return default


def build_activity_entry(
    tracked: List[Dict[str, Any]],
    last_activity: Optional[str],
    since: float,
    now: float,
) -> tuple:
    """从已识别 track 中提取主活动，生成上报条目（含切换事件）。

    取第一个非 unknown 的活动作为主活动；活动变化时标记 switched，
    供前端活动日志面板与 LLM 时段摘要使用。

    Returns: (activity_entry, new_last_activity, new_since)
    """
    primary: Optional[str] = None
    for detection in tracked:
        activity = detection.get("activity")
        if activity and activity != "unknown":
            primary = str(activity)
            break
    entry: Dict[str, Any] = {
        "label": primary or "unknown",
        "since": round(since, 2),
        "switched": False,
        "previous": last_activity,
    }
    if primary and primary != last_activity:
        entry["switched"] = True
        entry["previous"] = last_activity
        return entry, primary, now
    return entry, last_activity, since


def parse_yolo_result(result: Any, frame_width: int, frame_height: int) -> List[Dict[str, Any]]:
    """Convert one Ultralytics result into normalized person detections.

    This function is isolated from the runtime so it can be tested with fake
    result objects and remains compatible with CPU tensors, NumPy arrays, and
    plain Python lists.
    """
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []

    xyxy = _tolist(getattr(boxes, "xyxy", None)) or []
    confidences = _tolist(getattr(boxes, "conf", None)) or []
    class_ids = _tolist(getattr(boxes, "cls", None)) or []
    track_ids = _tolist(getattr(boxes, "id", None))
    keypoints_obj = getattr(result, "keypoints", None)
    keypoints_xy = _tolist(getattr(keypoints_obj, "xy", None)) if keypoints_obj else None
    keypoints_conf = _tolist(getattr(keypoints_obj, "conf", None)) if keypoints_obj else None
    names = getattr(result, "names", {}) or {}

    width = max(float(frame_width), 1.0)
    height = max(float(frame_height), 1.0)
    detections: List[Dict[str, Any]] = []
    for index, coordinates in enumerate(xyxy):
        if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 4:
            continue
        class_id = int(_flat_value(class_ids, index, 0) or 0)
        class_name = names.get(class_id, str(class_id)) if isinstance(names, dict) else str(class_id)
        if class_name != "person" and class_id != 0:
            continue

        x1, y1, x2, y2 = (float(value) for value in coordinates[:4])
        keypoints: List[List[float]] = []
        frame_points = _flat_value(keypoints_xy, index, []) or []
        frame_conf = _flat_value(keypoints_conf, index, []) or []
        for point_index, point in enumerate(frame_points):
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            point_conf = _flat_value(frame_conf, point_index, 1.0) or 0.0
            keypoints.append([
                round(float(point[0]) / width, 6),
                round(float(point[1]) / height, 6),
                round(float(point_conf), 6),
            ])

        track_id = _flat_value(track_ids, index) if track_ids is not None else None
        detections.append({
            "class": "person",
            "class_id": class_id,
            "confidence": round(float(_flat_value(confidences, index, 0.0) or 0.0), 6),
            "bbox": [
                round(x1 / width, 6),
                round(y1 / height, 6),
                round(max(0.0, x2 - x1) / width, 6),
                round(max(0.0, y2 - y1) / height, 6),
            ],
            "keypoints": keypoints,
        })
        if track_id is not None:
            detections[-1]["backend_track_id"] = int(track_id)

    return detections


class YoloCameraAdapter(BaseAdapter):
    """Read frames and emit real YOLO detections with temporal behavior."""

    SOURCE_TYPE = "camera"

    def __init__(
        self,
        node_id: str,
        bed_id: str,
        model_path: str,
        source: Any = 0,
        confidence_threshold: float = 0.35,
        device: Optional[str] = None,
        tracker_iou: float = 0.3,
        tracker_max_missed: int = 8,
        history_size: int = 24,
        save_evidence: bool = False,
        evidence_dir: str = "/app/evidence",
    ):
        super().__init__(node_id, bed_id)
        if not model_path:
            raise ValueError("YOLO_MODEL_PATH is required when CAMERA_MODE=yolo")

        try:
            import cv2
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "CAMERA_MODE=yolo requires optional dependencies; "
                "install edge-agent/requirements-yolo.txt"
            ) from exc

        self._cv2 = cv2
        self.model_path = model_path
        self.model = YOLO(model_path)
        self.source = self._parse_source(source)
        self.capture = cv2.VideoCapture(self.source)
        if not self.capture.isOpened():
            raise RuntimeError(f"cannot open camera source: {self.source}")

        self.confidence_threshold = max(0.05, min(0.99, confidence_threshold))
        self.device = device or None
        self.tracker = IoUTracker(iou_threshold=tracker_iou, max_missed=tracker_max_missed)
        self.behavior = BehaviorAnalyzer(history_size=history_size)
        # 日常活动识别（关键点规则分类，6 类），结果随 observation 上报
        self.activity_recognizer = ActivityRecognizer()
        self._last_activity: Optional[str] = None
        self._activity_since = time.time()
        self.fall_detector = FallDetector(device=device)
        self.frame_id = 0
        self.save_evidence = save_evidence
        self.evidence_dir = evidence_dir
        if self.save_evidence:
            os.makedirs(self.evidence_dir, exist_ok=True)

    @staticmethod
    def _parse_source(source: Any) -> Any:
        if isinstance(source, int):
            return source
        value = str(source)
        return int(value) if value.isdigit() else value

    def read(self) -> Observation:
        started = time.monotonic()
        ok, frame = self.capture.read()
        self.frame_id += 1
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if not ok or frame is None:
            return Observation(
                source_type=self.SOURCE_TYPE,
                data={
                    "presence": False,
                    "person_count": 0,
                    "posture": "unknown",
                    "fall_score": 0.0,
                    "tremor_score": 0.0,
                    "position_duration": 0,
                    "detections": [],
                    "tracks": [],
                    "behavior": {"active": False, "action": "none"},
                    "camera_error": "frame_read_failed",
                },
                quality=Quality(confidence=0.0, latency_ms=round((time.monotonic() - started) * 1000), degraded=True),
                timestamp=timestamp,
            )

        height, width = frame.shape[:2]
        predict_kwargs = {
            "source": frame,
            "conf": self.confidence_threshold,
            "classes": [0],
            "verbose": False,
        }
        if self.device:
            predict_kwargs["device"] = self.device
        results = self.model.predict(**predict_kwargs)
        result = results[0] if isinstance(results, (list, tuple)) else results
        detections = parse_yolo_result(result, width, height)
        tracked = self.tracker.update(detections)
        for detection in tracked:
            detection.pop("backend_track_id", None)

        # 任务书方案：YOLO 检测后送 ShuffleNetV2+SA 做跌倒二分类，
        # 结果写回 detection 的 fall_score/action，覆盖 BehaviorAnalyzer
        # 的原规则判定；activity_tracker 等其他维度不受影响。
        for detection in tracked:
            track_id = detection.get("track_id")
            bbox = detection.get("bbox") or []
            if track_id is None or len(bbox) != 4:
                continue
            x, y, bw, bh = bbox
            x1 = int(x * width)
            y1 = int(y * height)
            x2 = int((x + bw) * width)
            y2 = int((y + bh) * height)
            fall_score, action = self.fall_detector.detect_track(
                track_id, frame, [x1, y1, x2, y2])
            detection["fall_score"] = fall_score
            detection["action"] = action

        behavior = self.behavior.update(tracked, timestamp=timestamp)
        primary = behavior if behavior.get("active") else {}

        # 日常活动识别：复用 YOLO-Pose 关键点做规则分类，
        # 输出带滞回的活动标签 + 切换事件（switched/previous/since）
        self.activity_recognizer.update(tracked, timestamp=time.time())
        activity_entry, self._last_activity, self._activity_since = build_activity_entry(
            tracked, self._last_activity, self._activity_since, time.time())
        evidence_frame_ref = None
        evidence_keypoints_ref = None
        should_save_evidence = self.save_evidence and (
            primary.get("fall_score", 0.0) >= 0.6
            or primary.get("tremor_score", 0.0) >= 0.6
        )
        if should_save_evidence:
            event_dir = os.path.join(self.evidence_dir, self.node_id, str(self.frame_id))
            os.makedirs(event_dir, exist_ok=True)
            frame_path = os.path.join(event_dir, "frame.jpg")
            if self._cv2.imwrite(frame_path, frame):
                evidence_frame_ref = frame_path
            if primary.get("pose_keypoints"):
                keypoints_path = os.path.join(event_dir, "keypoints.json")
                with open(keypoints_path, "w", encoding="utf-8") as handle:
                    json.dump(primary["pose_keypoints"], handle, ensure_ascii=True)
                evidence_keypoints_ref = keypoints_path

        latency_ms = round((time.monotonic() - started) * 1000)
        mean_confidence = (
            sum(item.get("confidence", 0.0) for item in tracked) / len(tracked)
            if tracked else 0.0
        )
        data: Dict[str, Any] = {
            "node_id": self.node_id,
            "bed_id": self.bed_id,
            "frame_id": self.frame_id,
            "presence": bool(tracked),
            "person_count": len(tracked),
            "posture": primary.get("posture", "unknown"),
            "fall_score": primary.get("fall_score", 0.0),
            "tremor_score": primary.get("tremor_score", 0.0),
            "position_duration": primary.get("position_duration", 0),
            "pose_keypoints": primary.get("pose_keypoints", []),
            "bbox": primary.get("bbox"),
            "track_id": primary.get("track_id"),
            "detections": tracked,
            "tracks": behavior.get("tracks", []),
            "behavior": behavior,
            "activity": activity_entry,
            "camera_mode": "yolo",
            "camera_source": str(self.source),
            "model_path": self.model_path,
        }
        if evidence_frame_ref:
            data["evidence_frame_ref"] = evidence_frame_ref
        if evidence_keypoints_ref:
            data["evidence_keypoints_ref"] = evidence_keypoints_ref

        return Observation(
            source_type=self.SOURCE_TYPE,
            data=data,
            quality=Quality(
                confidence=round(mean_confidence, 3),
                latency_ms=latency_ms,
                degraded=False,
            ),
            timestamp=timestamp,
        )

    def health(self) -> Dict[str, Any]:
        return {
            "source_type": self.SOURCE_TYPE,
            "healthy": bool(self.capture and self.capture.isOpened()),
            "mode": "yolo",
            "model_path": self.model_path,
            "frame_id": self.frame_id,
        }

    def close(self) -> None:
        if self.capture:
            self.capture.release()
