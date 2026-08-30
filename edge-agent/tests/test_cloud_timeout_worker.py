"""独立云端超时定时线程测试：不依赖主循环 tick 也能及时回退边缘。"""

import os
import sys
import json
import queue
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

try:
    import paho.mqtt.client  # noqa: F401
except ModuleNotFoundError:
    mqtt_module = types.ModuleType("paho.mqtt.client")

    class _FakeMqttClient:
        def __init__(self, *args, **kwargs):
            pass

    mqtt_module.Client = _FakeMqttClient
    mqtt_package = types.ModuleType("paho.mqtt")
    mqtt_package.client = mqtt_module
    paho_module = types.ModuleType("paho")
    paho_module.mqtt = mqtt_package
    sys.modules["paho"] = paho_module
    sys.modules["paho.mqtt"] = mqtt_package
    sys.modules["paho.mqtt.client"] = mqtt_module

from database import LocalDatabase
from inference_tracker import InferenceTracker
from main import EdgeAgent
from task_router import ComputeTarget, TaskRouter


def _event(event_id: str) -> dict:
    return {
        "event_id": event_id,
        "ward_id": "W-01",
        "node_id": "EDGE-1",
        "bed_id": "B01",
        "event_type": "fall_suspected",
        "priority": "P1",
        "state": "new",
        "confidence": 0.4,
        "occurred_at": "2026-08-05T00:00:00Z",
        "detected_at": "2026-08-05T00:00:01Z",
        "model": {"model_name": "rule", "model_version": "1", "inference_ms": 1},
        "evidence_refs": [],
        "details": {},
    }


