"""Tests for parsing YOLO results without installing the optional backend."""

import os
import sys
import unittest

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from adapters.yolo_camera import parse_yolo_result


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


if __name__ == "__main__":
    unittest.main()

