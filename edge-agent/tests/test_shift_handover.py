"""边缘交接班小 agent 测试：窗口计算 / mock 生成 / 病人档案 / 存储回读"""

import json
import os
import sys
import tempfile
import unittest

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from llm_advisor import LLMAdvisor, compute_shift_window  # noqa: E402
from database import LocalDatabase  # noqa: E402

PATIENTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "patients.json"))


def make_event(event_id, event_type, priority, confidence, occurred_at, details=None):
    return {
        "event_id": event_id, "ward_id": "W-01", "node_id": "EDGE-W01-B02",
        "bed_id": "B02", "event_type": event_type, "priority": priority,
        "confidence": confidence, "occurred_at": occurred_at,
        "details": details or {},
    }


class ShiftWindowTest(unittest.TestCase):
    def test_day_window(self):
        start, end = compute_shift_window("2026-08-19", "day")
        self.assertEqual(start, "2026-08-19T00:00:00Z")
        self.assertEqual(end, "2026-08-19T08:00:00Z")

    def test_evening_window(self):
        start, end = compute_shift_window("2026-08-19", "evening")
        self.assertEqual(start, "2026-08-19T08:00:00Z")
        self.assertEqual(end, "2026-08-19T16:00:00Z")

    def test_night_window_crosses_utc_day(self):
        start, end = compute_shift_window("2026-08-19", "night")
        self.assertEqual(start, "2026-08-18T16:00:00Z")
        self.assertEqual(end, "2026-08-19T00:00:00Z")


class PatientsConfigTest(unittest.TestCase):
    def test_patients_json_loadable(self):
        with open(PATIENTS, encoding="utf-8") as f:
            patients = json.load(f)
        self.assertIn("B01", patients)
        self.assertTrue(patients["B01"]["fall_risk"])
        self.assertEqual(patients["B01"]["name"], "张阿姨")


class MockHandoverTest(unittest.TestCase):
    def setUp(self):
        self.advisor = LLMAdvisor("EDGE-W01-B02", "B02", "W-01")
        self.patient = {"name": "李伯伯", "age": 72, "nursing_level": "二级护理",
                        "diagnosis": "髋部骨折术后", "fall_risk": True, "bedsore_risk": True}

    def test_handover_contains_time_and_event(self):
        events = [
            make_event("E1", "fall_prediction", "P1", 0.7, "2026-08-19T01:20:00Z",
                       details={"posture": "lying_edge", "fall_score": 0.7}),
            make_event("E2", "long_still", "P2", 0.75, "2026-08-19T02:05:00Z",
                       details={"position_duration": 360}),
        ]
        ho = self.advisor.generate_shift_handover(
            self.patient, events, "2026-08-19", "day",
            window_start="2026-08-19T00:00:00Z", window_end="2026-08-19T08:00:00Z")
        self.assertEqual(ho.event_count, 2)
        self.assertEqual(ho.p1_count, 1)
        self.assertEqual(ho.mode, "mock")
        self.assertIn("坠床预警", ho.handover_text)
        self.assertIn("长时间静止", ho.handover_text)
        self.assertIn("09:20", ho.handover_text)  # 01:20 UTC -> 09:20 本地
        self.assertIn("李伯伯", ho.handover_text)

    def test_empty_handover(self):
        ho = self.advisor.generate_shift_handover(self.patient, [], "2026-08-19", "day")
        self.assertEqual(ho.event_count, 0)
        self.assertIn("未检测到安全事件", ho.handover_text)


class ShiftHandoverStorageTest(unittest.TestCase):
    def test_save_and_list_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = LocalDatabase(os.path.join(tmp, "edge_test.db"))
            record = {
                "node_id": "EDGE-W01-B01", "bed_id": "B01",
                "shift_date": "2026-08-19", "shift_period": "day",
                "window_start": "2026-08-19T00:00:00Z", "window_end": "2026-08-19T08:00:00Z",
                "event_count": 3, "p1_count": 1,
                "patient": {"name": "张阿姨"}, "handover_text": "# 测试交接班",
                "mode": "mock",
                "generated_at": "2026-08-19T09:00:00Z",
            }
            db.save_shift_handover(record)
            db.save_shift_handover(record)  # 幂等覆盖，不应产生重复行
            rows = db.list_shift_handovers(bed_id="B01")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["handover_text"], "# 测试交接班")
            self.assertEqual(rows[0]["event_count"], 3)


if __name__ == "__main__":
    unittest.main()
