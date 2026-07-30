"""Training scheduler tests: orchestration + algorithm layer."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from app.scheduler import (
    TrainingScheduler, Strategy, ClientUpdate, RoundState,
    FedAvgScheduler, SemiAsyncScheduler,
    flatten_weights, unflatten_weights, weight_norm_diff,
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
