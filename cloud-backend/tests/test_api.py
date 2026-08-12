"""云端事件中心 REST API 集成测试（TestClient + SQLite 内存库）

拦截 startup 的 init_db / MQTT connect，避免连接真实 MySQL/MQTT；
数据全部走 _fixtures 注入的 SQLite 内存库。对应 docs/07 第 4 节 TC-101~118。
"""

import unittest

from fastapi.testclient import TestClient

from _fixtures import install_test_db, clear_all_tables

from app import main as main_module

# 拦截 startup/shutdown 的外部连接（TestClient 触发 lifespan 时生效）
main_module.init_db = lambda **kw: None
main_module.mqtt_handler.connect = lambda: None
main_module.mqtt_handler.disconnect = lambda: None


class ApiTestBase(unittest.TestCase):
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
        # 同一库内测试方法间清表，保证断言不互相污染
        clear_all_tables(self.db)

    def _inject_event(self, **over):
        payload = {
            "event_id": "EV-T1",
            "ward_id": "W-01",
            "node_id": "EDGE-W01-B01",
            "bed_id": "B01",
            "event_type": "fall_suspected",
            "confidence": 0.9,
        }
        payload.update(over)
        r = self.client.post("/api/events", json=payload)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["data"]["event_id"]

    def _register_node(self, node_id="EDGE-W01-B01", status="online"):
        main_module.mqtt_handler._handle_health({
            "node_id": node_id, "ward_id": "W-01", "bed_id": "B01",
            "status": status, "timestamp": "2026-08-10T00:00:00Z",
        })


class BasicApiTest(ApiTestBase):
    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok"})

    def test_root(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("智慧病房", r.json()["message"])

    def test_wards_empty_list(self):
        r = self.client.get("/api/wards")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"], [])

    def test_ward_not_found(self):
        r = self.client.get("/api/wards/NO-SUCH")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["code"], 404)


class EventApiTest(ApiTestBase):
    def test_inject_and_query_event(self):
        self._inject_event()
        r = self.client.get("/api/events")
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["event_id"], "EV-T1")
        self.assertEqual(data[0]["state"], "notified")
        self.assertEqual(data[0]["priority"], "P1")  # fall_suspected 映射 P1

    def test_events_filter_by_priority_state_type(self):
        self._inject_event(event_id="EV-A", event_type="fall_suspected")
        self._inject_event(event_id="EV-B", event_type="bed_leave")
        self._inject_event(event_id="EV-C", event_type="nurse_call")

        r = self.client.get("/api/events", params={"priority": "P1"})
        self.assertEqual(len(r.json()["data"]), 2)  # fall_suspected + nurse_call

        r = self.client.get("/api/events", params={"state": "notified"})
        self.assertEqual(len(r.json()["data"]), 3)

        r = self.client.get("/api/events", params={"event_type": "bed_leave"})
        data = r.json()["data"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["priority"], "P2")

    def test_events_by_type_stats(self):
        self._inject_event(event_id="EV-A", event_type="fall_suspected")
        self._inject_event(event_id="EV-B", event_type="fall_suspected")
        self._inject_event(event_id="EV-C", event_type="seizure")
        r = self.client.get("/api/events/by-type")
        data = r.json()["data"]
        self.assertEqual(data["fall_suspected"], 2)
        self.assertEqual(data["seizure"], 1)

    def test_event_detail(self):
        self._inject_event()
        r = self.client.get("/api/events/EV-T1")
        self.assertEqual(r.status_code, 200)
        data = r.json()["data"]
        self.assertEqual(data["model"]["name"], "rule-fusion-v1")
        self.assertIn("dispositions", data)

    def test_event_not_found(self):
        r = self.client.get("/api/events/NO-SUCH")
        self.assertEqual(r.status_code, 404)

    def test_ack_flow_acknowledge_then_resolve(self):
        self._inject_event()
        r = self.client.post("/api/events/EV-T1/ack", json={
            "action": "acknowledge", "operator_id": "nurse-01",
            "operator_name": "李护士", "operator_role": "nurse",
        })
        self.assertEqual(r.status_code, 200, r.text)

        detail = self.client.get("/api/events/EV-T1").json()["data"]
        self.assertEqual(detail["state"], "acknowledged")
        # 注：详情接口 /api/events/{id} 不含 acknowledged_at 字段（API 缺口），
        # 用列表接口验证时间戳
        evs = self.client.get("/api/events").json()["data"]
        self.assertIsNotNone(evs[0]["acknowledged_at"])
        self.assertEqual(len(detail["dispositions"]), 1)
        self.assertEqual(detail["dispositions"][0]["operator_name"], "李护士")

        self.client.post("/api/events/EV-T1/ack", json={
            "action": "resolve", "operator_id": "nurse-01",
        })
        detail = self.client.get("/api/events/EV-T1").json()["data"]
        self.assertEqual(detail["state"], "resolved")
        evs = self.client.get("/api/events").json()["data"]
        self.assertIsNotNone(evs[0]["resolved_at"])

    def test_ack_unknown_event_404(self):
        r = self.client.post("/api/events/NO-SUCH/ack", json={
            "action": "acknowledge", "operator_id": "nurse-01"})
        self.assertEqual(r.status_code, 404)

    def test_ack_invalid_action_422(self):
        self._inject_event()
        r = self.client.post("/api/events/EV-T1/ack", json={
            "action": "delete", "operator_id": "nurse-01"})
        self.assertEqual(r.status_code, 422)


