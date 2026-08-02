"""Activity tracker unit tests.

Run with::

    python -m unittest discover edge-agent/tests -v
    # or directly:
    python edge-agent/tests/test_activity_tracker.py
"""
import os
import sys
import unittest

SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "src")
SRC_DIR = os.path.abspath(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from activity_tracker import (
    ActivityRecognizer,
    _distance,
    _elbow_angle,
    _kp,
)


def _make_kps(*points) -> list:
    """Build a 17-keypoint list.  Each point is ``(index, x, y, conf)``."""
    kps = [[0.0, 0.0, 0.0] for _ in range(17)]
    for idx, x, y, conf in points:
        if isinstance(idx, int) and 0 <= idx < 17:
            kps[idx] = [float(x), float(y), float(conf)]
    return kps


def _make_track(track_id: int, keypoints: list, bbox: list = None,
                posture: str = "unknown") -> dict:
    if bbox is None:
        bbox = [0.3, 0.3, 0.2, 0.5]
    return {
        "track_id": track_id,
        "pose_keypoints": keypoints,
        "bbox": bbox,
        "posture": posture,
    }


class TestHelpers(unittest.TestCase):
    """Low-level geometry and keypoint helpers."""

    def test_distance(self):
        self.assertAlmostEqual(_distance([0, 0], [3, 4]), 5.0)
        self.assertAlmostEqual(_distance([0, 0], [0, 0]), 0.0)

    def test_elbow_angle_straight(self):
        # shoulder(0,0) → elbow(0,1) → wrist(0,2) → straight arm → 180°
        angle = _elbow_angle([0, 0], [0, 1], [0, 2])
        self.assertIsNotNone(angle)
        self.assertAlmostEqual(angle, 180.0, delta=0.5)

    def test_elbow_angle_right_angle(self):
        # shoulder(0,0) → elbow(0,1) → wrist(1,1) → 90°
        angle = _elbow_angle([0, 0], [0, 1], [1, 1])
        self.assertIsNotNone(angle)
        self.assertAlmostEqual(angle, 90.0, delta=0.5)

    def test_kp_valid(self):
        kps = _make_kps((0, 0, 0, 1.0))  # nose with high confidence
        pt = _kp(kps, 0)
        self.assertIsNotNone(pt)
        self.assertAlmostEqual(pt[0], 0.0)

    def test_kp_low_confidence(self):
        kps = _make_kps((0, 0, 0, 0.1))  # below threshold
        pt = _kp(kps, 0)
        self.assertIsNone(pt)


class TestPlayPhoneDetection(unittest.TestCase):
    """Playing phone: wrist near ear + bent elbow + head down."""

    def test_phone_left_hand(self):
        """Left hand near left ear, arm bent, head down."""
        # Nose(0.5, 0.6), left ear(0.45, 0.55), left shoulder(0.45, 0.65)
        # left elbow(0.42, 0.60), left wrist(0.44, 0.54) → near ear
        kps = _make_kps(
            (0, 0.50, 0.60, 0.95),   # nose
            (1, 0.48, 0.58, 0.90),   # left_eye
            (2, 0.52, 0.58, 0.90),   # right_eye
            (3, 0.45, 0.55, 0.90),   # left_ear
            (4, 0.55, 0.55, 0.90),   # right_ear
            (5, 0.45, 0.65, 0.95),   # left_shoulder
            (6, 0.55, 0.65, 0.95),   # right_shoulder
            (7, 0.42, 0.60, 0.90),   # left_elbow
            (8, 0.58, 0.60, 0.90),   # right_elbow
            (9, 0.44, 0.54, 0.90),   # left_wrist → near ear (0.45,0.55)
            (10, 0.60, 0.50, 0.90),  # right_wrist
            (11, 0.43, 0.78, 0.95),  # left_hip
            (12, 0.57, 0.78, 0.95),  # right_hip
            (13, 0.42, 0.88, 0.90),  # left_knee
            (14, 0.58, 0.88, 0.90),  # right_knee
            (15, 0.41, 0.95, 0.90),  # left_ankle
            (16, 0.59, 0.95, 0.90),  # right_ankle
        )
        self.assertTrue(ActivityRecognizer._is_playing_phone(kps))

    def test_phone_right_hand(self):
        """Right hand near right ear."""
        kps = _make_kps(
            (0, 0.50, 0.60, 0.95),
            (3, 0.44, 0.54, 0.90),
            (4, 0.56, 0.54, 0.90),
            (5, 0.44, 0.65, 0.95),
            (6, 0.56, 0.65, 0.95),
            (7, 0.42, 0.59, 0.90),
            (8, 0.58, 0.59, 0.90),
            (9, 0.44, 0.52, 0.90),  # left wrist
            (10, 0.56, 0.53, 0.90),  # right wrist → near right ear
            (11, 0.43, 0.78, 0.95),
            (12, 0.57, 0.78, 0.95),
        )
        self.assertTrue(ActivityRecognizer._is_playing_phone(kps))

    def test_not_phone_arms_down(self):
        """Arms naturally down → not playing phone."""
        kps = _make_kps(
            (0, 0.50, 0.30, 0.95),   # nose high → not head down
            (3, 0.45, 0.28, 0.90),   # left_ear
            (4, 0.55, 0.28, 0.90),
            (5, 0.45, 0.40, 0.95),
            (6, 0.55, 0.40, 0.95),
            (7, 0.44, 0.55, 0.90),   # left_elbow low
            (8, 0.56, 0.55, 0.90),
            (9, 0.43, 0.70, 0.90),   # left_wrist far from ear
            (10, 0.57, 0.70, 0.90),  # right_wrist far from ear
        )
        self.assertFalse(ActivityRecognizer._is_playing_phone(kps))


class TestEatingDetection(unittest.TestCase):
    """Eating: repetitive hand-to-mouth motion."""

    def test_eating_cycles(self):
        """Simulate approach-withdraw cycles → eating."""
        import time
        recognizer = ActivityRecognizer()
        tracks = [_make_track(1, _make_kps((0, 0.5, 0.5, 0.9)))]
        # Alternate wrist positions to simulate eating motion
        start = time.time()
        for i in range(30):
            t = start + i * 0.1
            # Cycle wrist between near mouth (0.51, 0.47) and far (0.72, 0.52)
            cycle_pos = "near" if (i % 6) < 3 else "far"
            wx = 0.51 if cycle_pos == "near" else 0.72
            wy = 0.47 if cycle_pos == "near" else 0.52
            kps = _make_kps(
                (0, 0.50, 0.50, 0.95),
                (3, 0.47, 0.47, 0.90),
                (4, 0.53, 0.47, 0.90),
                (5, 0.47, 0.60, 0.95),
                (6, 0.53, 0.60, 0.95),
                (7, 0.45, 0.58, 0.90),
                (8, 0.55, 0.58, 0.90),
                (9, wx, wy, 0.90),
                (10, wx + 0.02, wy, 0.90),
            )
            track = _make_track(1, kps)
            recognizer.update([track], timestamp=t)
            last_track = track  # keep reference for assertion below
        # After enough cycles, activity should be eating
        self.assertEqual(last_track.get("activity"), "eating")


class TestWalkingDetection(unittest.TestCase):
    """Walking: alternating ankle motion."""

    def test_walking_ankles(self):
        import time
        recognizer = ActivityRecognizer()
        start = time.time()
        for i in range(15):
            t = start + i * 0.1
            # Alternate ankle x-positions
            offset = 0.03 if (i % 2) == 0 else -0.03
            kps = _make_kps(
                (0, 0.50, 0.30, 0.95),
                (5, 0.45, 0.40, 0.95),
                (6, 0.55, 0.40, 0.95),
                (11, 0.44, 0.65, 0.95),
                (12, 0.56, 0.65, 0.95),
                (13, 0.43, 0.78, 0.90),
                (14, 0.57, 0.78, 0.90),
                (15, 0.42 + offset, 0.92, 0.90),
                (16, 0.58 + offset, 0.92, 0.90),
            )
            track = _make_track(1, kps)
            recognizer.update([track], timestamp=t)
        self.assertEqual(track.get("activity"), "walking")


class TestDefaultUnknown(unittest.TestCase):
    """Default state for low-confidence / no keypoints."""

    def test_no_keypoints(self):
        recognizer = ActivityRecognizer()
        track = _make_track(1, [], bbox=[0.3, 0.3, 0.2, 0.5])
        recognizer.update([track])
        self.assertEqual(track.get("activity"), "unknown")

    def test_low_conf_keypoints(self):
        recognizer = ActivityRecognizer()
        kps = [[0.0, 0.0, 0.01] for _ in range(17)]
        track = _make_track(1, kps)
        recognizer.update([track])
        self.assertEqual(track.get("activity"), "unknown")


class TestHysteresis(unittest.TestCase):
    """Activity labels require consecutive frames (anti-flicker)."""

    @staticmethod
    def _static_kps() -> list:
        """Arms-down standing skeleton; never triggers phone/eat/walk."""
        return _make_kps(
            (0, 0.50, 0.30, 0.95),
            (3, 0.45, 0.28, 0.90),
            (4, 0.55, 0.28, 0.90),
            (5, 0.45, 0.40, 0.95),
            (6, 0.55, 0.40, 0.95),
            (7, 0.44, 0.55, 0.90),
            (8, 0.56, 0.55, 0.90),
            (9, 0.43, 0.70, 0.90),
            (10, 0.57, 0.70, 0.90),
            (11, 0.43, 0.78, 0.95),
            (12, 0.57, 0.78, 0.95),
            (13, 0.42, 0.88, 0.90),
            (14, 0.58, 0.88, 0.90),
            (15, 0.41, 0.95, 0.90),
            (16, 0.59, 0.95, 0.90),
        )

    @staticmethod
    def _phone_kps() -> list:
        """Head-down, hand-to-ear skeleton (playing phone)."""
        return _make_kps(
            (0, 0.50, 0.60, 0.95),
            (1, 0.48, 0.58, 0.90),
            (2, 0.52, 0.58, 0.90),
            (3, 0.45, 0.55, 0.90),
            (4, 0.55, 0.55, 0.90),
            (5, 0.45, 0.65, 0.95),
            (6, 0.55, 0.65, 0.95),
            (7, 0.42, 0.60, 0.90),
            (8, 0.58, 0.60, 0.90),
            (9, 0.44, 0.54, 0.90),
            (10, 0.60, 0.50, 0.90),
            (11, 0.43, 0.78, 0.95),
            (12, 0.57, 0.78, 0.95),
            (13, 0.42, 0.88, 0.90),
            (14, 0.58, 0.88, 0.90),
            (15, 0.41, 0.95, 0.90),
            (16, 0.59, 0.95, 0.90),
        )

    def test_phone_single_frame_not_sticky(self):
        """A 1-frame playing_phone blip must not override standing."""
        import time
        recognizer = ActivityRecognizer()
        start = time.time()
        track = None
        # Establish standing first (6 s of static posture)
        for i in range(60):
            track = _make_track(1, self._static_kps(), posture="standing")
            recognizer.update([track], timestamp=start + i * 0.1)
        self.assertEqual(track.get("activity"), "standing")

        # One phone frame in the middle of standing frames
        phone_track = _make_track(1, self._phone_kps(), posture="standing")
        recognizer.update([phone_track], timestamp=start + 6.1)
        self.assertEqual(phone_track.get("activity"), "standing")  # not confirmed

        for i in range(10):
            track = _make_track(1, self._static_kps(), posture="standing")
            recognizer.update([track], timestamp=start + 6.2 + i * 0.1)
        self.assertEqual(track.get("activity"), "standing")

    def test_phone_confirmed_after_consecutive_frames(self):
        """playing_phone becomes active only after confirm_frames frames."""
        import time
        recognizer = ActivityRecognizer()
        start = time.time()
        track = None
        for i in range(6):
            track = _make_track(1, self._phone_kps(), posture="standing")
            recognizer.update([track], timestamp=start + i * 0.1)
        self.assertEqual(track.get("activity"), "playing_phone")

    def test_walking_confirmed_then_reverts(self):
        """Walking is confirmed while present, then reverts after it stops."""
        import time
        recognizer = ActivityRecognizer()
        start = time.time()
        walking_kps = _make_kps(
            (0, 0.50, 0.30, 0.95),
            (5, 0.45, 0.40, 0.95),
            (6, 0.55, 0.40, 0.95),
            (11, 0.44, 0.65, 0.95),
            (12, 0.56, 0.65, 0.95),
            (13, 0.43, 0.78, 0.90),
            (14, 0.57, 0.78, 0.90),
            (15, 0.42, 0.92, 0.90),
            (16, 0.58, 0.92, 0.90),
        )
        track = None
        for i in range(12):
            offset = 0.03 if i % 2 == 0 else -0.03
            kps = _make_kps(
                (0, 0.50, 0.30, 0.95),
                (5, 0.45, 0.40, 0.95),
                (6, 0.55, 0.40, 0.95),
                (11, 0.44, 0.65, 0.95),
                (12, 0.56, 0.65, 0.95),
                (13, 0.43, 0.78, 0.90),
                (14, 0.57, 0.78, 0.90),
                (15, 0.42 + offset, 0.92, 0.90),
                (16, 0.58 + offset, 0.92, 0.90),
            )
            track = _make_track(1, kps, posture="standing")
            recognizer.update([track], timestamp=start + i * 0.1)
        self.assertEqual(track.get("activity"), "walking")

        # Walking stops → the 15-frame alternation window flushes, then
        # standing is re-confirmed once the posture duration reaches 5 s.
        for i in range(45):
            track = _make_track(1, walking_kps, posture="standing")
            recognizer.update([track], timestamp=start + 1.3 + i * 0.1)
        self.assertEqual(track.get("activity"), "standing")


class TestPostureDuration(unittest.TestCase):
    """Sitting/standing need the smoothed posture held long enough."""

    def test_standing_after_duration(self):
        """standing is confirmed once the posture is held ≥ 5 s."""
        import time
        recognizer = ActivityRecognizer()
        start = time.time()
        static_kps = _make_kps(
            (0, 0.50, 0.30, 0.95),
            (3, 0.45, 0.28, 0.90),
            (4, 0.55, 0.28, 0.90),
            (5, 0.45, 0.40, 0.95),
            (6, 0.55, 0.40, 0.95),
            (7, 0.44, 0.55, 0.90),
            (8, 0.56, 0.55, 0.90),
            (9, 0.43, 0.70, 0.90),
            (10, 0.57, 0.70, 0.90),
            (11, 0.43, 0.78, 0.95),
            (12, 0.57, 0.78, 0.95),
            (13, 0.42, 0.88, 0.90),
            (14, 0.58, 0.88, 0.90),
            (15, 0.41, 0.95, 0.90),
            (16, 0.59, 0.95, 0.90),
        )
        track = None
        # 60 frames at 0.1 s each = 6 s of standing posture
        for i in range(60):
            track = _make_track(1, static_kps, posture="standing")
            recognizer.update([track], timestamp=start + i * 0.1)
        self.assertEqual(track.get("activity"), "standing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
