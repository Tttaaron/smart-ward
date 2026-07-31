# MQTT 消息契约规范

> 本文档是智慧病房云边端 MQTT 通信的**接口层唯一标准**。
> 与 `contracts/` 目录下的 JSON Schema 一一对应，代码实现必须遵循。

## 1. 主题树（对齐方案书 §4.3）

```text
# ── 上行：边缘端 -> 云端 ──
ward/{ward_id}/node/{node_id}/observation      多源观测数据
ward/{ward_id}/node/{node_id}/event             安全事件
ward/{ward_id}/node/{node_id}/health            节点健康心跳
ward/{ward_id}/node/{node_id}/inference/request  云边协同推理请求

# ── 下行：云端 -> 边缘端 ──
ward/{ward_id}/alert/{event_id}/ack             告警确认/处置/升级指令
node/{node_id}/config/set                        节点配置下发（环境控制：ac/light/fresh_air on/off）
node/{node_id}/model/deploy                      模型版本下发（灰度）
node/{node_id}/model/rollback                    模型回滚
node/{node_id}/inference/response                云端推理结果回传

# ── 训练链路（与实时业务隔离）──
training/{job_id}/node/{node_id}/command         训练指令
training/{job_id}/node/{node_id}/update           梯度/权重上报
training/{job_id}/status                          训练任务状态
```

## 2. 通用消息信封（envelope）

**所有**消息外层必须符合 `contracts/envelope.json`：

```json
{
  "message_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_id": "660e8400-e29b-41d4-a716-446655440001",
  "schema_version": "v1",
  "occurred_at": "2026-07-21T08:30:00Z",
  "source": "edge:EDGE-W01-B01",
  "trace_id": "770e8400-e29b-41d4-a716-446655440002",
  "payload": { ... }
}
```

| 字段 | 说明 |
|---|---|
| `message_id` | 消息唯一 ID，消费端按此去重 |
| `event_id` | 关联事件 ID；非事件消息（observation/health）为 `null` |
| `schema_version` | 契约版本，当前 `v1` |
| `occurred_at` | 事件发生时间（UTC ISO 8601，`Z` 结尾） |
| `source` | 来源标识，如 `edge:EDGE-W01-B01` / `cloud` / `nurse-station` |
| `trace_id` | 跨服务追踪 ID |
| `payload` | 业务数据，结构见各消息 Schema |

## 3. 消息示例

### 3.1 observation（观测数据）

主题：`ward/W-01/node/EDGE-W01-B01/observation`

```json
{
  "message_id": "...",
  "event_id": null,
  "schema_version": "v1",
  "occurred_at": "2026-07-21T08:30:00Z",
  "source": "edge:EDGE-W01-B01",
  "trace_id": "...",
  "payload": {
    "ward_id": "W-01",
    "node_id": "EDGE-W01-B01",
    "bed_id": "B01",
    "timestamp": "2026-07-21T08:30:00Z",
    "sources": [
      {
        "source_type": "camera",
        "data": {
          "presence": true,
          "person_count": 1,
          "posture": "sitting",
          "fall_score": 0.0
        },
        "quality": {"confidence": 0.95, "latency_ms": 45, "degraded": false}
      },
      {
        "source_type": "bed_sensor",
        "data": {"occupied": true, "bed_state": "occupied", "absence_seconds": 0},
        "quality": {"confidence": 0.98, "latency_ms": 8, "degraded": false}
      }
    ]
  }
}
```

### 3.2 event（安全事件）

主题：`ward/W-01/node/EDGE-W01-B01/event`

```json
{
  "message_id": "...",
  "event_id": "660e8400-...",
  "schema_version": "v1",
  "occurred_at": "2026-07-21T08:30:05Z",
  "source": "edge:EDGE-W01-B01",
  "trace_id": "...",
  "payload": {
    "event_id": "660e8400-...",
    "ward_id": "W-01",
    "node_id": "EDGE-W01-B01",
    "bed_id": "B01",
    "event_type": "fall_suspected",
    "priority": "P1",
    "state": "new",
    "occurred_at": "2026-07-21T08:30:05Z",
    "detected_at": "2026-07-21T08:30:06Z",
    "confidence": 0.85,
    "model": {
      "model_name": "rule-fusion-v1",
      "model_version": "0.1.0-mock",
      "inference_ms": 5
    },
    "evidence_refs": [],
    "rule_hits": ["posture=falling", "fall_score=0.85>0.5"],
    "details": {"posture": "falling", "fall_score": 0.85}
  }
}
```