class NodeAndStatsApiTest(ApiTestBase):
    def test_nodes_list(self):
        self._register_node("EDGE-W01-B01")
        self._register_node("EDGE-W01-B02", status="degraded")
        r = self.client.get("/api/nodes")
        data = r.json()["data"]
        self.assertEqual(len(data), 2)
        by_id = {n["id"]: n for n in data}
        self.assertEqual(by_id["EDGE-W01-B02"]["status"], "degraded")

    def test_stats(self):
        self._register_node()
        self._inject_event(event_id="EV-A", event_type="fall_suspected")
        r = self.client.get("/api/stats")
        data = r.json()["data"]
        self.assertEqual(data["total_nodes"], 1)
        self.assertEqual(data["online_nodes"], 1)
        self.assertEqual(data["events_today"], 1)
        self.assertEqual(data["pending_events"], 1)
        self.assertEqual(data["p1_pending"], 1)

    def test_beds_occupancy(self):
        self._register_node()
        self._inject_event(event_id="EV-A", event_type="bed_leave")
        r = self.client.get("/api/beds/occupancy")
        data = r.json()["data"]
        self.assertEqual(len(data), 0)  # 未预置床位表数据

    def test_observations_filter(self):
        from datetime import datetime
        now = datetime.utcnow().isoformat() + "Z"
        main_module.mqtt_handler._handle_observation({
            "node_id": "EDGE-W01-B01", "ward_id": "W-01", "bed_id": "B01",
            "timestamp": now,
            "sources": [{"source_type": "camera", "data": {"people": 1}, "quality": {}}],
        })
        r = self.client.get("/api/observations")
        self.assertEqual(len(r.json()["data"]), 1)
        r = self.client.get("/api/observations", params={"source_type": "camera"})
        self.assertEqual(len(r.json()["data"]), 1)
        r = self.client.get("/api/observations", params={"source_type": "bed_sensor"})
        self.assertEqual(len(r.json()["data"]), 0)


