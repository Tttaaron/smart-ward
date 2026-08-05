# MQTT 消息契约（联调唯一标准）

本目录定义智慧病房云边端协同系统中所有 MQTT 消息的 JSON Schema。
前后端、边缘端联调时，**以本目录为准**，不依赖代码注释或口头约定。

## 主题树（对齐方案书 §4.3）

```text
# ── 上行：边缘 -> 云端 ──
ward/{ward_id}/node/{node_id}/observation      # 多源观测数据（摄像头/床位/环境）
ward/{ward_id}/node/{node_id}/event             # 安全事件（跌倒/离床/呼叫）
ward/{ward_id}/node/{node_id}/health            # 节点健康心跳

# ── 下行：云端 -> 边缘 ──
ward/{ward_id}/alert/{event_id}/ack             # 告警确认/处置/升级
node/{node_id}/config/set                        # 节点配置下发
node/{node_id}/model/deploy                      # 模型版本下发（灰度）
node/{node_id}/model/rollback                    # 模型回滚

# ── 云边协同推理链路 ──
ward/{ward_id}/node/{node_id}/inference/request  # 边缘 -> 云端：推理请求
node/{node_id}/inference/response                # 云端 -> 边缘：推理响应

# ── 训练链路（与实时业务隔离）──
training/{job_id}/node/{node_id}/command        # 训练指令
training/{job_id}/node/{node_id}/update         # 梯度/权重上报
training/{job_id}/status                         # 训练任务状态
```

## 通用消息信封

**所有**消息必须包含以下字段（见 [envelope.json](envelope.json)）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `message_id` | string(uuid) | 消息唯一 ID，消费端按此去重 |
| `event_id` | string(uuid) \| null | 关联的事件 ID（非事件消息为 null） |
| `schema_version` | string | 契约版本，如 `v1` |
| `occurred_at` | string(iso8601) | 事件发生时间（UTC，Z 结尾） |
| `source` | string | 来源标识，如 `edge:EDGE-W01-B01` / `cloud` / `nurse-station` |
| `trace_id` | string | 跨服务追踪 ID，便于日志关联 |
| `payload` | object | 业务数据，结构见各消息 Schema |

## Schema 文件清单

| 文件 | 主题 | 用途 |
|---|---|---|
| `envelope.json` | （通用） | 通用消息信封，所有消息外层结构 |
| `observation.json` | `ward/+/node/+/observation` | 多源观测数据上报 |
| `safety_event.json` | `ward/+/node/+/event` | 安全事件上报（跌倒/离床/呼叫等） |
| `alert_ack.json` | `ward/+/alert/+/ack` | 告警确认/处置/升级指令 |
| `node_health.json` | `ward/+/node/+/health` | 节点健康心跳 |
| `model_deploy.json` | `node/+/model/deploy` | 模型版本下发 |
| `inference_request.json` | `ward/+/node/+/inference/request` | 云边协同推理请求（边缘 -> 云端） |
| `inference_response.json` | `node/+/inference/response` | 云边协同推理响应（云端 -> 边缘） |

## 云边协同推理契约（inference request/response）

- 请求主题：`ward/{ward_id}/node/{node_id}/inference/request`
- 响应主题：`node/{node_id}/inference/response`
- **外层信封与 payload 均携带 `event_id`、`trace_id`**；云端按 `event_id` 去重（重复 request 不重复执行），按 `trace_id` 校验响应来源（trace 不匹配不消费）
- 响应 payload **必须**包含 `event_id`、`trace_id`、`judgment`、`confidence`、`advice`、`latency_ms`，缺任一字段不得进入成功路径
- `judgment` 枚举：`confirm`（确认）/ `reject`（排除）/ `escalate`（升级）；非法值进入边缘失败回退，不得覆盖有效结果
- 云端响应幂等：重复 response / 未知 event / trace 不匹配均不导致边缘状态二次变更

## 事件类型与优先级（事件字典节选，完整版见 `docs/00-事件字典.md`）

| event_type | priority | 说明 |
|---|---|---|
| `fall_suspected` | P1 | 疑似跌倒 |
| `nurse_call` | P1 | 护士呼叫按钮触发 |
| `bed_leave` | P2 | 持续离床超阈值 |
| `door_departure` | P2 | 门区异常离开 |
| `night_wandering` | P2 | 夜间徘徊 |
| `environment_anomaly` | P3 | 环境异常（温湿度/光照/空气质量） |
| `node_offline` | P3 | 节点失联 |

## 事件状态机

```text
new -> notified -> acknowledged -> resolved
                                  -> false_positive
                                  -> escalated
```

- `new`：边缘端新生成事件
- `notified`：已推送到护士站
- `acknowledged`：护士已确认（开始处置）
- `resolved`：已处置完成
- `false_positive`：误报，关闭事件
- `escalated`：升级，转更高优先级处置

## QoS 与幂等

- 所有消息 QoS = 1（至少一次），消费端按 `message_id` 去重
- 边缘端按本地序号补传断网期间事件
- 所有时间使用 UTC（ISO 8601，`Z` 结尾），前端转本地时区显示

## 版本管理

- `schema_version` 字段标识消息版本，当前为 `v1`
- 契约变更需同步更新本目录 Schema 文件、`docs/01-MQTT契约.md` 与代码中的校验逻辑
- 破坏性变更（删字段/改类型）需升版本号并保留旧版本兼容期
