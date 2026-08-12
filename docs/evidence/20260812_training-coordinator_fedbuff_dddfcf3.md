# FedBuff 异步聚合 + 陈旧度加权 - 实现证据

- 日期：2026-08-12
- 负责人：P4 振鑫（协作：P3 建鸿、P7 彦晗）
- 代码提交：dddfcf3（FedBuff + MiniLLM/Hinton 蒸馏）
- 状态：已完成

## 一、实现内容

| 项 | 说明 |
|----|------|
| FedBuffScheduler | 缓冲异步聚合：攒够 buffer 大小再聚合，w <- w + eta*(1/b)*sum(w_k - w) |
| 陈旧度控制 | staleness <= max_staleness 接受；超过则丢弃，不进 buffer |
| 工厂入口 | create_scheduler("fedbuff", ...) |
| 论文依据 | Nguyen et al., FedBuff, AISTATS 2022, arXiv:2106.06639 |

## 二、代码位置

`
training-coordinator/app/scheduler.py
  FedBuffScheduler.receive_update()    # 缓冲 + 陈旧度检查
  FedBuffScheduler._aggregate_pending() # 聚合公式实现
  FedBuffScheduler.simulate_concurrent_round() # 异构客户端模拟
  create_scheduler("fedbuff", ...)    # 工厂分支
`

## 三、新增测试（3 项，总计 15 项全绿）

| 测试 | 验证点 |
|------|--------|
| test_buffered_aggregation_formula | 公式正确性：初始0 + eta*( (2-0)+(4-0) )/2 = 3.0 |
| test_fedbuff_eta_scale | eta=0.5 时输出 1.5，验证缩放 |
| test_fedbuff_stale_discard | staleness > max_staleness 的更新被丢弃 |

命令：python -m unittest tests.test_scheduler -v -> Ran 15 tests, OK

## 四、复现命令

`ash
cd smart-ward/training-coordinator
python -m unittest tests.test_scheduler -v
python demo/run_fedavg.py          # FedAvg 对比
python demo/run_semi_async.py     # 半异步陈旧度对比
`

## 五、与陈旧度加权的关系

- 半异步路径使用 FedAsync 线性陈旧度权重 1/(staleness+1)（SemiAsyncScheduler）
- FedBuff 路径使用缓冲触发 + 超限丢弃，兼容陈旧度控制
- 两套调度均可通过 create_scheduler() 切换
