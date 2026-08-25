# P7 真实 vLLM/14B MQTT 验收

## 运行版本

- 云端 `cloud-llm-service`：`5801d19`
- 云端实例：AutoDL `:8005`
- 运行模式：`LLM_MODE=vllm`
- 模型：`Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4`
- 模型版本：`gptq-int4`
- 边缘 `edge-agent`：`ff83e2a`
- MQTT：边缘本地 `127.0.0.1:1884` 经 SSH 隧道连接 AutoDL Broker `:1883`
- `/ready`：`status=ready`，backend `mode=vllm`

## CLOUD

- `event_id`: `78012aed-11fa-431a-910c-975eaf1ac7de`
- `trace_id`: `26982926-911f-4e1e-a1d5-822bf5b4665e`
- `request_mode`: `cloud`
- `timeout_ms`: `10000`
- vLLM HTTP：`200 OK`
- 结果：`judgment=confirm`，`confidence=0.85`
- 推理延迟：`390.5 ms`
- 响应：`status=completed`
- SQLite：`state=notified`，`synced=1`

## HYBRID

- `event_id`: `7d3d4414-3b12-4063-9dac-7adee39f67c7`
- `trace_id`: `209a79c4-5bc4-45d1-a7ea-83a72d521936`
- `request_mode`: `hybrid`
- `timeout_ms`: `10000`
- vLLM HTTP：`200 OK`
- 结果：`judgment=confirm`，云端 `confidence=0.85`
- 推理延迟：`545.4 ms`
- 响应：`status=completed`
- SQLite：`state=notified`，`synced=1`

## 云端阶段日志

两条请求均有以下阶段，且每个阶段带有对应的 `event_id` 和 `trace_id`：

```text
request_validated
inference_started (mode=vllm)
inference_completed
response_publishing
response_published (publish_rc=0, qos=1)
```

## 证据文件

本目录包含本次统一 `5801d19` 实例产生的原始材料：

- `capture-cloud.jsonl`
- `capture-hybrid.jsonl`
- `cloud-llm-5801.log.snippet`
- `edge-cloud-5801.log`
- `edge-hybrid-5801.log`
- `edge_EDGE-W01-B02.db`
- `capture_mqtt.py`
- P1 验证记录（原始文件名可能因来源系统编码显示异常）

## 结论

真实 vLLM/14B 的 CLOUD 与 HYBRID MQTT 云边链路均通过。请求、云端推理、MQTT response、边缘状态更新和 SQLite 回写可由同一组 `event_id/trace_id` 关联。此前由旧 `8004` 实例产生的记录不作为本次最终证据。
