"""Tests for the dependency-free person tracker."""

import os
import sys
import unittest

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tracking import IoUTracker, bbox_iou


class IoUTrackerTest(unittest.TestCase):
    def test_bbox_iou(self):
        self.assertAlmostEqual(bbox_iou([0, 0, 1, 1], [0.5, 0.5, 1, 1]), 1 / 7, places=5)

    def test_keeps_id_for_overlapping_detection(self):
        tracker = IoUTracker(iou_threshold=0.2)
        first = tracker.update([{"bbox": [0.2, 0.2, 0.2, 0.4], "confidence": 0.9}])
        second = tracker.update([{"bbox": [0.21, 0.21, 0.2, 0.4], "confidence": 0.92}])
        self.assertEqual(first[0]["track_id"], second[0]["track_id"])

    def test_assigns_new_id_and_expires_missing_track(self):
        tracker = IoUTracker(iou_threshold=0.5, max_missed=0)
        first = tracker.update([{"bbox": [0.1, 0.1, 0.1, 0.2]}])
        second = tracker.update([{"bbox": [0.8, 0.1, 0.1, 0.2]}])
        self.assertNotEqual(first[0]["track_id"], second[0]["track_id"])
        tracker.update([])
        third = tracker.update([{"bbox": [0.1, 0.1, 0.1, 0.2]}])
        self.assertNotEqual(first[0]["track_id"], third[0]["track_id"])


if __name__ == "__main__":
    unittest.main()

