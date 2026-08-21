"""边缘 agent 能力测试：活动播报 / 时段摘要 / 问答 / 交接班闭环跟踪 / 统计 / 趋势"""

import json
import os
import sys
import tempfile
import unittest

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from llm_advisor import LLMAdvisor  # noqa: E402
from database import LocalDatabase  # noqa: E402
from ask_ward_agent import detect_event_types, detect_bed  # noqa: E402

PATIENT = {"name": "李伯伯", "age": 72, "nursing_level": "二级护理",
           "diagnosis": "髋部骨折术后", "fall_risk": True, "bedsore_risk": True}


def make_event(event_id, event_type, priority, confidence, occurred_at, details=None):
    return {
        "event_id": event_id, "ward_id": "W-01", "node_id": "EDGE-W01-B02",
        "bed_id": "B02", "event_type": event_type, "priority": priority,
        "confidence": confidence, "occurred_at": occurred_at,
        "details": details or {},
    }


class ActivityBroadcastTest(unittest.TestCase):
    def setUp(self):
        self.advisor = LLMAdvisor("EDGE-W01-B02", "B02", "W-01")

    def test_instant_broadcast_with_risk_hint(self):
        activity = {"label": "standing", "previous": "lying", "switched": True, "since": 1.0}
        b = self.advisor.activity_broadcast(activity, PATIENT, occurred_at="2026-08-19T01:20:00Z")
        self.assertEqual(b.mode, "instant")
        self.assertIn("B02", b.text)
        self.assertIn("李伯伯", b.text)
        self.assertIn("站立", b.text)
        self.assertIn("跌倒", b.text)  # 跌倒高风险提示

    def test_instant_broadcast_without_risk(self):
        activity = {"label": "lying", "previous": "sitting", "switched": True}
        b = self.advisor.activity_broadcast(activity, {}, occurred_at="2026-08-19T01:20:00Z")
        self.assertIn("卧躺", b.text)
        self.assertNotIn("跌倒", b.text)

    def test_period_summary(self):
        activities = [
            {"label": "lying", "switched": False},
            {"label": "lying", "switched": False},
            {"label": "sitting", "switched": True, "previous": "lying"},
            {"label": "standing", "switched": True, "previous": "sitting"},
        ]
        b = self.advisor.activity_period_summary(
            PATIENT, activities, "2026-08-19 晚班",
            window_start="2026-08-19T08:00:00Z", window_end="2026-08-19T16:00:00Z")
        self.assertEqual(b.mode, "period")
        self.assertIn("卧躺", b.text)
        self.assertIn("切换 2 次", b.text)


class AggregateActivitiesTest(unittest.TestCase):
    def test_stats(self):
        activities = [
            {"label": "lying", "switched": False},
            {"label": "lying", "switched": False},
            {"label": "sitting", "switched": True},
            {"label": "standing", "switched": True},
        ]
        stats = LLMAdvisor.aggregate_activities(activities)
        self.assertEqual(stats["total"], 4)
        self.assertEqual(stats["switches"], 2)
        self.assertEqual(stats["risk_switches"], 1)
        self.assertEqual(stats["labels"][0], "lying")
        self.assertIn("卧躺 50%", stats["dist_str"])


class HandoverFollowupTest(unittest.TestCase):
    def setUp(self):
        self.advisor = LLMAdvisor("EDGE-W01-B02", "B02", "W-01")

    def test_followup_resolved(self):
        lines = self.advisor._build_followup(
            {"watch_points": ["跌倒风险高，下床需陪同"]}, {"fall_suspected": 0})
        self.assertTrue(lines)
        self.assertIn("已落实", lines[0])

    def test_followup_ongoing(self):
        lines = self.advisor._build_followup(
            {"watch_points": ["压疮翻身"]}, {"long_still": 3, "bedsore_risk": 2})
        self.assertIn("仍发生 5 次", lines[0])

    def test_no_previous_returns_none(self):
        self.assertIsNone(self.advisor._build_followup(None, {}))
        self.assertIsNone(self.advisor._build_followup({"watch_points": []}, {}))

    def test_handover_contains_followup_section(self):
        events = [make_event("E1", "long_still", "P2", 0.75, "2026-08-19T01:20:00Z")]
        ho = self.advisor.generate_shift_handover(
            PATIENT, events, "2026-08-19", "day",
            window_start="2026-08-19T00:00:00Z", window_end="2026-08-19T08:00:00Z",
            previous_handover={"watch_points": ["跌倒风险高，下床需陪同"]})
        self.assertIn("上次交接事项跟踪", ho.handover_text)
        self.assertIn("已落实", ho.handover_text)
        self.assertTrue(ho.watch_points)

    def test_handover_with_stats_sections(self):
        events = [make_event("E1", "long_still", "P2", 0.75, "2026-08-19T01:20:00Z")]
        ho = self.advisor.generate_shift_handover(
            PATIENT, events, "2026-08-19", "day",
            window_start="2026-08-19T00:00:00Z", window_end="2026-08-19T08:00:00Z",
            bed_stats={"samples": 100, "occupied_samples": 82, "occupied_ratio": 0.82},
            env_stats={"temperature": 26.3, "humidity": 58.0, "co2": 645.0},
            activity_stats={"dist_str": "卧躺 60%、坐姿 40%", "switches": 6})
        self.assertIn("在床率 82%", ho.handover_text)
        self.assertIn("平均温度 26.3℃", ho.handover_text)
        self.assertIn("活动分布", ho.handover_text)

    def test_handover_trend_warning(self):
        events = [make_event(f"E{i}", "long_still", "P2", 0.75, "2026-08-19T01:20:00Z")
                  for i in range(5)]
        ho = self.advisor.generate_shift_handover(
            PATIENT, events, "2026-08-19", "day",
            window_start="2026-08-19T00:00:00Z", window_end="2026-08-19T08:00:00Z",
            trend={"counts": {"long_still": 7}, "shifts": 21})  # 班均 0.33，本班 5 次
        self.assertIn("明显偏高", ho.handover_text)

    def test_handover_trend_flat(self):
        events = [make_event("E1", "long_still", "P2", 0.75, "2026-08-19T01:20:00Z")]
        ho = self.advisor.generate_shift_handover(
            PATIENT, events, "2026-08-19", "day",
            window_start="2026-08-19T00:00:00Z", window_end="2026-08-19T08:00:00Z",
            trend={"counts": {"long_still": 21}, "shifts": 21})  # 班均 1，本班 1 次
        self.assertIn("持平", ho.handover_text)


