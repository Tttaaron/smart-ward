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

## 五、验收证据

- 训练日志：数据版本、参数、模型哈希、聚合版本
- 版本表：本文件 + 注册记录
- 发布/回滚记录：release_log 输出
- 边缘 health 确认记录：health_summary 输出

## 六、代码位置

- 版本登记/发布/回滚：app/model_registry.py
- 聚合版本生成：app/scheduler.py (TrainingScheduler.aggregate)
- 测试：tests/test_scheduler.py (ModelRegistryTest)
