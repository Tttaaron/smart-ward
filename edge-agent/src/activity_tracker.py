"""Fine-grained daily activity recognition from YOLO-Pose keypoint sequences.

Route 1 (rule-based): derives activities like playing phone, eating, walking,
sleeping, sitting, standing from the 17-keypoint COCO skeleton + temporal
patterns.  No extra model is required — the same keypoints already produced
by the YOLO-Pose pipeline are re-used.

This module deliberately stays conservative: if the keypoint confidence is
low or the skeleton is ambiguous, it returns ``unknown`` rather than a
confident guess.  It is designed to be composable with the existing
BehaviorAnalyzer output and does not replace it.

Stability design (fixes observed flicker in real camera sessions):

  * Posture comes from the already-smoothed BehaviorAnalyzer ``posture``
    field instead of being re-derived from raw keypoints every frame; a
    small dominant-posture window absorbs single-frame pose flicker.
  * Activity labels use hysteresis (``confirm_frames`` consecutive frames)
    so single-frame eating/walking/playing_phone spikes do not stick; the
    previous activity is kept until a new one is confirmed.
  * Posture duration is accumulated with wall-clock timestamps instead of
    re-walking the short BehaviorAnalyzer history window (default 24
    frames ≈ 0.8 s), so standing/sitting/sleeping can actually reach the
    duration thresholds.

COCO keypoint indices (used by Ultralytics YOLO-Pose):
    0: nose          1: left_eye     2: right_eye
    3: left_ear      4: right_ear    5: left_shoulder
    6: right_shoulder 7: left_elbow  8: right_elbow
    9: left_wrist    10: right_wrist  11: left_hip
   12: right_hip     13: left_knee   14: right_knee
   15: left_ankle    16: right_ankle
"""

from __future__ import annotations

import math
import time
from collections import Counter, deque
from typing import Any, Deque, Dict, List, Optional


# ─── Keypoint index constants ───
NOSE = 0
LEFT_EAR = 3
RIGHT_EAR = 4
LEFT_SHOULDER = 5
RIGHT_SHOULDER = 6
LEFT_ELBOW = 7
RIGHT_ELBOW = 8
LEFT_WRIST = 9
RIGHT_WRIST = 10
LEFT_HIP = 11
RIGHT_HIP = 12
LEFT_KNEE = 13
RIGHT_KNEE = 14
LEFT_ANKLE = 15
RIGHT_ANKLE = 16

# Minimum keypoint confidence to consider a keypoint valid
_MIN_KP_CONF = 0.25

# Distance threshold: wrist-to-ear for phone/eating (normalised coordinate space)
_WRIST_EAR_DIST = 0.15

# Elbow angle threshold: below this → arm is bent (phone)
_ELBOW_BENT_ANGLE_DEG = 120

# Distance thresholds for eating oscillation pattern
_EAT_APPROACH_DIST = 0.10  # wrist-to-nose below this → "approaching mouth"
_EAT_WITHDRAW_DIST = 0.14  # wrist-to-nose above this → "away from mouth"
_EAT_MIN_CYCLES = 2         # at least N approach-withdraw cycles to call it eating

# Walking: ankle alternation threshold (normalised)
_WALK_ANKLE_SPREAD = 0.04

# Sleeping: position duration (seconds)
_SLEEP_MIN_DURATION = 60.0

# Sitting/standing: minimum held duration (seconds)
_STATIC_MIN_DURATION = 5.0


def _kp(kps: List[List[float]], idx: int) -> Optional[List[float]]:
    """Return [x, y, conf] for keypoint *idx*, or None if missing/low-conf."""
    if idx < 0 or idx >= len(kps):
        return None
    point = kps[idx]
    if not isinstance(point, (list, tuple)) or len(point) < 3:
        return None
    if float(point[2]) < _MIN_KP_CONF:
        return None
    return [float(v) for v in point[:3]]


def _distance(a: List[float], b: List[float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _elbow_angle(
    shoulder: List[float], elbow: List[float], wrist: List[float]
) -> Optional[float]:
    """Compute angle at the elbow joint in degrees."""
    v1 = (shoulder[0] - elbow[0], shoulder[1] - elbow[1])
    v2 = (wrist[0] - elbow[0], wrist[1] - elbow[1])
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    mag1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2)
    mag2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2)
    if mag1 < 1e-6 or mag2 < 1e-6:
        return None
    cos_angle = max(-1.0, min(1.0, dot / (mag1 * mag2)))
    return math.degrees(math.acos(cos_angle))


# ─── Per-track history ───

class _KeyFrame:
    """Snapshot of keypoints + bbox at one timestamp."""
    __slots__ = ("timestamp", "keypoints", "bbox")

    def __init__(self, timestamp: float, keypoints: List[List[float]], bbox: List[float]):
        self.timestamp = timestamp
        self.keypoints = keypoints
        self.bbox = bbox


