"""Lightweight person tracking for edge camera observations.

The tracker intentionally has no NumPy/OpenCV dependency.  A real YOLO
backend can provide its own track IDs; this module is the fallback used when
the backend only returns bounding boxes.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


BBox = List[float]  # normalized [x, y, width, height]


def _validate_bbox(bbox: Any) -> Optional[BBox]:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        x, y, width, height = (float(value) for value in bbox)
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    return [x, y, width, height]


def bbox_iou(left: BBox, right: BBox) -> float:
    """Return intersection-over-union for normalized xywh boxes."""
    lx, ly, lw, lh = left
    rx, ry, rw, rh = right
    l_x2, l_y2 = lx + lw, ly + lh
    r_x2, r_y2 = rx + rw, ry + rh

    intersection_width = max(0.0, min(l_x2, r_x2) - max(lx, rx))
    intersection_height = max(0.0, min(l_y2, r_y2) - max(ly, ry))
    intersection = intersection_width * intersection_height
    if intersection <= 0:
        return 0.0

    union = lw * lh + rw * rh - intersection
    return intersection / union if union > 0 else 0.0


@dataclass
class _Track:
    track_id: int
    bbox: BBox
    missed: int = 0


class IoUTracker:
    """Small deterministic tracker for a ward camera with few people.

    It greedily matches the highest IoU pairs.  Ultralytics/ByteTrack IDs are
    preferred by the YOLO adapter; this fallback keeps IDs stable when a
    backend does not return IDs.
    """

    def __init__(self, iou_threshold: float = 0.3, max_missed: int = 15):
        self.iou_threshold = max(0.0, min(1.0, iou_threshold))
        self.max_missed = max(0, max_missed)
        self._next_id = 1
        self._tracks: Dict[int, _Track] = {}

    def update(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Attach a stable ``track_id`` to each detection."""
        normalized = []
        for detection in detections:
            bbox = _validate_bbox(detection.get("bbox"))
            if bbox is None:
                continue
            item = dict(detection)
            item["bbox"] = bbox
            normalized.append(item)

        candidates: List[Tuple[float, int, int]] = []
        for detection_index, detection in enumerate(normalized):
            for track_id, track in self._tracks.items():
                candidates.append((bbox_iou(detection["bbox"], track.bbox), detection_index, track_id))
        candidates.sort(reverse=True)

        matched_detections = set()
        matched_tracks = set()
        assignments: Dict[int, int] = {}
        for score, detection_index, track_id in candidates:
            if score < self.iou_threshold:
                break
            if detection_index in matched_detections or track_id in matched_tracks:
                continue
            assignments[detection_index] = track_id
            matched_detections.add(detection_index)
            matched_tracks.add(track_id)

        for detection_index, detection in enumerate(normalized):
            track_id = assignments.get(detection_index)
            if track_id is None:
                track_id = self._next_id
                self._next_id += 1
            detection["track_id"] = track_id
            self._tracks[track_id] = _Track(track_id=track_id, bbox=detection["bbox"], missed=0)

        for track_id, track in list(self._tracks.items()):
            if track_id not in matched_tracks and not any(
                item.get("track_id") == track_id for item in normalized
            ):
                track.missed += 1
                if track.missed > self.max_missed:
                    self._tracks.pop(track_id, None)

        return normalized

    def reset(self) -> None:
        self._tracks.clear()
        self._next_id = 1

