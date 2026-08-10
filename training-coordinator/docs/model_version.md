# 模型版本管理规范（T5）

> 负责人：P4 振鑫 | 协作：P5 先伟、P1 亚伦 | 截止：2026-08-22

## 一、版本命名规则

| 类型 | 命名格式 | 示例 | 说明 |
|------|----------|------|------|
| 节点模型版本 | edge-{model_name}-{M.m.p} | edge-qwen1.5b-1.2.0 | 边缘加载的模型，每个聚合结果生成一个 |
| 聚合版本 | agg-{job_id}-r{round_id} | agg-job001-r12 | 一次 FedAvg/异步聚合的产出标识 |
| 教师模型版本 | teacher-{model_name}-{M.m.p} | teacher-qwen14b-1.0.0 | 蒸馏源模型（云端 14B） |
| 学生模型版本 | student-{model_name}-{M.m.p} | student-qwen1.5b-0.3.0 | 蒸馏产物（边缘 1.5B） |
| 发布批次 | release-{YYYYMMDD}-{seq} | release-20260801-01 | 一次灰度/全量发布 |

## 二、版本关系表

| 字段 | 含义 | 记录时机 | 示例 |
|------|------|----------|------|
| model_name | 模型名 | 注册时 | qwen1.5b |
| model_version | 模型版本 | 注册时 | edge-qwen1.5b-1.2.0 |
| model_hash | 权重 SHA-256（前16位） | 注册时 | 3f2a8c... |
| aggregation_version | 来源聚合轮次 | 聚合完成 | agg-job001-r12 |
| dataset_version | 训练数据集版本 | 注册时 | ward-nlu-500-v1 |
| train_params | 训练超参/策略 | 注册时 | strategy=sync_fedavg |
| metrics | 聚合精度/损失 | 注册时 | avg_accuracy=0.84 |
| artifact_path | 产物路径 | 注册时 | models/qwen1.5b/ |
| status | draft/gray/active/rolled_back | 状态变更 | active |
| release_batch | 发布批次 | 发布时 | release-20260801-01 |
| node_ids | 已确认 health 的节点 | health 上报 | EDGE-W01-B01 |

## 三、发布流程

聚合完成 -> 注册模型版本(draft)
  -> publish() 灰度发布(gray, 10%)
  -> 边缘节点 confirm_health(ok=True, latency_ms)
  -> rollout() 全量发布(active)
  -> 边缘加载 model_version 并上报 health

health 失败或指标异常 -> rollback()
  -> 当前版本置为 rolled_back
  -> 回退到上一个已知可用 active 版本

## 四、边缘接口契约

- 边缘加载时读取 model_version（例如 edge-qwen1.5b-1.2.0）
- 边缘上报 health：node_id, model_version, ok, latency_ms
- 边缘无法识别 model_version 时回退到上一已知可运行版本

## 五、迟到/重复/冲突处理规则

| 异常场景 | 处理规则 | 实现 | 测试 |
|----------|----------|------|------|
| 版本冲突（相同权重哈希重复注册） | 相同 model_hash 只允许注册一次，重复注册抛 ValueError，保留原版本 | ModelRegistry.register() | test_version_conflict |
| 迟到节点（半异步/异步） | staleness <= max_staleness 接受，按 1/(staleness+1) 加权；超过 max_staleness 丢弃 | SemiAsyncScheduler.receive_update() | test_late_client_update |
| 迟到节点（FedBuff） | 超过 max_staleness 的更新丢弃，不进 buffer | FedBuffScheduler.receive_update() | test_fedbuff_stale_discard |
| 重复上传（同一节点同一轮） | 后到的更新覆盖 pending 中旧更新（后到为准）；已聚合轮次的更新不再生效 | receive_update() 按 client_id 覆盖 | test_late_client_update |
| 聚合失败/节点不足 | pending 为空时返回 aggregated=False；未达阈值不触发聚合 | trigger_aggregation() | test_insufficient_participants |
| 重复发布 | 非 DRAFT 状态的版本不可重复 publish，抛 ValueError | ReleaseManager.publish() | test_release_rollout |
| 灰度失败回滚 | GRAY 版本回滚时保留当前 ACTIVE；ACTIVE 版本回滚到上一 known-good | ReleaseManager.rollback() | test_release_rollback |

> 规则依据：FedAsync（arXiv:1903.03934）陈旧度衰减 + FedBuff（AISTATS 2022）缓冲触发 + 幂等注册。
## 六、验收证据

- 训练日志：数据版本、参数、模型哈希、聚合版本
- 版本表：本文件 + 注册记录
- 发布/回滚记录：release_log 输出
- 边缘 health 确认记录：health_summary 输出

## 七、代码位置

- 版本登记/发布/回滚：app/model_registry.py
- 聚合版本生成：app/scheduler.py (TrainingScheduler.aggregate)
- 测试：tests/test_scheduler.py (ModelRegistryTest)

## 八、公式与参考文献

| 公式/算法 | 论文 | 代码位置 |
|-----------|------|----------|
| FedAvg 加权平均 | McMahan et al., Communication-Efficient Learning of Deep Networks from Decentralized Data, AISTATS 2017 | FedAvgScheduler.aggregate() |
| 半异步陈旧度加权 (1/(s+1)) | Xie et al., Asynchronous Federated Optimization (FedAsync), arXiv:1903.03934, 2020 | SemiAsyncScheduler + default_staleness_weight() |
| 缓冲异步聚合 w <- w + eta*(1/b)*sum(w_k - w) | Nguyen et al., Federated Learning with Buffered Asynchronous Aggregation (FedBuff), AISTATS 2022, arXiv:2106.06639 | FedBuffScheduler |
| 反向 KL 蒸馏 L = E_q[log q - log p_T] | Gu et al., MiniLLM: Knowledge Distillation of Large Language Models, ICLR 2024, arXiv:2306.08543 | demo/run_distill_minillm.py (train_reverse_kl) |
| 正向 KL 蒸馏 (KD) L = T^2 * CE(p_T, q_T) | Hinton et al., Distilling the Knowledge in a Neural Network, 2015, arXiv:1503.02531 | demo/run_distill_minillm.py (train_forward_kl) |

### 复现命令

`ash
# FedBuff 缓冲异步聚合测试
python -m unittest tests.test_scheduler -v   # 15 项全绿

# MiniLLM 反向 KL + Hinton KD 蒸馏实验（合成数据，无需网络）
python demo/run_distill_minillm.py

# 用真实 MNIST 跑蒸馏
python demo/run_distill_minillm.py --data mnist
`
