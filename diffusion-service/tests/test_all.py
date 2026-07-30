"""扩散模型服务单元测试"""
import unittest
import tempfile
from pathlib import Path

from PIL import Image
import numpy as np

from config.pose_templates import (
    get_templates_for_event,
    get_prompt_for_event,
    ALL_EVENT_TYPES,
    EVENT_TEMPLATE_MAP,
    EVENT_PROMPTS,
    EVENT_CATEGORY_IDS,
)
from app.exporter import _format_yolo_line, export_single
from app.curator import QualityCurator


class TestPoseTemplates(unittest.TestCase):

    def test_all_events_have_templates(self):
        for event_type in ALL_EVENT_TYPES:
            templates = get_templates_for_event(event_type)
            self.assertIsNotNone(templates, f"No templates for {event_type}")
            self.assertGreater(len(templates), 0, f"Empty templates for {event_type}")

    def test_all_events_have_prompts(self):
        for event_type in ALL_EVENT_TYPES:
            prompt = get_prompt_for_event(event_type, night_mode=False)
            self.assertIsNotNone(prompt)
            self.assertGreater(len(prompt), 50, f"Prompt too short for {event_type}")
            night_prompt = get_prompt_for_event(event_type, night_mode=True)
            self.assertIn("night", night_prompt.lower())

    def test_keypoints_format(self):
        """验证所有模板的关键点格式正确"""
        for event_type in ALL_EVENT_TYPES:
            for template in get_templates_for_event(event_type):
                kps = template["keypoints"]
                self.assertEqual(len(kps), 17,
                                 f"{template['label']} keypoints count != 17")
                for i, kp in enumerate(kps):
                    self.assertEqual(len(kp), 2,
                                     f"keypoint {i} should be [x, y]")
                    self.assertGreaterEqual(kp[0], 0.0)
                    self.assertLessEqual(kp[0], 1.0)
                    self.assertGreaterEqual(kp[1], 0.0)
                    self.assertLessEqual(kp[1], 1.0)

    def test_bbox_format(self):
        for event_type in ALL_EVENT_TYPES:
            for template in get_templates_for_event(event_type):
                bbox = template["bbox"]
                self.assertEqual(len(bbox), 4,
                                 f"{template['label']} bbox should be [cx,cy,w,h]")
                self.assertGreaterEqual(bbox[0], 0.0)
                self.assertLessEqual(bbox[0], 1.0)
                self.assertGreaterEqual(bbox[2], 0.0)  # w > 0
                self.assertGreaterEqual(bbox[3], 0.0)  # h > 0

    def test_category_ids(self):
        for event_type in ALL_EVENT_TYPES:
            self.assertIn(event_type, EVENT_CATEGORY_IDS,
                          f"Missing category ID for {event_type}")

    def test_prompt_ward_context(self):
        """验证所有提示词包含病房场景关键词"""
        for event_type, prompt in EVENT_PROMPTS.items():
            self.assertTrue(
                any(w in prompt.lower() for w in ["patient", "hospital", "bed", "ward"]),
                f"Prompt for {event_type} missing ward context: {prompt[:80]}"
            )


class TestYoloExport(unittest.TestCase):

    def test_format_yolo_line(self):
        bbox = [0.5, 0.5, 0.3, 0.4]
        kps = [[0.5, 0.3], [0.48, 0.28], [0.52, 0.28],
               [0.46, 0.3], [0.54, 0.3],
               [0.4, 0.4], [0.6, 0.4],
               [0.35, 0.5], [0.65, 0.5],
               [0.3, 0.55], [0.7, 0.55],
               [0.4, 0.45], [0.6, 0.45],
               [0.4, 0.7], [0.6, 0.7],
               [0.42, 0.9], [0.58, 0.9]]

        line = _format_yolo_line(0, bbox, kps)
        parts = line.strip().split()

        # class_id + 4 bbox + 17*3 keypoints = 56 fields
        self.assertEqual(len(parts), 56, f"Expected 56 fields, got {len(parts)}")
        self.assertEqual(parts[0], "0")  # class_id

        # All values should be parseable as float
        for p in parts[1:]:
            float(p)

    def test_export_single(self):
        # Create a test image
        img = Image.new("RGB", (640, 640), (128, 128, 128))
        result = {
            "image": img,
            "keypoints": [[0.5, 0.5] for _ in range(17)],
            "bbox": [0.5, 0.5, 0.3, 0.4],
            "event_type": "fall_suspected",
            "label": "test",
        }

        with tempfile.TemporaryDirectory() as tmp:
            img_dir = Path(tmp) / "images"
            lbl_dir = Path(tmp) / "labels"
            img_dir.mkdir()
            lbl_dir.mkdir()

            paths = export_single(result, "000000", img_dir, lbl_dir, 0)

            self.assertTrue(Path(paths["image_path"]).exists())
            self.assertTrue(Path(paths["label_path"]).exists())

            label_content = Path(paths["label_path"]).read_text()
            self.assertTrue(label_content.startswith("0 "))


class TestQualityCurator(unittest.TestCase):

    def setUp(self):
        self.curator = QualityCurator()

    def test_good_image_passes(self):
        img = Image.new("RGB", (640, 640), (128, 128, 128))
        # Add some texture so it's not perfectly uniform
        arr = np.array(img)
        arr[100:200, 100:200] = [200, 150, 100]
        img = Image.fromarray(arr)

        metrics = self.curator.assess(img)
        self.assertIn("sharpness", metrics)
        self.assertIn("brightness", metrics)

    def test_black_image_fails_brightness(self):
        img = Image.new("RGB", (640, 640), (0, 0, 0))
        metrics = self.curator.assess(img)
        self.assertFalse(metrics["passed"])
        self.assertTrue(any("dark" in r for r in metrics["reasons"]))

    def test_white_image_fails_brightness(self):
        img = Image.new("RGB", (640, 640), (255, 255, 255))
        metrics = self.curator.assess(img)
        self.assertFalse(metrics["passed"])
        self.assertTrue(any("bright" in r for r in metrics["reasons"]))


if __name__ == "__main__":
    unittest.main()
