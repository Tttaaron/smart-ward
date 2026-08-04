"""Temporal behavior features derived from tracked person detections.

This module deliberately produces conservative features rather than medical
diagnoses.  It converts per-frame detections into a compact, JSON-safe summary
consumed by the existing inference/fusion/LLM layers.
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt
from typing import Any, Deque, Dict, Iterable, List, Optional


UPRIGHT_POSTURES = {"standing", "sitting", "leaning", "grabbing_chest"}
LYING_POSTURES = {"lying", "lying_edge", "falling"}


def _timestamp_seconds(timestamp: Any) -> float:
    if isinstance(timestamp, (int, float)):
        return float(timestamp)
    if not timestamp:
        return datetime.now(timezone.utc).timestamp()
    try:
        value = str(timestamp).replace("Z", "+00:00")
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return datetime.now(timezone.utc).timestamp()


def _bbox_aspect(bbox: List[float]) -> float:
    width = max(float(bbox[2]), 1e-6)
    return float(bbox[3]) / width


def estimate_posture(bbox: List[float], keypoints: Optional[List[List[float]]] = None) -> str:
    """Estimate coarse posture when the YOLO model does not provide one.

    Pose keypoints are preferred when available.  The bbox fallback is useful
    for a detection-only model, but remains ``unknown`` for ambiguous shapes.
    """
    if keypoints:
        valid = [point for point in keypoints if len(point) >= 3 and point[2] >= 0.25]
        if len(valid) >= 4:
            ys = [float(point[1]) for point in valid]
            xs = [float(point[0]) for point in valid]
            spread_x = max(xs) - min(xs)
            spread_y = max(ys) - min(ys)
            if spread_x > spread_y * 1.15:
                return "lying"
            if spread_y > spread_x * 1.35:
                return "standing"

    aspect = _bbox_aspect(bbox)
    if aspect >= 1.55:
        return "standing"
    if aspect <= 0.85:
        return "lying"
    return "unknown"


@dataclass
class _Frame:
    timestamp: float
    bbox: List[float]
    posture: str
    confidence: float
    keypoints: List[List[float]]


class BehaviorAnalyzer:
    """Maintain short per-person histories and derive behavior features."""

    def __init__(self, history_size: int = 24, track_ttl_seconds: float = 8.0):
        self.history_size = max(4, history_size)
        self.track_ttl_seconds = max(1.0, track_ttl_seconds)
        self._histories: Dict[int, Deque[_Frame]] = {}
        self._last_seen: Dict[int, float] = {}

    def update(
        self,
        detections: Iterable[Dict[str, Any]],
        timestamp: Any = None,
        bed_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = _timestamp_seconds(timestamp)
        current = []

        for detection in detections:
            try:
                track_id = int(detection["track_id"])
                bbox = [float(value) for value in detection["bbox"]]
            except (KeyError, TypeError, ValueError):
                continue
            keypoints = detection.get("keypoints") or detection.get("pose_keypoints") or []
            posture = str(detection.get("posture") or estimate_posture(bbox, keypoints))
            frame = _Frame(
                timestamp=now,
                bbox=bbox,
                posture=posture,
                confidence=float(detection.get("confidence", 0.0)),
                keypoints=keypoints,
            )
            history = self._histories.setdefault(track_id, deque(maxlen=self.history_size))
            history.append(frame)
            self._last_seen[track_id] = now
            current.append((track_id, frame, history, detection))

        self._expire(now)

        tracks = [self._summarize_track(track_id, frame, history, detection)
                  for track_id, frame, history, detection in current]
        if not tracks:
            return {
                "active": False,
                "track_count": 0,
                "tracks": [],
                "action": "none",
                "posture_sequence": [],
                "fall_score": 0.0,
                "tremor_score": 0.0,
                "position_duration": 0,
                "bed_context": bed_context or {},
            }

        # A ward bed normally has one patient.  Keep all tracks for evidence,
        # while selecting the most confident one as the primary behavior.
        primary = max(tracks, key=lambda item: (item["confidence"], item["track_id"]))
        result = dict(primary)
        result.update({
            "active": True,
            "track_count": len(tracks),
            "tracks": tracks,
            "bed_context": bed_context or {},
        })
        return result

    def _summarize_track(self, track_id: int, frame: _Frame,
                         history: Deque[_Frame],
                         detection: Dict[str, Any] = None) -> Dict[str, Any]:
        previous = history[-2] if len(history) >= 2 else None
        sequence = [item.posture for item in list(history)[-8:]]
        position_start = frame.timestamp
        for item in reversed(list(history)[:-1]):
            if item.posture != frame.posture:
                break
            position_start = item.timestamp

        posture_duration = max(0.0, frame.timestamp - position_start)
        orientation_change = 0.0
        vertical_speed = 0.0
        transition = False
        if previous:
            orientation_change = min(1.0, abs(_bbox_aspect(frame.bbox) - _bbox_aspect(previous.bbox)) / 2.0)
            elapsed = max(frame.timestamp - previous.timestamp, 0.001)
            vertical_speed = (frame.bbox[1] + frame.bbox[3] / 2 - previous.bbox[1] - previous.bbox[3] / 2) / elapsed
            transition = previous.posture in UPRIGHT_POSTURES and frame.posture in LYING_POSTURES

        # 任务书方案：优先使用 FallDetector（ShuffleNetV2+SA）注入的结果；
        # 检测字段缺 fall_score/action 时回退到原规则判定，保持向后兼容。
        detector_fall_score = (detection or {}).get("fall_score")
        detector_action = (detection or {}).get("action")
        if detector_fall_score is not None and detector_action:
            fall_score = float(detector_fall_score)
            action = str(detector_action)
        else:
            if frame.posture == "falling":
                action = "falling"
            elif transition:
                action = "suspected_fall"
            elif frame.posture == "lying_edge":
                action = "edge_lying"
            else:
                action = frame.posture
            fall_score = 0.0
            if transition or frame.posture == "falling":
                speed_score = min(1.0, max(0.0, vertical_speed) / 0.6)
                fall_score = min(1.0, 0.62 + 0.2 * orientation_change + 0.18 * speed_score)

        tremor_score = self._tremor_score(history)
        return {
            "track_id": track_id,
            "confidence": round(frame.confidence, 3),
            "bbox": frame.bbox,
            "posture": frame.posture,
            "action": action,
            "posture_sequence": sequence,
            "position_duration": round(posture_duration, 3),
            "fall_score": round(fall_score, 3),
            "tremor_score": round(tremor_score, 3),
            "motion": {
                "vertical_speed": round(vertical_speed, 4),
                "orientation_change": round(orientation_change, 3),
            },
            "pose_keypoints": frame.keypoints,
        }

    @staticmethod
    def _tremor_score(history: Deque[_Frame]) -> float:
        if len(history) < 4:
            return 0.0
        frames = list(history)[-6:]
        centers = [
            (frame.bbox[0] + frame.bbox[2] / 2, frame.bbox[1] + frame.bbox[3] / 2)
            for frame in frames
        ]
        motions = [
            sqrt((right[0] - left[0]) ** 2 + (right[1] - left[1]) ** 2)
            for left, right in zip(centers, centers[1:])
        ]
        if not motions:
            return 0.0
        mean_motion = sum(motions) / len(motions)
        alternations = sum(
            1 for left, right in zip(motions, motions[1:]) if (right - mean_motion) * (left - mean_motion) < 0
        )
        motion_score = min(1.0, mean_motion / 0.04)
        alternation_score = alternations / max(1, len(motions) - 1)
        return min(1.0, 0.65 * motion_score + 0.35 * alternation_score)

    def _expire(self, now: float) -> None:
        for track_id, last_seen in list(self._last_seen.items()):
            if now - last_seen > self.track_ttl_seconds:
                self._last_seen.pop(track_id, None)
                self._histories.pop(track_id, None)

    def reset(self) -> None:
        self._histories.clear()
        self._last_seen.clear()

