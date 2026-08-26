# 云端真实 vLLM 链路验证记录 · hybrid 模式（2026-08-23 晚）

> 状态：✅ 端到端通过（request_mode=hybrid，timeout_ms=10000，真实 vLLM 复核）
> 在 cloud 模式验证之后新增的一条 **hybrid** 请求，使用全新 event_id/trace_id。

## 一、运行配置

| 项 | 值 |
|---|---|
| 边缘 commit | `ff83e2a fix(edge): 云端超时响应识别优先于 pending 状态检查`（=`ff83e2a91da1ea29d50b92fd3952396c0476b8bf`）|
| 边缘节点 | EDGE-W01-B02（ward=W-01, bed=B02） |
| 场景 | SCENARIO_PROFILE=fall_prediction（P1, conf=0.70） |
| 路由阈值 | ROUTER_EDGE_THRESHOLD=0.95（edge_score=0.40 < 0.95） |
| Hybrid 触发 | P1 且 conf=0.70 < 0.85 → 边缘+云端复核 |
| 云端超时 | ROUTER_CLOUD_TIMEOUT_S=10 → timeout_ms=**10000** |
| MQTT | 127.0.0.1:1884（SSH 隧道 → AutoDL mosquitto :1883） |
| 云端模型 | Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4（vLLM，gptq-int4）|

## 二、证据（本次新 ID）

### 2.1 核心 ID
- **event_id**: `8e7ebb98-72f8-4033-bf49-1b91cc81f45e`
- **trace_id**: `90027c87-ac74-4289-83d2-3ad377c7cfec`（请求/响应/云端日志/边端 SQLite 全程一致）
- 请求时间：2026-08-23 14:45:47.244Z；响应时间：14:45:47.770Z

### 2.2 MQTT 抓包（`capture-hybrid.jsonl`）
- 请求 `ward/W-01/node/EDGE-W01-B02/inference/request`：
  - `request_mode=hybrid, timeout_ms=10000`
  - `reason=P1事件置信度0.70<0.85，边缘+云端复核`
- 响应 `node/EDGE-W01-B02/inference/response`：
  - `judgment=confirm, confidence=0.85`（云端 LLM 将置信度从 0.70 复核提升至 0.85）
  - `latency_ms=532.5`（真实 vLLM 推理耗时）
  - `model_name=Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4, model_version=gptq-int4`
  - advice：`请立即检查患者状态，确认是否发生跌倒，并采取相应护理措施以确保患者安全。`

### 2.3 边缘日志（`edge-hybrid-real-vllm.log`）
```
[EDGE-W01-B02] 🔀 上报事件: fall_prediction [P1] conf=0.70 route=hybrid ttft=53ms
[EDGE-W01-B02] 收到消息: topic=node/EDGE-W01-B02/inference/response
[EDGE-W01-B02] 云端研判结果: event=8e7ebb98-72f8-4033-bf49-1b91cc81f45e, judgment=confirm, conf=0.85
[EDGE-W01-B02] 云端建议: 请立即检查患者状态，确认是否发生跌倒，并采取相应护理措施以确保患者安全。
```

### 2.4 云端 cloud-llm 日志（`cloud-llm-hybrid.log.snippet`）
```
request_validated  | event 8e7ebb98… | trace 90027c87… | request_mode hybrid | conf 0.70
inference_started  | mode vllm       | model Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4
HTTP Request: POST http://localhost:8501/v1/chat/completions "HTTP/1.1 200 OK"   ← 真实 vLLM 调用成功
inference_completed| judgment confirm | conf 0.85 | latency 532.5
response_published
```

### 2.5 边端 SQLite（`edge_EDGE-W01-B02.db`，safety_events）
- `event_id=8e7ebb98…, event_type=fall_prediction, priority=P1, state=notified, confidence=0.70, synced=1`
- `details.routing = {target: hybrid, reason: P1事件置信度0.70<0.85，边缘+云端复核, network_state: connected, edge_score: 0.4}`
- `details.cloud_inference = {status: completed, judgment: confirm, confidence: 0.85, latency_ms: 532.5, trace_id: 90027c87…}`

## 三、说明

1. hybrid 语义：边缘先基于本地规则/LLM 响应，同时将低置信度 P1 事件卸载给云端 14B 复核；响应中云端 confidence(0.85) 高于边缘原始 0.70，符合"复核提升"预期。
2. 本目录同时保留 cloud 模式证据（`验证记录.md`、`capture.jsonl`、`edge-real-vllm.log`、`cloud-llm-vllm.log.snippet`），未被本次 hybrid 运行覆盖。

## 四、本目录文件（hybrid 相关）

- `capture-hybrid.jsonl`：MQTT 抓包
- `edge-hybrid-real-vllm.log`：边缘日志
- `cloud-llm-hybrid.log.snippet`：云端 cloud-llm + vLLM 调用日志
- `验证记录-hybrid.md`：本文档
