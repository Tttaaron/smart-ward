# training-coordinator 测试证据：15 项全绿

- 日期：2026-08-10
- 模块：training-coordinator（协同训练调度 + 版本一致性）
- 负责人：P4 振鑫
- 相关提交：dddfcf3（FedBuff + MiniLLM/Hinton 蒸馏）、532c131（当前 master）

## 复现命令

`ash
cd smart-ward/training-coordinator
python -m unittest tests.test_scheduler -v
`

## 结果

Ran 15 tests - OK（全部通过）

| 测试类 | 数量 | 覆盖内容 |
|--------|------|----------|
| StrategyEnumTest | 1 | 三种聚合策略枚举 |
| SyncRoundLifecycleTest | 1 | 同步训练轮次生命周期 |
| InsufficientParticipantsTest | 1 | 参与节点不足拒绝聚合 |
| RoundStateMachineTest | 1 | 轮次状态机 |
| FedAvgTest | 2 | FedAvg 基础/加权聚合 |
| SemiAsyncTest | 1 | 陈旧度限制/丢弃 |
| WeightHelperTest | 1 | 权重工具函数 |
| ModelRegistryTest | 4 | 版本冲突、迟到节点、回滚、灰度发布 |
| FedBuffTest | 3 | FedBuff 公式、eta 缩放、陈旧丢弃 |

## 蒸馏实验（8/5，合成数据 synthetic-784-v1，可复现）

`ash
python demo/run_distill_minillm.py
`

| 路线 | accuracy | recall_macro | f1_macro |
|------|----------|--------------|----------|
| A. teacher (256) | 0.9940 | 0.9940 | 0.9940 |
| B. reverse-KL distill (MiniLLM) | 0.9745 | 0.9745 | 0.9744 |
| C. forward-KL distill (Hinton) | 0.9915 | 0.9915 | 0.9914 |
| D. baseline student (32) | 0.9285 | 0.9288 | 0.9283 |

结论：两种蒸馏均优于学生基线；正向 KL（Hinton KD）比反向 KL（MiniLLM）在本分类任务上增益更高（+0.0631 vs +0.0461 F1）。

## FedBuff 公式实现

w_{t+1} = w_t + eta * (1/b) * sum_{k in S_t} (w_k - w_t)

对应论文：Nguyen et al., AISTATS 2022, arXiv:2106.06639

## 版本一致性功能

- 模型版本登记 + SHA-256 哈希（app/model_registry.py）
- 灰度发布 -> 边缘 health 确认 -> 全量 rollout
- 失败回滚到上一已知可用版本
- 版本命名规则见 docs/model_version.md

