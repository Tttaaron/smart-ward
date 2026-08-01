"""Training scheduler tests: orchestration + algorithm layer."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from app.scheduler import (
    TrainingScheduler, Strategy, ClientUpdate, RoundState,
    FedAvgScheduler, SemiAsyncScheduler,
    flatten_weights, unflatten_weights, weight_norm_diff,
)
from app.model_registry import (
    ModelRegistry, ReleaseManager, ModelStatus, compute_model_hash,
)

# ---- helpers ----

def dummy_weights(scale=1.0):
    return [np.full((2,3), scale, np.float32), np.full((2,), scale, np.float32)]

# ---- orchestration layer tests (建鸿) ----

class StrategyEnumTest(unittest.TestCase):
    def test_strategy_enum(self):
        self.assertEqual(Strategy.SYNC_FEDAVG.value, "sync_fedavg")
        self.assertEqual(Strategy.ASYNC_STALE.value, "async_stale")
        self.assertEqual(Strategy.ROBUST.value, "robust")


class SyncRoundLifecycleTest(unittest.TestCase):
    def test_sync_round_lifecycle(self):
        scheduler = TrainingScheduler(strategy=Strategy.SYNC_FEDAVG)
        r = scheduler.start_round("job-001", ["EDGE-W01-B01", "EDGE-W01-B02"])
        self.assertEqual(r.state, RoundState.RUNNING)
        upd1 = ClientUpdate("EDGE-W01-B01", 1, {"w1":0.5}, 100, 30, 0.3, 0.85)
        ready = scheduler.collect_update("job-001", 1, upd1)
        self.assertFalse(ready)
        upd2 = ClientUpdate("EDGE-W01-B02", 1, {"w1":0.6}, 120, 32, 0.28, 0.87)
        ready = scheduler.collect_update("job-001", 1, upd2)
        self.assertTrue(ready)
        result = scheduler.aggregate("job-001", 1)
        self.assertIsNotNone(result)
        self.assertEqual(result["participants"], 2)
        self.assertEqual(result["status"], "aggregated")


class InsufficientParticipantsTest(unittest.TestCase):
    def test_insufficient_participants(self):
        scheduler = TrainingScheduler()
        scheduler.start_round("job-002", ["N1"])
        scheduler.collect_update("job-002", 1,
            ClientUpdate("N1", 1, {}, 100, 30, 0.3, 0.85))
        self.assertIsNone(scheduler.aggregate("job-002", 1))


class RoundStateMachineTest(unittest.TestCase):
    def test_round_state_machine(self):
        scheduler = TrainingScheduler()
        r = scheduler.start_round("job-003", ["N1","N2"])
        self.assertEqual(r.state, RoundState.RUNNING)
        scheduler.collect_update("job-003",1,ClientUpdate("N1",1,{},10,1,0.5,0.8))
        scheduler.collect_update("job-003",1,ClientUpdate("N2",1,{},10,1,0.5,0.8))
        scheduler.aggregate("job-003", 1)
        self.assertEqual(r.state, RoundState.COMPLETED)


# ---- algorithm layer tests (振鑫) ----

class FedAvgTest(unittest.TestCase):
    def test_basic_aggregation(self):
        sched = FedAvgScheduler(dummy_weights(0), 2, seed=0)
        updates = {0: (dummy_weights(2), 10), 1: (dummy_weights(4), 10)}
        agg = sched.aggregate(updates)
        for arr in agg:
            self.assertTrue(np.allclose(arr, 3.0))
        self.assertEqual(sched.round, 1)

    def test_weighted_aggregation(self):
        sched = FedAvgScheduler(dummy_weights(0), 2, seed=0)
        updates = {0: (dummy_weights(1), 10), 1: (dummy_weights(5), 30)}
        agg = sched.aggregate(updates)
        for arr in agg:
            self.assertTrue(np.allclose(arr, 4.0))


class SemiAsyncTest(unittest.TestCase):
    def test_staleness_valid(self):
        sched = SemiAsyncScheduler(dummy_weights(0), 4, max_staleness=10, seed=0)
        for cid in range(4):
            sched._pending_updates[cid] = (dummy_weights(float(cid+1)), 10, 0)
        rec = sched.trigger_aggregation()
        self.assertTrue(rec["aggregated"])
        self.assertEqual(rec["num_updates"], 4)
        self.assertEqual(sched.round, 1)
        rec_late = sched.receive_update(0, dummy_weights(5), 10, 0)
        self.assertIsNone(rec_late)
        sched.round = 20
        rec_discard = sched.receive_update(1, dummy_weights(99), 10, 0)
        self.assertIsNone(rec_discard)
        self.assertNotIn(1, sched._pending_updates)


class WeightHelperTest(unittest.TestCase):
    def test_weight_utilities(self):
        w = dummy_weights(3)
        flat = flatten_weights(w)
        self.assertEqual(flat.shape, (8,))
        restored = unflatten_weights(flat, w)
        for a, b in zip(w, restored):
            self.assertTrue(np.allclose(a, b))
        self.assertEqual(weight_norm_diff(w, restored), 0.0)
        self.assertGreater(weight_norm_diff(w, dummy_weights(5)), 0.0)


class ModelRegistryTest(unittest.TestCase):
    """P4 T5: version registry, conflict, release and rollback evidence."""

    def make_weights(self, scale):
        return [np.full((2, 3), scale, np.float32), np.full((2,), scale, np.float32)]

    def test_version_conflict(self):
        """Same weights (same hash) must not be registered twice."""
        reg = ModelRegistry()
        w = self.make_weights(1.0)
        reg.register("qwen1.5b", w, "models/qwen1.5b/", "ward-nlu-500-v1")
        with self.assertRaises(ValueError):
            reg.register("qwen1.5b", w, "models/qwen1.5b/", "ward-nlu-500-v1")
        self.assertEqual(len(reg.list()), 1)
        print("[PASS] test_version_conflict")

    def test_late_client_update(self):
        """SemiAsync: stale-but-valid late updates are accepted; updates
        beyond max_staleness are discarded."""
        sched = SemiAsyncScheduler(self.make_weights(0), 4, max_staleness=3, seed=0)
        # Two fresh updates hit the threshold (ceil(4/2)=2) -> round 1
        sched.receive_update(0, self.make_weights(2.0), 10, client_round=0)
        sched.receive_update(1, self.make_weights(2.0), 10, client_round=0)
        self.assertEqual(sched.round, 1)

        # Late update trained on round 0, arrives at round 1 -> staleness 1 (valid)
        rec = sched.receive_update(2, self.make_weights(3.0), 10, client_round=0)
        self.assertIsNone(rec)  # buffered, below threshold
        self.assertIn(2, sched._pending_updates)

        # Update trained on round -4 -> staleness 5 > max_staleness 3 -> discarded
        discarded = sched.receive_update(3, self.make_weights(9.0), 10, client_round=-4)
        self.assertIsNone(discarded)
        self.assertNotIn(3, sched._pending_updates)
        print("[PASS] test_late_client_update")

    def test_release_rollback(self):
        """A release that fails health confirmation must roll back to the
        last known-good active version."""
        reg = ModelRegistry()
        mgr = ReleaseManager(reg, min_healthy_nodes=1)

        v1 = reg.register("qwen1.5b", self.make_weights(1.0),
                          "models/qwen1.5b/", "ward-nlu-500-v1",
                          metrics={"acc": 0.80})
        mgr.publish(v1.model_version)
        mgr.confirm_health(v1.model_version, "EDGE-W01-B01", ok=True, latency_ms=120)
        mgr.rollout(v1.model_version)
        self.assertEqual(reg.active().model_version, v1.model_version)

        v2 = reg.register("qwen1.5b", self.make_weights(2.0),
                          "models/qwen1.5b/", "ward-nlu-500-v1",
                          metrics={"acc": 0.90})
        mgr.publish(v2.model_version)
        # Health fails on edge node -> rollback
        mgr.confirm_health(v2.model_version, "EDGE-W01-B01", ok=False, latency_ms=9999)
        rec = mgr.rollback(v2.model_version)
        self.assertEqual(rec["status"], "ok")
        self.assertEqual(rec["fallback"], v1.model_version)
        self.assertEqual(reg.active().model_version, v1.model_version)
        self.assertEqual(reg.get(v2.model_version).status, ModelStatus.ROLLED_BACK)
        print("[PASS] test_release_rollback")

    def test_release_rollout(self):
        """Gray release -> healthy nodes -> full rollout -> ACTIVE."""
        reg = ModelRegistry()
        mgr = ReleaseManager(reg, min_healthy_nodes=2)
        v = reg.register("qwen1.5b", self.make_weights(3.0),
                         "models/qwen1.5b/", "ward-nlu-500-v1")
        rec = mgr.publish(v.model_version, gray_percent=10)
        self.assertEqual(rec["release_batch"][:8], "release-")
        self.assertEqual(reg.get(v.model_version).status, ModelStatus.GRAY)

        # Not enough healthy nodes yet
        mgr.confirm_health(v.model_version, "EDGE-W01-B01", ok=True, latency_ms=110)
        with self.assertRaises(RuntimeError):
            mgr.rollout(v.model_version)

        mgr.confirm_health(v.model_version, "EDGE-W01-B02", ok=True, latency_ms=130)
        mgr.rollout(v.model_version)
        self.assertEqual(reg.active().model_version, v.model_version)
        print("[PASS] test_release_rollout")



if __name__ == "__main__":
    unittest.main(verbosity=2)
