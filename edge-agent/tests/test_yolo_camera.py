"""Tests for parsing YOLO results without installing the optional backend."""

import os
import sys
import unittest

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from adapters.yolo_camera import build_activity_entry, parse_yolo_result


class _Tensor:
    def __init__(self, value):
        self.value = value

    def tolist(self):
        return self.value


class _Boxes:
    xyxy = _Tensor([[10, 20, 50, 100], [1, 2, 20, 20]])
    conf = _Tensor([0.95, 0.99])
    cls = _Tensor([0, 1])
    id = None


class _Keypoints:
    xy = _Tensor([[[20, 30], [30, 60]], []])
    conf = _Tensor([[0.9, 0.8], []])


class _Result:
    boxes = _Boxes()
    keypoints = _Keypoints()
    names = {0: "person", 1: "bed"}


class YoloResultParserTest(unittest.TestCase):
    def test_keeps_only_person_and_normalizes_coordinates(self):
        detections = parse_yolo_result(_Result(), frame_width=100, frame_height=200)
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]["class"], "person")
        self.assertEqual(detections[0]["bbox"], [0.1, 0.1, 0.4, 0.4])
        self.assertEqual(detections[0]["keypoints"][0], [0.2, 0.15, 0.9])


class BuildActivityEntryTest(unittest.TestCase):
    def test_first_non_unknown_activity_is_primary(self):
        tracked = [
            {"track_id": 1, "activity": "unknown"},
            {"track_id": 2, "activity": "sleeping"},
        ]
        entry, last, since = build_activity_entry(tracked, None, 10.0, 20.0)
        self.assertEqual(entry["label"], "sleeping")
        # 首次确认活动也视为切换事件（前端记录"活动开始"）
        self.assertTrue(entry["switched"])
        self.assertIsNone(entry["previous"])
        self.assertEqual(last, "sleeping")
        self.assertEqual(since, 20.0)

    def test_activity_switch_marks_switched_and_updates_since(self):
        tracked = [{"track_id": 1, "activity": "sitting"}]
        entry, last, since = build_activity_entry(tracked, "sleeping", 10.0, 42.0)
        self.assertEqual(entry["label"], "sitting")
        self.assertTrue(entry["switched"])
        self.assertEqual(entry["previous"], "sleeping")
        self.assertEqual(last, "sitting")
        self.assertEqual(since, 42.0)  # 切换时 since 更新为 now

    def test_all_unknown_falls_back_to_unknown(self):
        tracked = [{"track_id": 1, "activity": "unknown"}]
        entry, last, since = build_activity_entry(tracked, "sleeping", 5.0, 9.0)
        self.assertEqual(entry["label"], "unknown")
        self.assertFalse(entry["switched"])
        self.assertEqual(last, "sleeping")
        self.assertEqual(since, 5.0)


if __name__ == "__main__":
    unittest.main()

