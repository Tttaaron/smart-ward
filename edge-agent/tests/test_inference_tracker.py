"""Cloud inference lifecycle tests for the edge agent."""

import os
import json
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    import paho.mqtt.client  # noqa: F401
except ModuleNotFoundError:
    paho_module = types.ModuleType("paho")
    mqtt_module = types.ModuleType("paho.mqtt.client")

    class _FakeMqttClient:
        def __init__(self, *args, **kwargs):
            pass

    mqtt_module.Client = _FakeMqttClient
    mqtt_package = types.ModuleType("paho.mqtt")
    mqtt_package.client = mqtt_module
    paho_module.mqtt = mqtt_package
    sys.modules["paho"] = paho_module
    sys.modules["paho.mqtt"] = mqtt_package
    sys.modules["paho.mqtt.client"] = mqtt_module

from database import LocalDatabase
from inference_tracker import InferenceTracker
from main import EdgeAgent
from task_router import TaskRouter


class InferenceTrackerTest(unittest.TestCase):
    def setUp(self):
        self.tracker = InferenceTracker(finished_ttl_s=60)
        self.event = {"event_id": "evt-1", "state": "new", "confidence": 0.4}

    def test_resolve_is_idempotent(self):
        request = self.tracker.register(
            "evt-1", "trace-1", "cloud", "cloud", self.event, timeout_s=2, now=10
        )
        self.assertIsNotNone(request)
        self.assertEqual(self.tracker.resolve("evt-1", "wrong-trace", now=11).status,
                         "trace_mismatch")
        result = self.tracker.resolve("evt-1", "trace-1", now=12)
        self.assertEqual(result.status, "completed")
        self.assertEqual(self.tracker.resolve("evt-1", "trace-1", now=13).status,
                         "duplicate")

    def test_expire_returns_request_once(self):
        self.tracker.register(
            "evt-1", "trace-1", "cloud", "cloud", self.event, timeout_s=1, now=10
        )
        expired = self.tracker.expire(now=11)
        self.assertEqual([r.event_id for r in expired], ["evt-1"])
        self.assertEqual(self.tracker.expire(now=12), [])
        self.assertEqual(self.tracker.resolve("evt-1", "trace-1", now=13).status,
                         "duplicate")

    def test_duplicate_pending_request_is_rejected(self):
        first = self.tracker.register(
            "evt-1", "trace-1", "cloud", "cloud", self.event, timeout_s=2, now=10
        )
        second = self.tracker.register(
            "evt-1", "trace-2", "cloud", "cloud", self.event, timeout_s=2, now=11
        )
        self.assertIsNotNone(first)
        self.assertIsNone(second)


class LocalDatabaseCloudUpdateTest(unittest.TestCase):
    def test_update_event_replaces_payload_and_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = LocalDatabase(os.path.join(temp_dir, "edge.db"))
            event = {
                "event_id": "evt-1",
                "ward_id": "W-01",
                "node_id": "EDGE-1",
                "bed_id": "B01",
                "event_type": "fall_suspected",
                "priority": "P1",
                "state": "new",
                "confidence": 0.4,
                "occurred_at": "2026-01-01T00:00:00Z",
                "details": {},
            }
            db.save_event(event)
            event["state"] = "false_positive"
            event["details"] = {"cloud_inference": {"judgment": "reject"}}
            self.assertTrue(db.update_event(event, synced=True))
            rows = db.get_unsynced_events()
            self.assertEqual(rows, [])

    def test_edge_response_updates_state_and_ignores_duplicate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            agent = EdgeAgent.__new__(EdgeAgent)
            agent.node_id = "EDGE-1"
            agent.db = LocalDatabase(os.path.join(temp_dir, "edge.db"))
            agent.mqtt = Mock()
            agent.mqtt.connected = False
            agent.task_router = TaskRouter("EDGE-1")
            agent.inference_tracker = InferenceTracker()
            event = {
                "event_id": "evt-main",
                "ward_id": "W-01",
                "node_id": "EDGE-1",
                "bed_id": "B01",
                "event_type": "fall_suspected",
                "priority": "P1",
                "state": "new",
                "confidence": 0.4,
                "occurred_at": "2026-01-01T00:00:00Z",
                "detected_at": "2026-01-01T00:00:01Z",
                "model": {"model_name": "rule", "model_version": "1", "inference_ms": 1},
                "evidence_refs": [],
                "details": {},
            }
            agent.db.save_event(event)
            agent.inference_tracker.register(
                "evt-main", "trace-main", "cloud", "cloud", event, timeout_s=2
            )

            response = {
                "event_id": "evt-main",
                "trace_id": "trace-main",
                "payload": {
                    "event_id": "evt-main",
                    "judgment": "reject",
                    "confidence": 0.92,
                    "advice": "复核后排除",
                },
            }
            agent.handle_inference_response(response)
            agent.handle_inference_response(response)

            conn = agent.db.get_conn()
            try:
                row = conn.execute(
                    "SELECT state, payload FROM safety_events WHERE event_id = ?",
                    ("evt-main",),
                ).fetchone()
            finally:
                conn.close()
            self.assertEqual(row[0], "false_positive")
            self.assertEqual(json.loads(row[1])["details"]["cloud_inference"]["judgment"], "reject")
            self.assertEqual(agent.task_router.metrics.cloud_offload_succeeded, 1)

    def test_timeout_response_preserves_edge_result_and_marks_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            agent = EdgeAgent.__new__(EdgeAgent)
            agent.node_id = "EDGE-1"
            agent.db = LocalDatabase(os.path.join(temp_dir, "edge.db"))
            agent.mqtt = Mock()
            agent.mqtt.connected = False
            agent.task_router = TaskRouter("EDGE-1")
            agent.inference_tracker = InferenceTracker()
            event = {
                "event_id": "evt-timeout",
                "ward_id": "W-01",
                "node_id": "EDGE-1",
                "bed_id": "B01",
                "event_type": "fall_suspected",
                "priority": "P1",
                "state": "new",
                "confidence": 0.4,
                "occurred_at": "2026-01-01T00:00:00Z",
                "details": {},
            }
            agent.db.save_event(event)
            agent.inference_tracker.register(
                "evt-timeout", "trace-timeout", "cloud", "cloud", event, timeout_s=2
            )

            agent.handle_inference_response({
                "event_id": "evt-timeout",
                "trace_id": "trace-timeout",
                "payload": {
                    "event_id": "evt-timeout",
                    "trace_id": "trace-timeout",
                    "judgment": "escalate",
                    "confidence": 0.0,
                    "advice": "Cloud inference timeout; edge fallback remains enabled.",
                    "latency_ms": 10.0,
                    "status": "timeout",
                },
            })

            conn = agent.db.get_conn()
            try:
                row = conn.execute(
                    "SELECT state, payload FROM safety_events WHERE event_id = ?",
                    ("evt-timeout",),
                ).fetchone()
            finally:
                conn.close()
            self.assertEqual(row[0], "new")
            cloud = json.loads(row[1])["details"]["cloud_inference"]
            self.assertEqual(cloud["status"], "timeout")
            self.assertEqual(cloud["reason"], "cloud_timeout")
            self.assertEqual(agent.task_router.metrics.cloud_offload_failed, 1)


if __name__ == "__main__":
    unittest.main()