class CloudTimeoutWorkerTest(unittest.TestCase):
    def _make_agent(self, db):
        agent = EdgeAgent.__new__(EdgeAgent)
        agent.node_id = "EDGE-1"
        agent.bed_id = "B01"
        agent.ward_id = "W-01"
        agent.db = db
        agent.mqtt = Mock()
        agent.mqtt.connected = False
        agent.task_router = TaskRouter("EDGE-1")
        agent.inference_tracker = InferenceTracker(finished_ttl_s=60)
        agent._cloud_timeout_stop = threading.Event()
        agent._cloud_timeout_thread = None
        return agent

    def _wait_pending_zero(self, tracker, timeout_s=3.0):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if tracker.get_status()["pending"] == 0:
                return
            time.sleep(0.02)
        self.fail("独立超时线程未在预期时间内清理 pending 请求")

    def _wait_cloud_failure_written(self, agent, event_id, timeout_s=3.0):
        """等待 worker 线程完成 DB 回退写入（expire 与写库之间有间隔）。"""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            conn = agent.db.get_conn()
            try:
                row = conn.execute(
                    "SELECT payload FROM safety_events WHERE event_id = ?",
                    (event_id,)).fetchone()
            finally:
                conn.close()
            if row:
                details = json.loads(row[0]).get("details", {})
                if details.get("cloud_inference"):
                    return details["cloud_inference"]
            time.sleep(0.02)
        self.fail(f"云端回退未写入事件: {event_id}")

    def _stop_worker(self, agent):
        agent._cloud_timeout_stop.set()
        if agent._cloud_timeout_thread and agent._cloud_timeout_thread.is_alive():
            agent._cloud_timeout_thread.join(timeout=1.0)

    def test_worker_expires_pending_without_main_loop(self):
        """主循环未运行（不调用 tick）时，独立线程仍能按超时回退边缘。"""
        with tempfile.TemporaryDirectory() as temp_dir, \
                LocalDatabase(os.path.join(temp_dir, "edge.db")) as db:
            agent = self._make_agent(db)
            agent._cloud_timeout_check_interval = 0.05
            event = _event("evt-to")
            agent.db.save_event(event)
            agent.inference_tracker.register(
                "evt-to", "trace-to", "cloud", "cloud", event, timeout_s=0.15)
            agent._start_cloud_timeout_worker()
            try:
                self._wait_pending_zero(agent.inference_tracker)
                details = self._wait_cloud_failure_written(agent, "evt-to")
                self.assertEqual(details["status"], "fallback_edge")
                self.assertEqual(details["reason"], "timeout")
                self.assertEqual(details["trace_id"], "trace-to")
                self.assertEqual(agent.task_router.metrics.cloud_offload_failed, 1)
            finally:
                self._stop_worker(agent)

    def test_worker_does_not_expire_unexpired_pending(self):
        """超时未到的请求不应被独立线程误清。"""
        with tempfile.TemporaryDirectory() as temp_dir, \
                LocalDatabase(os.path.join(temp_dir, "edge.db")) as db:
            agent = self._make_agent(db)
            agent._cloud_timeout_check_interval = 0.02
            event = _event("evt-ok")
            agent.db.save_event(event)
            agent.inference_tracker.register(
                "evt-ok", "trace-ok", "cloud", "cloud", event, timeout_s=10)
            agent._start_cloud_timeout_worker()
            try:
                time.sleep(0.3)  # 远小于 10s 超时
                self.assertEqual(agent.inference_tracker.get_status()["pending"], 1)
                self.assertEqual(agent.task_router.metrics.cloud_offload_failed, 0)
            finally:
                self._stop_worker(agent)

    def test_worker_stops_cleanly(self):
        """停止事件设置后线程退出，不留后台残留。"""
        with tempfile.TemporaryDirectory() as temp_dir, \
                LocalDatabase(os.path.join(temp_dir, "edge.db")) as db:
            agent = self._make_agent(db)
            agent._cloud_timeout_check_interval = 0.01
            agent._start_cloud_timeout_worker()
            thread = agent._cloud_timeout_thread
            self.assertIsNotNone(thread)
            self.assertTrue(thread.is_alive())
            agent._cloud_timeout_stop.set()
            thread.join(timeout=2.0)
            self.assertFalse(thread.is_alive())

    def test_hybrid_request_uses_contract_mode(self):
        """HYBRID 路由必须发出契约允许的 hybrid，而不是历史 review 值。"""
        with tempfile.TemporaryDirectory() as temp_dir, \
                LocalDatabase(os.path.join(temp_dir, "edge.db")) as db:
            agent = self._make_agent(db)
            agent.mqtt.connected = True
            agent.mqtt.publish_event = Mock()
            agent.llm_advisor = Mock()
            agent.llm_advisor.enhance_event.return_value = types.SimpleNamespace(
                enhanced=False,
                llm_response=None,
            )
            agent.task_router.detect_conflict = Mock(return_value=None)
            agent.task_router.route = Mock(return_value=types.SimpleNamespace(
                target=ComputeTarget.HYBRID,
                reason="需要云端复核",
                to_dict=lambda: {"target": "hybrid"},
            ))
            agent._send_cloud_inference = Mock()

            event_payload = _event("evt-hybrid")
            event = types.SimpleNamespace(
                event_type=event_payload["event_type"],
                priority=event_payload["priority"],
                confidence=event_payload["confidence"],
                to_dict=lambda: event_payload,
            )

            agent._publish_events([event], [])

            request, target, mode = agent._send_cloud_inference.call_args.args[:3]
            self.assertEqual(target, ComputeTarget.HYBRID)
            self.assertEqual(mode, "hybrid")
            self.assertEqual(request["mode"], "hybrid")


