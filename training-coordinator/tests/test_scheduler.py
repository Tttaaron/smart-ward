"""协同训练调度器冒烟测试

验证 TrainingScheduler 骨架接口可用。建鸿/振鑫实现聚合算法后应补充：
- FedAvg 加权平均正确性
- 陈旧度加权权重计算
- 异常更新剔除
- 超时与回滚

使用 unittest.TestCase 以便 `python -m unittest discover` 能自动发现，
同时保留 `python test_scheduler.py` 直接运行的能力。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.scheduler import TrainingScheduler, Strategy, ClientUpdate, RoundState


class StrategyEnumTest(unittest.TestCase):
    """策略枚举测试"""

    def test_strategy_enum(self):
        """策略枚举值应覆盖三阶段"""
        self.assertEqual(Strategy.SYNC_FEDAVG.value, "sync_fedavg")
        self.assertEqual(Strategy.ASYNC_STALE.value, "async_stale")
        self.assertEqual(Strategy.ROBUST.value, "robust")


class SyncRoundLifecycleTest(unittest.TestCase):
    """同步训练轮次生命周期测试"""

    def test_sync_round_lifecycle(self):
        """同步训练轮次生命周期：启动 -> 收集更新 -> 聚合"""
        scheduler = TrainingScheduler(strategy=Strategy.SYNC_FEDAVG)
        r = scheduler.start_round("job-001", ["EDGE-W01-B01", "EDGE-W01-B02"], round_id=1)
        self.assertEqual(r.state, RoundState.RUNNING)
        self.assertEqual(len(r.participants), 2)
        self.assertEqual(r.min_participants, 2)

        # 第一个节点上报，未达阈值，不应 ready
        upd1 = ClientUpdate("EDGE-W01-B01", 1, {"w1": 0.5}, 100, 30.0, 0.3, 0.85)
        ready = scheduler.collect_update("job-001", 1, upd1)
        self.assertFalse(ready)

        # 第二个节点上报，达到阈值，应 ready
        upd2 = ClientUpdate("EDGE-W01-B02", 1, {"w1": 0.6}, 120, 32.0, 0.28, 0.87)
        ready = scheduler.collect_update("job-001", 1, upd2)
        self.assertTrue(ready)

        # 触发聚合
        result = scheduler.aggregate("job-001", 1)
        self.assertIsNotNone(result)
        self.assertEqual(result["participants"], 2)


class InsufficientParticipantsTest(unittest.TestCase):
    """参与节点不足测试"""

    def test_insufficient_participants(self):
        """参与节点不足时聚合应返回 None"""
        scheduler = TrainingScheduler(strategy=Strategy.SYNC_FEDAVG)
        scheduler.start_round("job-002", ["EDGE-W01-B01"], round_id=1)
        upd = ClientUpdate("EDGE-W01-B01", 1, {"w1": 0.5}, 100, 30.0, 0.3, 0.85)
        scheduler.collect_update("job-002", 1, upd)
        # min_participants=2 但只有 1 个节点上报
        result = scheduler.aggregate("job-002", 1)
        self.assertIsNone(result)


class RoundStateMachineTest(unittest.TestCase):
    """轮次状态机测试"""

    def test_round_state_machine(self):
        """轮次状态机：pending->running->completed"""
        scheduler = TrainingScheduler()
        r = scheduler.start_round("job-003", ["N1", "N2"])
        self.assertEqual(r.state, RoundState.RUNNING)
        # 补足更新后聚合，状态变为 completed
        scheduler.collect_update("job-003", 1, ClientUpdate("N1", 1, {}, 10, 1.0, 0.5, 0.8))
        scheduler.collect_update("job-003", 1, ClientUpdate("N2", 1, {}, 10, 1.0, 0.5, 0.8))
        scheduler.aggregate("job-003", 1)
        self.assertEqual(r.state, RoundState.COMPLETED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
