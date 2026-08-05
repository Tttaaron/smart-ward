"""Tests for continuous-frame behavior analysis."""

import os
import sys
import unittest

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from behavior import BehaviorAnalyzer, estimate_posture


class BehaviorAnalyzerTest(unittest.TestCase):
    def test_estimates_posture_from_bbox(self):
        self.assertEqual(estimate_posture([0.2, 0.1, 0.1, 0.5]), "standing")
        self.assertEqual(estimate_posture([0.2, 0.5, 0.5, 0.15]), "lying")

    def test_detects_upright_to_lying_transition(self):
        analyzer = BehaviorAnalyzer(history_size=8)
        first = analyzer.update(
            [{"track_id": 1, "bbox": [0.4, 0.1, 0.1, 0.55], "confidence": 0.95}],
            timestamp="2026-08-02T08:30:00Z",
        )
        self.assertEqual(first["posture"], "standing")

        second = analyzer.update(
            [{"track_id": 1, "bbox": [0.3, 0.55, 0.45, 0.16], "confidence": 0.94}],
            timestamp="2026-08-02T08:30:01Z",
        )
        self.assertEqual(second["action"], "suspected_fall")
        self.assertGreaterEqual(second["fall_score"], 0.6)
        self.assertEqual(second["posture_sequence"], ["standing", "lying"])
        self.assertEqual(second["track_id"], 1)

    def test_tracks_position_duration(self):
        analyzer = BehaviorAnalyzer(history_size=8)
        bbox = [0.4, 0.1, 0.1, 0.55]
        analyzer.update([{"track_id": 1, "bbox": bbox}], timestamp="2026-08-02T08:30:00Z")
        result = analyzer.update([{"track_id": 1, "bbox": bbox}], timestamp="2026-08-02T08:30:03Z")
        self.assertEqual(result["posture"], "standing")
        self.assertAlmostEqual(result["position_duration"], 3.0, places=2)

    def test_empty_frame_reports_no_active_person(self):
        analyzer = BehaviorAnalyzer()
        result = analyzer.update([], timestamp="2026-08-02T08:30:00Z")
        self.assertFalse(result["active"])
        self.assertEqual(result["action"], "none")


if __name__ == "__main__":
    unittest.main()

