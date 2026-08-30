# P7 阶段交付索引（截至 2026-08-19）

负责人：P7 刘彦晗  
分支：`feature/cloud-llm-p7`  
代码基线：`efcf757`；当前工作区包含 HYBRID `review -> hybrid` 修复及回归测试

## 已交付

| 交付物 | 位置 | 状态 |
| --- | --- | --- |
| 云端服务入口、健康检查、调试接口 | `cloud-llm-service/app/main.py` | 已完成 |
| MQTT request/response、字段校验、幂等 | `cloud-llm-service/app/mqtt_handler.py`、`schemas.py` | 已完成 |
| mock/vLLM adapter | `cloud-llm-service/app/llm_client.py` | mock 已验证，vLLM 接口已预留 |
| 云端单元测试 | `cloud-llm-service/tests/test_service.py` | 14 项通过 |
| 边缘 HYBRID 契约修复 | `edge-agent/src/main.py` | 已修复，待提交并与 P1 联调 |
| 边缘回归测试 | `edge-agent/tests/test_cloud_timeout_worker.py` | 86 项通过（7 项环境跳过） |
| 联调运行手册 | `20260818_p7_cloud-llm_integration_runbook.md` | 已完成 |
| P2 字段与指标说明 | `20260818_p7_frontend_metrics_contract.md` | 已完成 |
| CLOUD/HYBRID 原始联调证据 | `20260818_p7_cloud-llm_integration_evidence.md` 及同前缀日志/抓包 | 已归档，LLM_MODE=mock |

## 当前限制

- 尚无真实 Qwen2.5-14B/vLLM endpoint、模型资源和性能数据；不能宣称真实模型验收完成。
- 云端已补齐按请求 `timeout_ms` 的服务端 deadline：超时记录 `inference_timeout`，发布 `judgment=escalate,status=timeout` 降级 response，并保留边缘 pending/timeout 回退。
- P6 提到的 RTX 4090 可部署 Qwen2.5-1.5B，只能作为 GPU/vLLM 基础设施 smoke test；若作为最终云端模型，需由 P3/P5 明确接受其替代 14B 的验收口径，并补模型版本与指标说明。
- P6 已确认 Broker 使用服务器 `IP:1884`，Compose 启动命令为 `docker compose up --build`，日志命令为 `docker compose logs -f cloud-llm-service`。
- P6 当前 clone 的 `master` 尚未包含 PR #8；联调必须先统一到 PR #8 分支，或等待 PR #8 合并后再以统一 master 重跑。
- 已归档原始日志包含正常和校验失败记录；重复 request、trace 不匹配、未知事件、发布失败/云端不可用仍需补充独立异常证据。
- `docs/temp-evidence/` 仍保留未跟踪原始副本，提交前需由 P3 决定保留、移入归档或清理。

## 联动清单

- P1：合入 HYBRID 契约修复；使用同一提交重跑 CLOUD/HYBRID、重复 response、trace 不匹配、超时回退和 SQLite 状态回写。
- P2：按 `20260818_p7_frontend_metrics_contract.md` 接收 `cloud_inference`、`cloud_latency_ms`、pending/timeout 字段，补一条前端可见链路证据。
- P6：按服务器 `IP:1884` 和 `docker compose up --build` 提供环境；当前先用 mock，后续部署 vLLM 后补 endpoint、健康检查和真实模型证据。
- P5：统一云端延迟、成功率、异常样本统计口径，纳入三路线评测。
- P3：更新验收矩阵、PR #8 描述和 master/feature 合并记录，引用本目录证据。

## PR 与真实模型核对

- 当前本地 refs：`feature/cloud-llm-p7 @ efcf757`，`master @ bdd6160`；本地没有 PR #8 合并提交，无法仅凭仓库确认外部 PR 的 review/merge 状态。
- 当前正式归档的 CLOUD/HYBRID 原始日志标记 `LLM_MODE=mock`，仓库内没有先伟提供的真实 14B/vLLM e2e 原始证据或 commit 引用；该证据需要 P5 提供运行 commit、endpoint/模型版本和日志路径后才能核对是否与 PR #8 一致。