class ModelAndControlApiTest(ApiTestBase):
    def test_models_deploy_records_deployment(self):
        r = self.client.post(
            "/api/models/deploy?node_id=EDGE-W01-B01",
            json={
                "model_name": "shufflenetv2-sa",
                "model_version": "1.0.0-int4",
                "artifact_url": "http://models/fall.pt",
                "runtime": "pytorch",
                "target_device": "gpu",
            },
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["data"]["model"], "shufflenetv2-sa@1.0.0-int4")

        from app.database import ModelDeployment
        dep = self.db.query(ModelDeployment).filter_by(node_id="EDGE-W01-B01").first()
        self.assertIsNotNone(dep)
        self.assertEqual(dep.status, "pending")
        self.assertEqual(dep.action, "deploy")

    def test_models_deploy_missing_node_id_422(self):
        r = self.client.post("/api/models/deploy", json={
            "model_name": "m", "model_version": "v",
            "artifact_url": "http://x/1.pt"})
        self.assertEqual(r.status_code, 422)

    def test_env_control_node_not_found(self):
        r = self.client.post("/api/env/control", json={
            "node_id": "NO-SUCH", "device": "light", "action": "on"})
        self.assertEqual(r.status_code, 404)

    def test_env_control_success(self):
        self._register_node()
        r = self.client.post("/api/env/control", json={
            "node_id": "EDGE-W01-B01", "device": "light", "action": "on",
            "reason": "night_wandering"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["data"]["device"], "light")

        from app.database import AuditLog
        audit = self.db.query(AuditLog).filter_by(action="env_control").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.target_id, "EDGE-W01-B01")


class ShiftSummaryApiTest(ApiTestBase):
    def _seed_events(self):
        self._inject_event(event_id="EV-1", event_type="fall_suspected")
        self._inject_event(event_id="EV-2", event_type="bed_leave")
        self._inject_event(event_id="EV-3", event_type="seizure")

    @staticmethod
    def _today():
        # generate 的时段窗口按本地东八区（08:00~16:00 = UTC 00:00~08:00），
        # 注入事件 occurred_at 为当前 UTC 时间，故用今天日期保证落入窗口
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")

    def test_generate_shift_summary(self):
        self._seed_events()
        r = self.client.post("/api/shift-summaries/generate", json={
            "ward_id": "W-01", "shift_date": self._today(), "shift_period": "day",
            "operator_id": "nurse-01"})
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()["data"]
        self.assertEqual(data["event_count"], 3)
        self.assertEqual(data["p1_count"], 2)  # fall + seizure
        self.assertEqual(data["p2_count"], 1)
        self.assertIn("疑似跌倒=1次", data["summary_text"])

    def test_generate_idempotent_overwrite(self):
        self._seed_events()
        self.client.post("/api/shift-summaries/generate", json={
            "ward_id": "W-01", "shift_date": self._today(), "shift_period": "day",
            "operator_id": "nurse-01"})
        # 同 ward+date+period 再次生成 → 覆盖而非新增
        self.client.post("/api/shift-summaries/generate", json={
            "ward_id": "W-01", "shift_date": self._today(), "shift_period": "day",
            "operator_id": "nurse-02"})
        r = self.client.get("/api/shift-summaries")
        self.assertEqual(len(r.json()["data"]), 1)

    def test_generate_invalid_date_400(self):
        r = self.client.post("/api/shift-summaries/generate", json={
            "ward_id": "W-01", "shift_date": "not-a-date", "shift_period": "day"})
        self.assertEqual(r.status_code, 400)

    def test_delete_shift_summary(self):
        self._seed_events()
        self.client.post("/api/shift-summaries/generate", json={
            "ward_id": "W-01", "shift_date": self._today(), "shift_period": "day"})
        r = self.client.get("/api/shift-summaries")
        summary_id = r.json()["data"][0]["id"]

        r = self.client.delete(f"/api/shift-summaries/{summary_id}")
        self.assertEqual(r.status_code, 200)
        r = self.client.get("/api/shift-summaries")
        self.assertEqual(len(r.json()["data"]), 0)

    def test_delete_shift_summary_not_found(self):
        r = self.client.delete("/api/shift-summaries/99999")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
