# P7 云端 LLM 与前端指标契约（8/12-8/18）

负责人：P7 刘彦晗  
模块：`cloud-llm-service` / 护士站前端联调  
日期：2026-08-18  
分支：`feature/cloud-llm-p7` / PR #8

## 1. 契约边界

本文只定义 P7 云端 LLM 服务向前端可观测面提供的指标口径。护士站前端不直接消费 `cloud-llm-service` 的 MQTT request，而是通过以下路径拿到展示数据：

| 数据类型 | 生产方 | 中转/落库 | 前端来源 |
| --- | --- | --- | --- |
| 云端研判结果 | `cloud-llm-service` 发布 `node/{node_id}/inference/response` | `edge-agent` 合并到事件 details 后上报 `cloud-backend` | `/api/events`、WebSocket `safety_event` |
| 云端请求状态 | `edge-agent` pending/timeout tracker | `node_health.metrics.cloud_inference` | `/api/nodes`、WebSocket `node_health` |
| 云端 LLM 服务运行指标 | `cloud-llm-service` `/stats` | 联调/运维采集，可由后续 backend proxy 暴露 | `/stats` 原始字段或后续 `/api/llm/stats` |
| 护士站全局统计 | `cloud-backend` | MySQL 聚合 | `/api/stats` |

## 2. `cloud-llm-service` `/stats`

接口：

```text
GET http://<cloud-llm-service>:8004/stats
```

响应：

```json
{
  "code": 0,
  "data": {
    "broker": "localhost:1883",
    "uptime_seconds": 120.5,
    "total_requests": 10,
    "total_responses": 10,
    "total_duplicates": 2,
    "total_errors": 0,
    "pending_dedup": 8,
    "dedup_ttl_seconds": 300,
    "llm_mode": "mock"
  }
}
```

字段口径：

| 字段 | 类型 | 单位 | 前端建议展示 |
| --- | --- | --- | --- |
| `broker` | string | - | 运维面板显示当前 Broker |
| `uptime_seconds` | number | 秒 | 转换为运行时长 |
| `total_requests` | number | 次 | 云端实际推理次数，不含重复复用 |
| `total_responses` | number | 次 | MQTT response 成功发布次数 |
| `total_duplicates` | number | 次 | `event_id` 命中去重缓存次数 |
| `total_errors` | number | 次 | 请求校验、推理降级、发布失败等错误计数 |
| `pending_dedup` | number | 条 | 当前去重缓存内事件数 |
| `dedup_ttl_seconds` | number | 秒 | 去重窗口配置 |
| `llm_mode` | string | - | `mock` / `vllm`，用于演示标识 |

派生指标：

| 指标 | 公式 | 用途 |
| --- | --- | --- |
| `response_success_rate` | `total_responses / max(total_requests + total_duplicates, 1)` | 云端发布成功率 |
| `duplicate_rate` | `total_duplicates / max(total_requests + total_duplicates, 1)` | 重试/重复请求占比 |
| `error_rate` | `total_errors / max(total_requests + total_duplicates + total_errors, 1)` | 服务异常趋势 |

## 3. 事件 details 中的云端研判字段

`edge-agent` 收到云端 response 后，应把云端结果写入安全事件 details，供前端卡片、详情抽屉和趋势面板展示。

建议结构：

```json
{
  "route": "cloud",
  "cloud_latency_ms": 186.4,
  "cloud_inference": {
    "event_id": "evt-001",
    "trace_id": "trace-001",
    "judgment": "confirm",
    "confidence": 0.91,
    "advice": "请立即查看床位。",
    "latency_ms": 12.3,
    "model_name": "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4",
    "model_version": "gptq-int4",
    "resolved_at": "2026-08-18T08:00:02Z"
  }
}
```

前端展示规则：

