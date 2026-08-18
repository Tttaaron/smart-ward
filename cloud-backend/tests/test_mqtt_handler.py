"""云端 MQTT 消息处理器单元测试

覆盖 docs/07 中云端侧核心链路：
- 事件入库 / 幂等 / 告警任务 / 审计
- 节点健康注册与更新
- 观测写库与 latest_state 缓存
- 告警处置状态机（acknowledge/resolve/false_positive/escalate）
- 主题路由与异常消息容错
"""

import json
import unittest
from types import SimpleNamespace

from _fixtures import install_test_db, clear_all_tables, FakeWS

from app.mqtt_handler import MqttHandler, _parse_ts
from app.database import (
    SafetyEvent, AlertTask, AuditLog, Observation, EdgeNode, EventDisposition,
)


def _envelope(payload: dict) -> bytes:
    return json.dumps({
        "message_id": "m1", "schema_version": "v1",
        "occurred_at": "2026-08-10T00:00:00Z", "source": "edge",
        "payload": payload,
    }).encode()


class MqttHandlerTest(unittest.TestCase):
    def setUp(self):
        self.db = install_test_db()
        self.ws = FakeWS()
        self.handler = MqttHandler(self.ws)

    def _event_payload(self, event_id="EV-1", **over):
        payload = {
            "event_id": event_id,
            "ward_id": "W-01",
            "node_id": "EDGE-W01-B01",
            "bed_id": "B01",
            "event_type": "fall_suspected",
            "priority": "P1",
            "confidence": 0.92,
            "occurred_at": "2026-08-10T00:00:00Z",
            "detected_at": "2026-08-10T00:00:00Z",
            "model": {"model_name": "rule-fusion-v1", "model_version": "0.1.0",
                      "inference_ms": 5},
            "evidence_refs": ["img-1"],
            "rule_hits": ["r1"],
            "details": {"note": "demo"},
        }
        payload.update(over)
        return payload

    # ─── 事件处理 ───

    def test_handle_event_persists_event_task_and_audit(self):
        self.handler._handle_event(self._event_payload())

        event = self.db.query(SafetyEvent).filter_by(event_id="EV-1").first()
        self.assertIsNotNone(event)
        self.assertEqual(event.state, "notified")
        self.assertEqual(event.event_type, "fall_suspected")
        self.assertEqual(event.priority, "P1")
        self.assertEqual(event.model_name, "rule-fusion-v1")
        self.assertEqual(json.loads(event.evidence_refs), ["img-1"])

        task = self.db.query(AlertTask).filter_by(event_id="EV-1").first()
        self.assertIsNotNone(task)
        self.assertEqual(task.channel, "ws")

        audit = self.db.query(AuditLog).filter_by(action="event_create").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.target_id, "EV-1")

        # WS 广播
        ws_types = [m["type"] for m in self.ws.messages]
        self.assertIn("safety_event", ws_types)

    def test_handle_event_idempotent(self):
        self.handler._handle_event(self._event_payload())
        self.handler._handle_event(self._event_payload())  # 重复

        count = self.db.query(SafetyEvent).filter_by(event_id="EV-1").count()
        self.assertEqual(count, 1)

    def test_handle_event_missing_event_id_ignored(self):
        self.handler._handle_event(self._event_payload(event_id=None))
        self.assertEqual(self.db.query(SafetyEvent).count(), 0)

    # ─── 云端研判回写（首达入库、回写更新）───

    def _cloud_resubmit(self, judgment="confirm", state="notified"):
        """构造边缘收到云端判断后的重报事件"""
        return self._event_payload(
            state=state,
            details={
                "note": "demo",
                "cloud_inference": {
                    "status": "completed",
                    "judgment": judgment,
                    "confidence": 0.95,
                    "advice": "请立即前往床位检查",
                    "latency_ms": 120.5,
                    "trace_id": "TR-CLOUD-1",
                    "received_at": "2026-08-10T00:01:00Z",
                },
            })

    def test_cloud_inference_updates_existing_event(self):
        """事件已存在且重报携带 cloud_inference -> 更新 details/state 并广播"""
        self.handler._handle_event(self._event_payload())
        self.handler._handle_event(self._cloud_resubmit(judgment="confirm",
                                                        state="notified"))

        event = self.db.query(SafetyEvent).filter_by(event_id="EV-1").first()
        self.assertIsNotNone(event)
        details = json.loads(event.details)
        ci = details["cloud_inference"]
        self.assertEqual(ci["judgment"], "confirm")
        self.assertEqual(ci["advice"], "请立即前往床位检查")
        self.assertEqual(ci["trace_id"], "TR-CLOUD-1")
        # 原 details 保留
        self.assertEqual(details["note"], "demo")
        # 行数不重复
        self.assertEqual(self.db.query(SafetyEvent).filter_by(
            event_id="EV-1").count(), 1)

        # WS 广播 event_update
        update_msgs = [m for m in self.ws.messages if m["type"] == "event_update"]
        self.assertEqual(len(update_msgs), 1)
        self.assertEqual(update_msgs[0]["event_id"], "EV-1")
        self.assertEqual(update_msgs[0]["cloud_inference"]["judgment"], "confirm")

    def test_cloud_inference_updates_state_reject(self):
        """云端 reject -> 边缘重报 state=false_positive，云端同步"""
        self.handler._handle_event(self._event_payload())
        self.handler._handle_event(self._cloud_resubmit(judgment="reject",
                                                        state="false_positive"))
        event = self.db.query(SafetyEvent).filter_by(event_id="EV-1").first()
        self.assertEqual(event.state, "false_positive")

    def test_duplicate_without_cloud_inference_keeps_original(self):
        """重复上报但无 cloud_inference -> 保持幂等，不覆盖原数据"""
        self.handler._handle_event(self._event_payload())
        self.handler._handle_event(self._event_payload(details={"other": 1}))

        event = self.db.query(SafetyEvent).filter_by(event_id="EV-1").first()
        details = json.loads(event.details)
        self.assertEqual(details["note"], "demo")  # 原始 details 未被覆盖
        self.assertNotIn("other", details)
        self.assertNotIn("cloud_inference", details)
        # 无 event_update 广播
        self.assertFalse([m for m in self.ws.messages
                          if m["type"] == "event_update"])

    # ─── 节点健康 ───

    def test_handle_health_registers_new_node(self):
        self.handler._handle_health({
            "node_id": "EDGE-W01-B02",
            "ward_id": "W-01",
            "bed_id": "B02",
            "status": "online",
            "buffered_events": 3,
            "model_version": "1.0.0-int4",
            "timestamp": "2026-08-10T00:00:00Z",
        })
        node = self.db.query(EdgeNode).filter_by(id="EDGE-W01-B02").first()
        self.assertIsNotNone(node)
        self.assertEqual(node.status, "online")
        self.assertEqual(node.buffered_events, 3)

        ws_types = [m["type"] for m in self.ws.messages]
        self.assertIn("node_health", ws_types)

    def test_handle_health_updates_existing_node(self):
        self.handler._handle_health({
            "node_id": "EDGE-W01-B01", "ward_id": "W-01", "bed_id": "B01",
            "status": "online", "buffered_events": 1,
        })
        self.handler._handle_health({
            "node_id": "EDGE-W01-B01", "ward_id": "W-01", "bed_id": "B01",
            "status": "degraded", "buffered_events": 5,
        })
        node = self.db.query(EdgeNode).filter_by(id="EDGE-W01-B01").first()
        self.assertEqual(node.status, "degraded")
        self.assertEqual(node.buffered_events, 5)
        # 未重复注册
        self.assertEqual(self.db.query(EdgeNode).count(), 1)

    # ─── 观测数据 ───

    def test_handle_observation_writes_sources_and_cache(self):
        self.handler._handle_observation({
            "node_id": "EDGE-W01-B01", "ward_id": "W-01", "bed_id": "B01",
            "timestamp": "2026-08-10T00:00:00Z",
            "sources": [
                {"source_type": "camera", "data": {"people": 1}, "quality": {}},
                {"source_type": "bed_sensor", "data": {"pressure": 0.8}, "quality": {}},
            ],
        })
        self.assertEqual(self.db.query(Observation).count(), 2)
        self.assertIn("last_observation",
                      self.handler.latest_state["EDGE-W01-B01"])

        ws_types = [m["type"] for m in self.ws.messages]
        self.assertIn("observation", ws_types)

    # ─── 告警处置状态机 ───

    def _ack_payload(self, action, event_id="EV-1"):
        return {
            "event_id": event_id,
            "action": action,
            "operator": {"id": "nurse-01", "name": "李护士", "role": "nurse"},
            "result": "已到床旁", "note": "处置完成",
        }

    def test_handle_ack_state_transitions(self):
        cases = [
            ("acknowledge", "acknowledged", "acknowledged_at"),
            ("resolve", "resolved", "resolved_at"),
            ("false_positive", "false_positive", None),
            ("escalate", "escalated", None),
        ]
        for action, expect_state, ts_field in cases:
            with self.subTest(action=action):
                clear_all_tables(self.db)
                self.handler._handle_event(self._event_payload())
                self.handler._handle_ack(self._ack_payload(action))

                event = self.db.query(SafetyEvent).filter_by(event_id="EV-1").first()
                self.assertEqual(event.state, expect_state)
                if ts_field:
                    self.assertIsNotNone(getattr(event, ts_field))
                # 处置记录 + 审计
                disp = self.db.query(EventDisposition).filter_by(
                    event_id="EV-1", action=action).first()
                self.assertIsNotNone(disp)
                self.assertEqual(disp.operator_id, "nurse-01")
                self.assertEqual(
                    self.db.query(AuditLog).filter_by(action="event_ack").count(), 1)

    def test_handle_ack_unknown_event_noop(self):
        self.handler._handle_ack(self._ack_payload("acknowledge", event_id="NO-SUCH"))
        self.assertEqual(self.db.query(EventDisposition).count(), 0)
        self.assertEqual(self.db.query(AuditLog).filter_by(action="event_ack").count(), 0)

    def test_handle_ack_missing_fields_ignored(self):
        self.handler._handle_event(self._event_payload())
        self.handler._handle_ack({"event_id": "EV-1"})  # 无 action
        event = self.db.query(SafetyEvent).filter_by(event_id="EV-1").first()
        self.assertEqual(event.state, "notified")

    # ─── 主题路由 ───

    def _msg(self, topic, payload=None):
        return SimpleNamespace(
            topic=topic,
            payload=_envelope(payload) if payload is not None else b"{}",
        )

    def test_on_message_routes_event_topic(self):
        self.handler._on_message(None, None, self._msg(
            "ward/W-01/node/EDGE-W01-B01/event", self._event_payload()))
        self.assertEqual(
            self.db.query(SafetyEvent).filter_by(event_id="EV-1").count(), 1)

    def test_on_message_routes_health_topic(self):
        self.handler._on_message(None, None, self._msg(
            "ward/W-01/node/EDGE-W01-B01/health",
            {"node_id": "EDGE-W01-B01", "ward_id": "W-01", "bed_id": "B01",
             "status": "online", "timestamp": "2026-08-10T00:00:00Z"}))
        self.assertEqual(
            self.db.query(EdgeNode).filter_by(id="EDGE-W01-B01").count(), 1)

    def test_on_message_routes_ack_topic(self):
        self.handler._handle_event(self._event_payload())
        self.handler._on_message(None, None, self._msg(
            "ward/W-01/alert/EV-1/ack", self._ack_payload("resolve")))
        event = self.db.query(SafetyEvent).filter_by(event_id="EV-1").first()
        self.assertEqual(event.state, "resolved")

    def test_on_message_invalid_json_ignored(self):
        msg = SimpleNamespace(topic="ward/W-01/node/N/event",
                              payload=b"{not-json")
        self.handler._on_message(None, None, msg)  # 不应抛异常

    # ─── 发布辅助 ───

    def test_publish_returns_false_when_disconnected(self):
        # 假客户端 is_connected() 恒 False → 所有 publish 返回 False
        self.assertFalse(self.handler.publish_ack("W-01", "EV-1", {"action": "ack"}))
        self.assertFalse(self.handler.publish_model_deploy("N1", {"model": "m"}))
        self.assertFalse(self.handler.publish_env_control("N1", {"device": "light"}))

    # ─── 工具函数 ───

    def test_parse_ts_handles_z_suffix(self):
        from datetime import datetime
        dt = _parse_ts("2026-08-10T08:30:00Z")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.hour, 8)
        # 空/None 回退当前 UTC 时间
        self.assertIsInstance(_parse_ts(""), datetime)
        self.assertIsInstance(_parse_ts(None), datetime)


if __name__ == "__main__":
    unittest.main()