class ActivityRecognizer:
    """Recognize fine-grained daily activities from per-track keypoint history.

    Usage::

        recognizer = ActivityRecognizer()
        # Inside the per-frame loop, after BehaviorAnalyzer.update():
        recognizer.update(behavior["tracks"], timestamp=time.time())
        # Each track dict now has an ``activity`` field.
    """

    def __init__(
        self,
        history_size: int = 60,
        track_ttl_seconds: float = 4.0,
        confirm_frames: int = 5,
        posture_window: int = 5,
    ):
        self.history_size = max(10, history_size)
        self.track_ttl_seconds = max(1.0, track_ttl_seconds)
        self.confirm_frames = max(1, confirm_frames)
        self.posture_window = max(1, posture_window)
        self._histories: Dict[int, Deque[_KeyFrame]] = {}
        self._posture_history: Dict[int, Deque[str]] = {}
        self._last_seen: Dict[int, float] = {}
        # Activity state (hysteresis)
        self._active_activity: Dict[int, str] = {}
        self._pending: Dict[int, int] = {}      # track_id -> consecutive run of _last_raw
        self._last_raw: Dict[int, str] = {}
        # Posture duration state
        self._main_posture: Dict[int, str] = {}
        self._posture_since: Dict[int, float] = {}

    def update(
        self,
        tracks: List[Dict[str, Any]],
        timestamp: Optional[float] = None,
    ) -> None:
        """Classify activity for each track and add an ``activity`` field.

        The track dict is modified in-place.  Tracks whose skeletons are
        ambiguous get ``activity="unknown"``.
        """
        now = timestamp if timestamp is not None else time.time()
        current_ids = set()

        for track in tracks:
            track_id = track.get("track_id")
            if track_id is None:
                continue
            track_id = int(track_id)
            current_ids.add(track_id)

            keypoints = track.get("pose_keypoints") or track.get("keypoints") or []
            bbox = track.get("bbox") or []

            # Raw posture comes from BehaviorAnalyzer (already smoothed); keep
            # a short window and take the dominant value to absorb 1-frame
            # flicker between e.g. standing/unknown.
            raw_posture = str(track.get("posture") or "unknown")
            postures = self._posture_history.setdefault(
                track_id, deque(maxlen=self.posture_window))
            postures.append(raw_posture)
            main_posture = self._dominant_posture(postures)

            # Wall-clock posture duration: reset only when the dominant
            # posture changes (not on single-frame flicker).
            if self._main_posture.get(track_id) != main_posture:
                self._main_posture[track_id] = main_posture
                self._posture_since[track_id] = now
            duration = max(0.0, now - self._posture_since.get(track_id, now))

            history = self._histories.setdefault(
                track_id, deque(maxlen=self.history_size))
            history.append(_KeyFrame(now, keypoints, bbox))
            self._last_seen[track_id] = now

            raw = self._classify(keypoints, history, main_posture, duration)
            track["activity"] = self._confirm(track_id, raw)

        self._expire(now)

    # ─── Hysteresis / confirmation ───

    def _dominant_posture(self, postures: Deque[str]) -> str:
        if not postures:
            return "unknown"
        return Counter(postures).most_common(1)[0][0]

    def _confirm(self, track_id: int, raw: str) -> str:
        """Return the confirmed activity with hysteresis (counter-based).

        Switching to a new activity requires ``confirm_frames`` *consecutive*
        frames of the new raw label; until then the previous activity is
        kept.  The default 5 frames (~0.17 s at 30 fps) absorbs both
        single-frame flickers and short noise runs (e.g. 2-4 frames of
        standing while the person is still holding the phone), while real
        transitions (person stops the activity) still switch quickly.
        """
        active = self._active_activity.get(track_id, "unknown")
        if raw == active:
            self._pending.pop(track_id, None)
            return active

        run = self._pending.setdefault(track_id, 0)
        run = run + 1 if raw == self._last_raw.get(track_id) else 1
        self._pending[track_id] = run
        self._last_raw[track_id] = raw
        if run >= self.confirm_frames:
            self._active_activity[track_id] = raw
            self._pending.pop(track_id, None)
            self._last_raw.pop(track_id, None)
            return raw
        return active

    # ─── Classification ───

    def _classify(
        self,
        keypoints: List[List[float]],
        history: Deque[_KeyFrame],
        posture: str,
        duration: float,
    ) -> str:
        """Return the raw (unconfirmed) activity label for one track."""
        if not keypoints or len(keypoints) < 17:
            return "unknown"

        # Walking (ankle alternation over short history)
        if self._is_walking(history):
            return "walking"
        # Eating (hand-to-mouth oscillation over longer history)
        if self._is_eating(history):
            return "eating"
        # Playing phone (current-frame geometry)
        if self._is_playing_phone(keypoints):
            return "playing_phone"
        # Sleeping (lying + long duration)
        if self._is_sleeping(posture, duration):
            return "sleeping"
        # Sitting / standing (smoothed posture + held duration)
        if posture in ("sitting", "standing") and duration >= _STATIC_MIN_DURATION:
            return posture
        if posture == "lying":
            return "lying"

        return "unknown"

    # ─── Detection helpers ───

    @staticmethod
    def _is_playing_phone(keypoints: List[List[float]]) -> bool:
        """Detect phone playing: wrist near ear + bent elbow + head down."""
        nose = _kp(keypoints, NOSE)
        left_ear = _kp(keypoints, LEFT_EAR)
        right_ear = _kp(keypoints, RIGHT_EAR)
        left_elbow = _kp(keypoints, LEFT_ELBOW)
        right_elbow = _kp(keypoints, RIGHT_ELBOW)
        left_wrist = _kp(keypoints, LEFT_WRIST)
        right_wrist = _kp(keypoints, RIGHT_WRIST)

        if nose is None:
            return False

        # Head slightly down: nose y > ear y by a margin
        ear_y = (left_ear[1] if left_ear else 1.0) if right_ear is None else (
            (left_ear[1] + right_ear[1]) / 2 if left_ear else right_ear[1]
        )
        head_down = nose[1] > ear_y + 0.03

        # Check left hand near ear
        left_near = False
        if left_wrist is not None and left_ear is not None:
            left_near = _distance(left_wrist, left_ear) < _WRIST_EAR_DIST
            if left_near and left_elbow is not None:
                angle = _elbow_angle(left_ear, left_elbow, left_wrist)
                if angle is not None and angle > _ELBOW_BENT_ANGLE_DEG:
                    left_near = False  # arm not bent enough

        # Check right hand near ear
        right_near = False
        if right_wrist is not None and right_ear is not None:
            right_near = _distance(right_wrist, right_ear) < _WRIST_EAR_DIST
            if right_near and right_elbow is not None:
                angle = _elbow_angle(right_ear, right_elbow, right_wrist)
                if angle is not None and angle > _ELBOW_BENT_ANGLE_DEG:
                    right_near = False

        return (left_near or right_near) and head_down

    @staticmethod
    def _is_eating(history: Deque[_KeyFrame]) -> bool:
        """Detect eating: repetitive hand-to-mouth motion over recent frames."""
        if len(history) < 10:
            return False

        frames = list(history)[-24:]  # look back up to 24 frames
        distances: List[float] = []
        for frame in frames:
            kp = frame.keypoints
            if not kp or len(kp) < 17:
                continue
            nose_pt = _kp(kp, NOSE)
            if nose_pt is None:
                continue
            # Pick the wrist closer to the nose
            lw = _kp(kp, LEFT_WRIST)
            rw = _kp(kp, RIGHT_WRIST)
            d = 1.0
            if lw is not None:
                d = min(d, _distance(nose_pt, lw))
            if rw is not None:
                d = min(d, _distance(nose_pt, rw))
            distances.append(d)

        if len(distances) < 8:
            return False

        # Count approach-withdraw cycles
        below = False
        cycles = 0
        for d in distances:
            if not below and d < _EAT_APPROACH_DIST:
                below = True
            elif below and d > _EAT_WITHDRAW_DIST:
                below = False
                cycles += 1

        return cycles >= _EAT_MIN_CYCLES

    @staticmethod
    def _is_walking(history: Deque[_KeyFrame]) -> bool:
        """Detect walking: alternating ankle positions over recent frames."""
        if len(history) < 8:
            return False

        frames = list(history)[-15:]
        left_ankles = []
        right_ankles = []
        for frame in frames:
            kp = frame.keypoints
            if not kp or len(kp) < 17:
                continue
            la = _kp(kp, LEFT_ANKLE)
            ra = _kp(kp, RIGHT_ANKLE)
            if la is not None:
                left_ankles.append(la[0])  # x-coordinate
            if ra is not None:
                right_ankles.append(ra[0])

        if len(left_ankles) < 4 or len(right_ankles) < 4:
            return False

        # Walking: both ankle x-positions alternate over time
        def _alternation(values: List[float]) -> bool:
            diffs = [v - values[i - 1] for i, v in enumerate(values) if i > 0]
            direction_changes = sum(
                1 for left, right in zip(diffs, diffs[1:])
                if left * right < 0
            )
            return direction_changes >= 2 and max(abs(d) for d in diffs) > _WALK_ANKLE_SPREAD

        left_walk = _alternation(left_ankles)
        right_walk = _alternation(right_ankles)
        return left_walk or right_walk

    @staticmethod
    def _is_sleeping(posture: str, duration: float) -> bool:
        """Detect sleeping: lying posture + long duration."""
        return posture in ("lying", "lying_edge") and duration >= _SLEEP_MIN_DURATION

    def _expire(self, now: float) -> None:
        for track_id, last_seen in list(self._last_seen.items()):
            if now - last_seen > self.track_ttl_seconds:
                self._last_seen.pop(track_id, None)
                self._histories.pop(track_id, None)
                self._posture_history.pop(track_id, None)
                self._active_activity.pop(track_id, None)
                self._pending.pop(track_id, None)
                self._last_raw.pop(track_id, None)
                self._main_posture.pop(track_id, None)
                self._posture_since.pop(track_id, None)

    def reset(self) -> None:
        self._histories.clear()
        self._posture_history.clear()
        self._last_seen.clear()
        self._active_activity.clear()
        self._pending.clear()
        self._last_raw.clear()
        self._main_posture.clear()
        self._posture_since.clear()
