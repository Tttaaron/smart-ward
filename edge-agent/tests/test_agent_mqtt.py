"""边缘 Agent 服务与 MQTT 命令路由测试（agent_service / mqtt_client）"""

import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from database import LocalDatabase  # noqa: E402
from agent_service import EdgeAgentService, detect_bed, utc_now_iso  # noqa: E402
from mqtt_client import MqttClient  # noqa: E402
from inference_tracker import InferenceTracker  # noqa: E402
from task_router import TaskRouter  # noqa: E402
from main import EdgeAgent  # noqa: E402

PATIENT = {"name": "李伯伯", "age": 72, "nursing_level": "二级护理",
           "diagnosis": "髋部骨折术后", "fall_risk": True, "bedsore_risk": True}


def make_event(event_id, event_type, priority, confidence, occurred_at):
    return {
        "event_id": event_id, "ward_id": "W-01", "node_id": "EDGE-W01-B02",
        "bed_id": "B02", "event_type": event_type, "priority": priority,
        "confidence": confidence, "occurred_at": occurred_at,
        "details": {"posture": "sitting"},
    }


class AgentServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = LocalDatabase(os.path.join(self.tmp.name, "edge.db"))
        self.service = EdgeAgentService("EDGE-W01-B02", "B02", "W-01",
                                        database=self.db, patient=PATIENT)

    def tearDown(self):
        # LocalDatabase 持久连接不关会锁住 db 文件，Windows 上临时目录删不掉
        self.db.close()
        self.tmp.cleanup()

    def test_generate_handover_writes_db_and_returns_report(self):
        for i in range(3):
            self.db.save_event(make_event(f"E{i}", "long_still", "P2", 0.75,
                                          f"2026-08-19T01:0{i}:00Z"))
        result = self.service.generate_handover("2026-08-19", "day")
        self.assertEqual(result["event_count"], 3)
        self.assertIn("长时间静止", result["handover_text"])
        self.assertTrue(result["watch_points"])
        rows = self.db.list_shift_handovers(bed_id="B02")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["shift_date"], "2026-08-19")

    def test_answer_retrieves_events(self):
        # 用当前时间的事件，保证落在"今天"窗口
        self.db.save_event(make_event("E1", "bed_leave", "P2", 0.85, utc_now_iso()))
        result = self.service.answer("今天离床了几次？")
        self.assertIn("离床", result["answer"])
        self.assertEqual(result["time_range"], "今天")
        self.assertIn("离床 1 次", "".join(result["context_blocks"]))

    def test_answer_empty(self):
        result = self.service.answer("今天压疮风险几次？")
        self.assertIn("无相关事件", result["answer"])


class AgentMqttRoutingTest(unittest.TestCase):
    def setUp(self):
        self.client = MqttClient("W-01", "EDGE-W01-B02", "localhost", 1883)
        self.received = []
        self.client.set_agent_request_callback(lambda payload: self.received.append(payload))

    def _msg(self, topic, payload):
        return SimpleNamespace(topic=topic, payload=json.dumps(payload).encode())

    def test_agent_request_routed_to_callback(self):
        payload = {"request_id": "r1", "action": "generate_handover"}
        self.client._on_message(None, None,
                                self._msg("node/EDGE-W01-B02/agent/request", payload))
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0]["action"], "generate_handover")

    def test_other_node_request_ignored(self):
        self.client._on_message(None, None,
                                self._msg("node/EDGE-W01-B01/agent/request",
                                          {"action": "ask"}))
        self.assertEqual(self.received, [])

    def test_publish_agent_response_topic(self):
        captured = {}
        self.client.connected = True
        self.client.client.publish = lambda topic, payload, qos=0: captured.update(
            topic=topic, payload=payload)
        ok = self.client.publish_agent_response({"request_id": "r1", "status": "ok"})
        self.assertTrue(ok)
        self.assertEqual(captured["topic"],
                         "ward/W-01/node/EDGE-W01-B02/agent/response")
        body = json.loads(captured["payload"])
        self.assertEqual(body["payload"]["request_id"], "r1")


class AgentTimeoutResponseTest(unittest.TestCase):
    """阶段6：云端 status=timeout 响应——保留边缘原始判断，标记回退"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = LocalDatabase(os.path.join(self.tmp.name, "edge.db"))
        tracker = InferenceTracker()

        class FakeMqtt:
            connected = False
            def publish_event(self, payload):
                return False

        fake = SimpleNamespace(
            node_id="EDGE-W01-B02", bed_id="B02",
            inference_tracker=tracker,
            task_router=TaskRouter("EDGE-W01-B02"),
            db=self.db, mqtt=FakeMqtt(),
        )
        fake.handle_inference_response = EdgeAgent.handle_inference_response.__get__(fake)
        fake._apply_cloud_failure = EdgeAgent._apply_cloud_failure.__get__(fake)
        fake._persist_cloud_update = EdgeAgent._persist_cloud_update.__get__(fake)
        self.fake = fake

    def tearDown(self):
        # LocalDatabase 持久连接不关会锁住 db 文件，Windows 上临时目录删不掉
        self.db.close()
        self.tmp.cleanup()

    def test_timeout_response_keeps_edge_judgment(self):
        evt = make_event("E-TMO", "seizure", "P1", 0.85, utc_now_iso())
        self.db.save_event(evt)  # 边端已上报的事件
        registered = self.fake.inference_tracker.register(
            event_id="E-TMO", trace_id="TR-TMO", target="cloud", mode="cloud",
            event_payload=evt, timeout_s=5)
        self.assertIsNotNone(registered)

        self.fake.handle_inference_response({"payload": {
            "event_id": "E-TMO", "trace_id": "TR-TMO", "status": "timeout",
            "judgment": "escalate", "timeout_ms": 500,
            "latency_ms": 500.0}})

        rows = self.db.get_events_between("2000-01-01T00:00:00Z", "2100-01-01T00:00:00Z")
        match = [e for e in rows if e["event_id"] == "E-TMO"]
        self.assertEqual(len(match), 1)
        saved = match[0]
        # 云端超时：不采纳 escalate，保留边缘原始判断并标记回退
        self.assertNotEqual(saved.get("state"), "escalated")
        self.assertNotIn("escalated", json.dumps(saved))
        ci = saved["details"]["cloud_inference"]
        self.assertEqual(ci["status"], "fallback_edge")
        # 云端主动回传的 status=timeout 用 reason=cloud_timeout，
        # 与本地超时线程的 reason=timeout 区分来源
        self.assertEqual(ci["reason"], "cloud_timeout")


if __name__ == "__main__":
    unittest.main()