| 字段 | 来源 | 展示位置 |
| --- | --- | --- |
| `details.route` | 边缘路由器 | 事件卡片 route 徽章：`edge` / `cloud` / `hybrid` |
| `details.cloud_latency_ms` | 边缘 pending resolve 耗时 | 事件卡片与详情抽屉的云端往返延迟 |
| `details.cloud_inference.judgment` | 云端 response | 详情抽屉研判结果 |
| `details.cloud_inference.status` / response `status` | 云端 response | `completed` 或 `timeout` 状态标识 |
| `details.cloud_inference.confidence` | 云端 response | 云端置信度 |
| `details.cloud_inference.advice` | 云端 response | 护理建议 |
| `details.cloud_inference.latency_ms` | 云端 response | 云端模型侧耗时 |
| `details.cloud_inference.model_name` | 云端 response | 模型名称 |
| `details.cloud_inference.model_version` | 云端 response | 模型版本 |
| `trace_id` / `details.cloud_inference.trace_id` | envelope / response | 链路回查、截图标注 |

兼容规则：

- 前端优先读 `details.cloud_inference.*`。
- 如果事件列表已扁平返回 `cloud_latency_ms`、`model_name`、`model_version`，前端可以直接展示；详情抽屉仍以 details 为准。
- 缺字段时显示 `-`，不得把字段缺失视为接口失败。

## 4. 云端 pending 与超时指标

边缘节点 health 建议携带：

```json
{
  "metrics": {
    "cloud_inference": {
      "pending": 1,
      "expired": 0,
      "resolved": 12,
      "timeout_s": 5.0
    }
  }
}
```

前端口径：

| 字段 | 类型 | 展示规则 |
| --- | --- | --- |
| `pending` | number | 大于 0 时显示云端等待中 |
| `expired` | number | 增长时显示云端超时/边缘回退 |
| `resolved` | number | 云端成功回传累计 |
| `timeout_s` | number | 展示或 tooltip 中说明超时阈值 |

当 `expired` 增长或事件 details 出现 `state_fallback=timeout` / `state_fallback=cloud_unavailable` 时，前端应展示“云端超时，边缘回退”类状态，而不是覆盖原始事件。

## 5. 结构化日志到前端问题定位

前端反馈某条云端研判异常时，P7 用以下字段回查日志：

| 前端可见字段 | 云端日志字段 | 相关 stage |
| --- | --- | --- |
| `event_id` | `event_id` / `envelope_event_id` | 全部关键 stage |
| `trace_id` | `trace_id` / `envelope_trace_id` | 全部关键 stage |
| 云端等待中 | `request_received`、`inference_started` | 判断请求是否到达云端 |
| 云端超时 | 缺少 `response_published` 或存在 `response_publish_failed` | 判断是否推理慢、发布失败或边缘超时 |
| 云端主动超时 | `inference_timeout` | 判断云端按请求 `timeout_ms` 主动降级并允许边缘回退 |
| 结果重复 | `duplicate_reused` | 判断边缘重试是否复用缓存 |
| 展示字段缺失 | `response_publishing.payload_bytes`、`response_published.message_id` | 判断 response envelope 是否成功发布 |

## 6. 前端验收清单

| 场景 | 输入 | 前端期望 |
| --- | --- | --- |
| 云端确认 | `judgment=confirm` | 详情显示云端模型、置信度、护理建议 |
| 云端驳回 | `judgment=reject` | 事件标识为误报/无需升级，保留原始 trace |
| 云端复核 | `judgment=escalate` | 展示人工复核提示 |
| 重复 request | 相同 `event_id` 新 `trace_id` | 前端只看到同一事件状态更新，不生成重复事件 |
| 云端超时 | pending 超过 `timeout_s` | 展示回退标识，事件仍可处置 |
| 服务错误 | `total_errors` 增长 | 运维指标显示错误数，业务卡片不崩溃 |

## 7. 与 P2/P7 对齐结论

- P7 保证云端 response payload 字段稳定：`event_id`、`trace_id`、`judgment`、`confidence`、`advice`、`latency_ms`、`model_name`、`model_version`。
- P2 前端只依赖字段存在与枚举值，不依赖中文日志文本。
- P1 边缘负责把云端 response 写回事件 details，并维护 pending/timeout 状态。
- 后续若增加 `/api/llm/stats` 聚合接口，字段应保持与本文 `/stats.data` 同名。