### 3.3 health（节点健康）

主题：`ward/W-01/node/EDGE-W01-B01/health`

```json
{
  "payload": {
    "node_id": "EDGE-W01-B01",
    "ward_id": "W-01",
    "status": "online",
    "timestamp": "2026-07-21T08:30:00Z",
    "metrics": {"buffered_events": 0},
    "model_version": "0.1.0-mock",
    "buffered_events": 0
  }
}
```

### 3.4 alert/ack（告警确认指令）

主题：`ward/W-01/alert/660e8400-.../ack`

```json
{
  "payload": {
    "event_id": "660e8400-...",
    "ward_id": "W-01",
    "action": "acknowledge",
    "operator": {
      "id": "nurse-demo",
      "name": "演示护士",
      "role": "nurse"
    },
    "occurred_at": "2026-07-21T08:31:00Z"
  }
}
```

### 3.5 inference/request 与 inference/response（云边协同推理）

推理请求和响应沿用通用 envelope，并且必须在 envelope 与 payload 中保留 `event_id`、`trace_id`，用于 pending 生命周期、超时回退和重复响应幂等处理。

请求主题：`ward/{ward_id}/node/{node_id}/inference/request`

```json
{
  "event_id": "660e8400-...",
  "trace_id": "770e8400-...",
  "payload": {
    "event_id": "660e8400-...",
    "trace_id": "770e8400-...",
    "event": {"event_type": "fall_suspected", "priority": "P1", "confidence": 0.72},
    "observations": [],
    "model_name": "qwen2.5-14b-instruct"
  }
}
```

响应主题：`node/{node_id}/inference/response`

```json
{
  "event_id": "660e8400-...",
  "trace_id": "770e8400-...",
  "payload": {
    "event_id": "660e8400-...",
    "trace_id": "770e8400-...",
    "judgment": "confirm",
    "confidence": 0.94,
    "advice": "立即确认患者状态并通知责任护士",
    "latency_ms": 186,
    "model_name": "qwen2.5-14b-instruct",
    "model_version": "cloud-v1"
  }
}
```

`judgment` 只允许 `confirm`、`reject`、`escalate`。边缘端收到重复响应、未知事件或 trace 不匹配响应时不得重复修改本地状态。

## 4. QoS 与可靠性

| 配置项 | 值 | 说明 |
|---|---|---|
| QoS | 1 | 至少一次，消费端按 `message_id` 去重 |
| retained | false | 不使用保留消息（health 用周期心跳替代） |
| 幂等键 | `message_id` / `event_id` | 云端按此去重 |
| 时间格式 | UTC ISO 8601 | `Z` 结尾，前端转本地时区显示 |
| 断网补传 | 边缘端 SQLite 缓存 | 恢复后按序号补传，标记 `synced=1` |

## 5. 订阅清单（cloud-backend）

| 通配主题 | QoS | 处理器 |
|---|---|---|
| `ward/+/node/+/observation` | 1 | `MqttHandler._handle_observation` |
| `ward/+/node/+/event` | 1 | `MqttHandler._handle_event` |
| `ward/+/node/+/health` | 1 | `MqttHandler._handle_health` |
| `ward/+/alert/+/ack` | 1 | `MqttHandler._handle_ack` |
| `ward/+/node/+/inference/request` | 1 | `cloud-llm-service` consumer |

## 6. 订阅清单（edge-agent）

| 通配主题 | QoS | 处理器 |
|---|---|---|
| `ward/{ward_id}/alert/+/ack` | 1 | `EdgeAgent.handle_ack` |
| `node/{node_id}/config/set` | 1 | `EdgeAgent.handle_config` |
| `node/{node_id}/model/deploy` | 1 | `EdgeAgent.handle_model_deploy` |
| `node/{node_id}/model/rollback` | 1 | `EdgeAgent.handle_model_deploy` |
| `node/{node_id}/inference/response` | 1 | `EdgeAgent.handle_inference_response` |

## 7. 安全配置（演示阶段）

当前 `mqtt-broker/mosquitto.conf` 配置 `allow_anonymous true`，仅用于演示。
接入真实病房前必须启用：
- 账号密码认证
- ACL 主题权限（限制每个节点只能发布自己的主题）
- TLS 加密
