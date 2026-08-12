# P7 云端 LLM 服务 8/1-8/11 补交记录

负责人：P7 刘彦晗  
模块：cloud-llm-service  
日期：2026-08-11

## 1. 任务冻结与接口确认（8/1-8/3）

| 项目 | 当前结论 | 证据位置 |
| --- | --- | --- |
| 请求主题 | `ward/{ward_id}/node/{node_id}/inference/request` | `cloud-llm-service/app/mqtt_handler.py` |
| 响应主题 | `node/{node_id}/inference/response` | `cloud-llm-service/app/mqtt_handler.py` |
| 必填响应字段 | `event_id`、`trace_id`、`judgment`、`confidence`、`advice`、`latency_ms`、`model_name`、`model_version` | `cloud-llm-service/app/schemas.py` |
| judgment 枚举 | `confirm` / `reject` / `escalate` | `cloud-llm-service/app/schemas.py` |
| 调试接口 | `GET /health`、`GET /stats`、`POST /infer` | `cloud-llm-service/app/main.py` |

## 2. 最小云端服务闭环（8/4-8/7）

已完成：

- FastAPI 服务入口可导入。
- mock LLM adapter 可返回符合契约的 response。
- vLLM adapter 保留 OpenAI-compatible `/v1/chat/completions` 接入方式。
- 服务启动时自动连接 MQTT Broker 并订阅 request topic。
- `/infer` 可用于绕过 MQTT 的本地调试。

本地验证命令：

```powershell
cd D:\smart-ward-master\cloud-llm-service
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8004
```

当前测试结果：

```text
Ran 13 tests in 0.002s
OK
```

## 3. 云边真实联调准备（8/8-8/11）

已补齐的云端侧逻辑：

| 场景 | 云端处理规则 | 验证方式 |
| --- | --- | --- |
| 正常 request | 调用 mock/vLLM，发布 response | `TestCloudMqttHandler.test_normal_request_publishes_response` |
| 重复 request | 按 `event_id` 复用缓存结果，不重复执行模型 | `TestCloudMqttHandler.test_duplicate_request_reuses_cached_result_with_new_trace` |
| 新 trace 重试 | 复用缓存结果，并用新的 `trace_id` 回传，避免边缘 pending 超时 | 同上 |
| 缺少 event_id | 拒绝消费，不发布 response，记录 error | `TestCloudMqttHandler.test_invalid_request_missing_event_id_is_rejected` |
| 非法 judgment | response schema 拒绝非法枚举 | `TestSchemas.test_inference_response_rejects_invalid_judgment` |
| 模型输出异常 | 降级为 `escalate`，要求人工复核 | `TestLLMClient.test_parse_invalid_llm_output_falls_back_to_valid_judgment` |

## 4. 与 P1/P6 联调时需要补的原始证据

请在真实 Broker 联调时补齐下面内容：

| 场景 | trace_id | 命令/操作 | 云端日志 | 边缘日志 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 正常云端确认 | 待填 | 待填 | 待填 | 待填 | 待填 |
| 重复 request | 待填 | 待填 | 待填 | 待填 | 待填 |
| 云端不可用/超时 | 待填 | 待填 | 待填 | 待填 | 待填 |
| 非法 judgment 注入 | 待填 | 待填 | 待填 | 待填 | 待填 |
| trace 不匹配 | 待填 | 待填 | 待填 | 待填 | 待填 |
| 未知 event | 待填 | 待填 | 待填 | 待填 | 待填 |

## 5. mock 到真实 vLLM 的切换说明

mock 模式：

```powershell
$env:LLM_MODE="mock"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

vLLM 模式：

```powershell
$env:LLM_MODE="vllm"
$env:VLLM_ENDPOINT="http://<P6提供的云端地址>:8501/v1/chat/completions"
$env:CLOUD_LLM_MODEL_NAME="Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4"
$env:CLOUD_LLM_MODEL_VERSION="gptq-int4"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

如果 14B/vLLM 环境未就绪，最终材料必须注明：当前闭环使用接口一致的 mock adapter；真实模型接入依赖 P6 提供 vLLM endpoint。
