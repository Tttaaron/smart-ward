# P7 云端 LLM 服务联调 Runbook（8/12-8/18）

负责人：P7 刘彦晗  
模块：`cloud-llm-service`  
日期：2026-08-18  
分支：`feature/cloud-llm-p7` / PR #8

## 1. 联调目标

本 runbook 用于 8/12-8/18 阶段的云边协同推理联调，确认 `cloud-llm-service` 可以：

- 订阅 `ward/{ward_id}/node/{node_id}/inference/request`。
- 校验 MQTT envelope 与 `InferenceRequest` payload。
- 调用 mock 或 vLLM adapter 生成 `InferenceResponse`。
- 发布 `node/{node_id}/inference/response`。
- 对重复 `event_id` 复用缓存结果，并使用新的 `trace_id` 回传。
- 输出可按 `stage + event_id + trace_id` 检索的结构化日志。

## 2. 启动前检查

| 项目 | 命令/位置 | 期望 |
| --- | --- | --- |
| Python 依赖 | `cloud-llm-service/requirements.txt` | `paho-mqtt`、`fastapi`、`uvicorn`、`pydantic`、`httpx` 已安装 |
| MQTT Broker | `MQTT_BROKER` / `MQTT_PORT` | 默认 `localhost:1883` 可连接 |
| LLM 模式 | `LLM_MODE` | `mock` 用于离线闭环，`vllm` 用于真实模型 |
| 去重窗口 | `CLOUD_DEDUP_TTL_SECONDS` | 默认 300 秒 |
| 调试接口 | `GET /health`、`GET /stats`、`POST /infer` | FastAPI 可访问 |

本地 mock 模式：

```powershell
cd D:\smart-ward-repo\cloud-llm-service
$env:LLM_MODE="mock"
$env:MQTT_BROKER="localhost"
$env:MQTT_PORT="1883"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8004
```

真实 vLLM 模式：

```powershell
cd D:\smart-ward-repo\cloud-llm-service
$env:LLM_MODE="vllm"
$env:VLLM_ENDPOINT="http://<P6-vllm-host>:8501/v1/chat/completions"
$env:CLOUD_LLM_MODEL_NAME="Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4"
$env:CLOUD_LLM_MODEL_VERSION="gptq-int4"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

## 3. MQTT 契约

### 3.1 请求主题

```text
ward/{ward_id}/node/{node_id}/inference/request
```

请求 envelope 中必须保留 `event_id` 与 `trace_id`。如果 payload 缺少 `node_id` 或 `ward_id`，云端会从 topic 中补齐。

最小请求：

```json
{
  "message_id": "msg-001",
  "event_id": "evt-001",
  "trace_id": "trace-001",
  "schema_version": "v1",
  "occurred_at": "2026-08-18T08:00:00Z",
  "source": "edge:EDGE-W01-B01",
  "payload": {
    "event_id": "evt-001",
    "trace_id": "trace-001",
    "event_type": "fall_suspected",
    "priority": "P1",
    "confidence": 0.9,
    "ward_id": "W-01",
    "node_id": "EDGE-W01-B01",
    "bed_id": "B01",
    "request_mode": "cloud",
    "timeout_ms": 30000,
    "details": {}
  }
}
```

### 3.2 响应主题

```text
node/{node_id}/inference/response
```

响应 payload：

```json
{
  "event_id": "evt-001",
  "trace_id": "trace-001",
  "judgment": "confirm",
  "confidence": 0.91,
  "advice": "请立即查看床位。",
  "latency_ms": 12.3,
  "model_name": "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4",
  "model_version": "gptq-int4"
}
```

`judgment` 只允许 `confirm`、`reject`、`escalate`。

## 4. 结构化日志检查点

日志统一前缀为 `cloud_inference`，正文为 JSON。联调时按 `event_id`、`trace_id`、`stage` 过滤即可串联全链路。

| stage | 触发点 | 关键字段 |
| --- | --- | --- |
| `request_received` | 收到 MQTT 消息 | `topic`、`payload_bytes`、`mqtt_qos`、`mqtt_dup`、`mqtt_mid` |
| `request_validated` | envelope 与 payload 通过校验 | `message_id`、`event_id`、`trace_id`、`node_id`、`ward_id`、`event_type`、`priority`、`request_mode`、`timeout_ms` |
| `request_invalid` | JSON/envelope/payload 校验失败 | `reason`、`error_type` 或 `validation_errors`、`topic`、`payload_bytes` |
| `duplicate_reused` | 命中 `event_id` 去重缓存 | `old_trace_id`、`cache_age_ms`、`cache_ttl_seconds`、`response_node_id` |
| `inference_started` | 开始调用 LLM adapter | `mode`、`model_name`、`model_version`、`event_type`、`priority` |
| `inference_completed` | adapter 返回并完成响应校验 | `judgment`、`confidence`、`latency_ms`、`handler_latency_ms`、`total_request_latency_ms` |
| `response_publishing` | 发布前生成 response envelope | `topic`、`message_id`、`qos`、`payload_bytes`、`judgment` |
| `response_published` | MQTT publish 返回成功 | `publish_rc`、`publish_mid`、`topic`、`payload_bytes` |
| `response_publish_failed` | 缺少 node、响应非法、publish 异常或 rc 非 0 | `reason`、`publish_rc`、`validation_errors` 或 `error_type` |

## 5. 联调场景

| 场景 | 操作 | 期望 |
| --- | --- | --- |
| 正常云端确认 | 发送 P1、高置信度 `fall_suspected` | 出现 `request_received -> request_validated -> inference_started -> inference_completed -> response_publishing -> response_published` |
| 低置信度误报 | 发送 confidence `<0.3` | mock 返回 `reject`，边缘不得升级为真实告警 |
| 中等置信度复核 | 发送 confidence `0.3-0.7` | mock 返回 `escalate`，前端展示人工复核 |
| 重复 request | 使用相同 `event_id`、新 `trace_id` 重发 | 只调用一次模型，第二次出现 `duplicate_reused` 并使用新 `trace_id` 回传 |
| 缺少 event_id | 删除 envelope/payload 中的 `event_id` | 出现 `request_invalid`，不发布 response |
| 缺少 node_id | topic 无法解析且 payload 无 `node_id` | 出现 `response_publish_failed`，`reason=missing_node_id` |
| MQTT publish 失败 | Broker 断开后发送 | 出现 `response_publish_failed`，边缘侧应走 pending 超时回退 |

## 6. 验证命令

```powershell
cd D:\smart-ward-repo\cloud-llm-service
python -m unittest discover -s tests
```

当前单元测试覆盖 13 项：

- mock LLM 三类判定。
- LLM 输出字段与解析降级。
- request/response/envelope schema。
- 正常 MQTT request 发布 response。
- 重复 request 复用缓存并更新 `trace_id`。
- 缺少 `event_id` 时拒绝消费。

## 7. 交付注意事项

- mock 模式是接口闭环证据，不代表 P6 真实 14B/vLLM 性能。
- 真实联调截图或日志必须记录 `trace_id`，便于 P1 边缘、P2 前端、P7 云端三方对账。
- PR #8 合并前至少保留一次 13 项测试全绿记录。