class AnswerQuestionTest(unittest.TestCase):
    def test_mock_answer_contains_context(self):
        advisor = LLMAdvisor("EDGE-W01-B02", "B02", "W-01")
        answer = advisor.answer_question(
            "今晚离床几次？", ["近24小时共 3 起事件：离床 3 次", "18:03 离床 (P2，置信度85%)"],
            PATIENT)
        self.assertIn("离床 3 次", answer)

    def test_empty_context(self):
        advisor = LLMAdvisor("EDGE-W01-B02", "B02", "W-01")
        answer = advisor.answer_question("问题", [], PATIENT)
        self.assertIn("未检索到", answer)


class AskAgentRoutingTest(unittest.TestCase):
    def test_detect_fall_types(self):
        self.assertEqual(detect_event_types("昨天跌倒了几次"),
                         ("fall_suspected", "fall_prediction"))

    def test_detect_bed_by_patient_name(self):
        patients = {"B01": {"name": "张阿姨"}, "B02": {"name": "李伯伯"}}
        self.assertEqual(detect_bed("李伯伯昨晚怎么样", patients, "B01"), "B02")

    def test_detect_bed_by_id(self):
        self.assertEqual(detect_bed("B03 有事件吗", {}, "B01"), "B03")


class AgentStorageTest(unittest.TestCase):
    def _seed_db(self, tmp):
        db = LocalDatabase(os.path.join(tmp, "edge_test.db"))
        for i in range(4):
            db.save_observation({
                "ward_id": "W-01", "node_id": "EDGE-W01-B02", "bed_id": "B02",
                "source_type": "camera",
                "data": {"posture": "sitting",
                         "activity": {"label": "sitting" if i < 2 else "standing",
                                      "switched": i == 2, "previous": "sitting"}},
                "quality": {}, "timestamp": f"2026-08-19T01:0{i}:00Z",
            })
        for i in range(4):
            db.save_observation({
                "ward_id": "W-01", "node_id": "EDGE-W01-B02", "bed_id": "B02",
                "source_type": "bed_sensor",
                "data": {"occupied": i < 3, "absence_seconds": 0},
                "quality": {}, "timestamp": f"2026-08-19T01:0{i}:00Z",
            })
        for i in range(2):
            db.save_observation({
                "ward_id": "W-01", "node_id": "EDGE-W01-B02", "bed_id": "B02",
                "source_type": "environment",
                "data": {"temperature": 26.0 + i, "humidity": 55.0, "co2": 600, "light": 300},
                "quality": {}, "timestamp": f"2026-08-19T01:0{i}:00Z",
            })
        db.save_shift_handover({
            "node_id": "EDGE-W01-B02", "bed_id": "B02",
            "shift_date": "2026-08-18", "shift_period": "day",
            "window_start": "2026-08-18T00:00:00Z", "window_end": "2026-08-18T08:00:00Z",
            "event_count": 5, "p1_count": 1, "patient": PATIENT,
            "handover_text": "# 上次交接", "mode": "mock",
            "generated_at": "2026-08-18T08:10:00Z",
            "watch_points": ["跌倒风险高，下床需陪同", "压疮翻身"],
        })
        return db

    def test_queries_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = self._seed_db(tmp)
            activities = db.get_activity_between("2026-08-19T00:00:00Z", "2026-08-19T08:00:00Z")
            self.assertEqual(len(activities), 4)
            bed_stats = db.get_bed_stats_between("2026-08-19T00:00:00Z", "2026-08-19T08:00:00Z")
            self.assertEqual(bed_stats["samples"], 4)
            self.assertEqual(bed_stats["occupied_ratio"], 0.75)
            env_stats = db.get_env_stats_between("2026-08-19T00:00:00Z", "2026-08-19T08:00:00Z")
            self.assertEqual(env_stats["temperature"], 26.5)
            previous = db.get_last_handover("B02", before_generated_at="2026-08-19T00:00:00Z")
            self.assertEqual(previous["shift_date"], "2026-08-18")
            self.assertEqual(len(previous["watch_points"]), 2)

            db.save_activity_broadcast({
                "node_id": "EDGE-W01-B02", "bed_id": "B02", "mode": "instant",
                "text": "【播报】B02床 李伯伯 转为站立", "activity": {"label": "standing"},
                "timestamp": "2026-08-19T01:02:00Z",
            })
            conn = db.get_conn()
            count = conn.execute("SELECT COUNT(*) FROM activity_broadcasts").fetchone()[0]
            conn.close()
            self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
