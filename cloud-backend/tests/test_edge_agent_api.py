"""边缘 Agent 桥接测试：MQTT response/broadcast 处理 + REST 端点

复用 _fixtures 的 SQLite 内存库 + 假 paho/WS，不连真实 MySQL/MQTT。
"""

import unittest

from fastapi.testclient import TestClient

from _fixtures import install_test_db, clear_all_tables

from app import main as main_module
from app import mqtt_handler as handler_module
from app.database import EdgeAgentMessage

# 拦截 startup/shutdown 的外部连接
main_module.init_db = lambda **kw: None
main_module.mqtt_handler.connect = lambda: None
main_module.mqtt_handler.disconnect = lambda: None


class EdgeAgentMqttTest(unittest.TestCase):
    def setUp(self):
        self.db = install_test_db()
        from _fixtures import FakeWS
        self.ws = FakeWS()
        self.handler = handler_module.MqttHandler(self.ws)

    def _persist(self, data):
        self.handler._handle_agent_response(data, envelope=None)

    def test_agent_response_wakes_pending(self):
        import threading
        ev = threading.Event()
        self.handler._pending_requests["req-1"] = {"event": ev, "result": None}
        self._persist({"request_id": "req-1", "action": "ask", "status": "ok",
                       "question": "今天离床几次？", "answer": "3 次", "bed_id": "B02",
                       "node_id": "EDGE-W01-B02", "model_name": "qwen"})
        self.assertTrue(ev.wait(1.0))
        with self.handler._pending_lock:
            result = self.handler._pending_requests["req-1"]["result"]
        self.assertEqual(result["answer"], "3 次")
        types = [m["type"] for m in self.ws.messages]
        self.assertIn("agent_answer", types)

    def test_agent_broadcast_persists_and_broadcasts(self):
        self.handler._handle_agent_broadcast({
            "bed_id": "B02", "node_id": "EDGE-W01-B02", "ward_id": "W-01",
            "mode": "instant", "text": "【播报】B02床 李伯伯 转为站立",
            "model": {"name": "qwen2.5-1.5b", "mode": "mock"},
        })
        types = [m["type"] for m in self.ws.messages]
        self.assertIn("agent_broadcast", types)
        msg = self.db.query(EdgeAgentMessage).filter_by(action="broadcast").first()
        self.assertIsNotNone(msg)
        self.assertIn("转为站立", msg.answer)

    def test_request_agent_offline(self):
        result = self.handler.request_agent("EDGE-W01-B02",
                                            {"action": "ask", "question": "q"})
        self.assertEqual(result.get("offline"), True)


class EdgeAgentApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = install_test_db()
        cls._ctx = TestClient(main_module.app)
        cls._ctx.__enter__()
        cls.client = cls._ctx

    @classmethod
    def tearDownClass(cls):
        cls._ctx.__exit__(None, None, None)

    def setUp(self):
        clear_all_tables(self.db)
        # 注册节点（直接调 _handle_health，走内存库会话）
        main_module.mqtt_handler._handle_health({
            "node_id": "EDGE-W01-B02", "ward_id": "W-01", "bed_id": "B02",
            "status": "online", "timestamp": "2026-08-19T00:00:00Z",
        })

    def test_handover_generate_offline_504(self):
        r = self.client.post("/api/edge-agent/handover/generate", json={
            "node_id": "EDGE-W01-B02", "bed_id": "B02",
            "shift_date": "2026-08-19", "shift_period": "day", "wait_seconds": 3,
        })
        self.assertEqual(r.status_code, 504, r.text)

    def test_ask_offline_504(self):
        r = self.client.post("/api/edge-agent/ask", json={
            "node_id": "EDGE-W01-B02", "bed_id": "B02",
            "question": "今天离床几次？", "wait_seconds": 3,
        })
        self.assertEqual(r.status_code, 504, r.text)

    def test_ask_unknown_node_404(self):
        r = self.client.post("/api/edge-agent/ask", json={
            "node_id": "NO-SUCH", "bed_id": "B02", "question": "q",
        })
        self.assertEqual(r.status_code, 404)

    def test_handovers_list_empty(self):
        r = self.client.get("/api/edge-agent/handovers", params={"ward_id": "W-01"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"], [])


if __name__ == "__main__":
    unittest.main()