class AsyncEnhancementTest(unittest.TestCase):
    """LLM_ASYNC_ENHANCE=true 时增强不得阻塞 _publish_events。"""

    def _agent(self, db, async_mode):
        agent = EdgeAgent.__new__(EdgeAgent)
        agent.node_id = "EDGE-1"
        agent.bed_id = "B01"
        agent.ward_id = "W-01"
        agent.db = db
        agent.mqtt = Mock()
        agent.mqtt.connected = True
        agent.mqtt.publish_event = Mock(return_value=True)
        agent.task_router = TaskRouter("EDGE-1")
        agent.task_router.detect_conflict = Mock(return_value=None)
        agent.task_router.route = Mock(return_value=types.SimpleNamespace(
            target=ComputeTarget.EDGE, reason="edge",
            to_dict=lambda: {"target": "edge"}))
        agent.inference_tracker = InferenceTracker()
        agent._llm_async = async_mode
        agent._enhance_queue = queue.Queue(maxsize=4)
        agent._enhance_stop = threading.Event()
        agent._enhance_thread = None
        return agent

    @staticmethod
    def _event(payload):
        return types.SimpleNamespace(
            event_type=payload["event_type"], priority=payload["priority"],
            confidence=payload["confidence"], to_dict=lambda: payload)

    def _slow_advisor(self, delay=0.4):
        advisor = Mock()

        def slow_enhance(event_dict, obs_dicts):
            time.sleep(delay)
            return types.SimpleNamespace(
                enhanced=True, summary="摘要", advice="建议",
                llm_response=types.SimpleNamespace(ttft_ms=35.0))

        advisor.enhance_event = Mock(side_effect=slow_enhance)
        return advisor

    def test_async_mode_does_not_block_publish(self):
        with tempfile.TemporaryDirectory() as temp_dir,                 LocalDatabase(os.path.join(temp_dir, "edge.db")) as db:
            agent = self._agent(db, async_mode=True)
            agent.llm_advisor = self._slow_advisor(0.4)

            payload = _event("evt-async")
            started = time.perf_counter()
            agent._publish_events([self._event(payload)], [])
            elapsed = time.perf_counter() - started

            # 增强耗时 0.4s，异步模式下主循环不应为此等待
            self.assertLess(elapsed, 0.15, f"_publish_events 被阻塞了 {elapsed:.3f}s")
            # 事件已即时上报，且入队待增强
            agent.mqtt.publish_event.assert_called_once()
            self.assertEqual(agent._enhance_queue.qsize(), 1)

    def test_sync_mode_still_blocks_and_attaches_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir,                 LocalDatabase(os.path.join(temp_dir, "edge.db")) as db:
            agent = self._agent(db, async_mode=False)
            agent.llm_advisor = self._slow_advisor(0.2)

            payload = _event("evt-sync")
            started = time.perf_counter()
            agent._publish_events([self._event(payload)], [])
            elapsed = time.perf_counter() - started

            self.assertGreaterEqual(elapsed, 0.2)
            published = agent.mqtt.publish_event.call_args.args[0]
            self.assertEqual(published["details"]["llm_summary"], "摘要")

    def test_worker_writes_enhancement_back(self):
        with tempfile.TemporaryDirectory() as temp_dir,                 LocalDatabase(os.path.join(temp_dir, "edge.db")) as db:
            agent = self._agent(db, async_mode=True)
            agent.llm_advisor = self._slow_advisor(0.0)

            payload = _event("evt-writeback")
            db.save_event(payload)
            agent._submit_enhancement(payload, [])
            agent._start_enhance_worker()
            try:
                deadline = time.monotonic() + 3.0
                while time.monotonic() < deadline:
                    conn = db.get_conn()
                    try:
                        row = conn.execute(
                            "SELECT payload FROM safety_events WHERE event_id = ?",
                            ("evt-writeback",)).fetchone()
                    finally:
                        conn.close()
                    details = json.loads(row[0]).get("details", {}) if row else {}
                    if details.get("llm_summary"):
                        self.assertEqual(details["llm_summary"], "摘要")
                        self.assertEqual(details["llm_advice"], "建议")
                        return
                    time.sleep(0.02)
                self.fail("异步增强结果未回写到 SQLite")
            finally:
                agent._enhance_stop.set()
                if agent._enhance_thread:
                    agent._enhance_thread.join(timeout=2.0)

    def test_queue_full_drops_oldest(self):
        with tempfile.TemporaryDirectory() as temp_dir,                 LocalDatabase(os.path.join(temp_dir, "edge.db")) as db:
            agent = self._agent(db, async_mode=True)
            for i in range(6):  # maxsize=4
                agent._submit_enhancement(_event(f"evt-{i}"), [])
            self.assertEqual(agent._enhance_queue.qsize(), 4)
            # 最旧的两条被丢弃，队首应是 evt-2
            first, _ = agent._enhance_queue.get_nowait()
            self.assertEqual(first["event_id"], "evt-2")


if __name__ == "__main__":
    unittest.main()
