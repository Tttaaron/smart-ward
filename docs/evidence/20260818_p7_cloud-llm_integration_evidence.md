# 真实 MQTT Broker 云边协同联调验证记录

> 时间：2026-08-18
> 环境：本机（Windows），真实 MQTT Broker（amqtt 0.11.4，纯 Python，完整实现 MQTT 3.1.1 / QoS 1）
> 组件版本：
> - 代码基线：`feature/cloud-llm-p7` @ `efcf757`；本工作区另有 HYBRID `review -> hybrid` 修复未提交变更
> - 对照分支：`master` @ `bdd6160`
> - 云端 LLM：`LLM_MODE=mock`（链路验证阶段）

---

## 一、验证目标

验证云边协同推理完整闭环：边端事件 → TaskRouter 路由 → 推理请求 → 云端二次研判 → 响应回传 → 边端 SQLite 状态回写，并以 event_id/trace_id 全程关联。

## 二、验证结果总览

| 路由 | 测试事件 | 结果 | SQLite 回写 |
|------|---------|------|------------|
| **CLOUD**（纯云端卸载） | `seizure`（P1, conf=0.85） | ✅ 通过 | state=notified, status=completed |
| **HYBRID**（边缘+云端复核） | `fall_prediction`（P1, conf=0.70） | ✅ 通过（修复后） | state=notified, status=completed |

## 三、CLOUD 路径完整链路（以 event 05d6e526 为例）

```
① 事件上报   ward/W-01/node/EDGE-W01-B01/event          conf=0.85  trace=1914d9b0…
② 推理请求   ward/.../inference/request  mode=cloud    conf=0.85  trace=d868b914…
③ 云端响应   node/EDGE-W01-B01/inference/response       confirm    trace=d868b914…  ← 与②同一条 trace
④ 回写上报   ward/.../event（云端结果合并后重新上报）               trace=c2d1aefc…
```

云端侧（cloud-llm-service 追踪日志，trace_id 全程一致）：
```
request_received → request_validated(request_mode=cloud)
→ inference_started(mode=mock) → inference_completed(judgment=confirm, latency_ms=0.1)
→ dedup_cache_stored(ttl=300s) → response_publishing → response_published
```

SQLite（`edge_EDGE-W01-B01.db` safety_events）：
```
event_id=05d6e526…  state=notified  synced=1
details.routing.target = cloud
details.cloud_inference = { status: completed, judgment: confirm, confidence: 0.85, latency_ms: 0.1 }
```

## 四、HYBRID 路径完整链路（以 event 2fe0ce5c 为例）

```
① 事件上报   ward/.../event                          conf=0.70  trace=c7b92b4a…
② 推理请求   ward/.../inference/request  mode=hybrid conf=0.70  trace=03f1d5c7…
③ 云端响应   node/EDGE-W01-B01/inference/response    confirm    trace=03f1d5c7…  ← 与②同一条 trace
```

云端侧：`request_validated(request_mode=hybrid) → inference_completed(judgment=confirm)`
SQLite：`state=notified`、`cloud_inference.status=completed`、`routing.target=hybrid`

## 五、联调发现的问题与修复（重要）

**问题**：HYBRID 路径请求被云端丢弃，边端超时回退 `fallback_edge`。

**根因**：边端 `edge-agent/src/main.py` 对 HYBRID 路由把请求标为
`request_mode="review"`，但云端 `cloud-llm-service/app/schemas.py` 的枚举是
`RequestMode = Literal["cloud", "hybrid"]`（契约 `contracts/inference_request.json`
同样只列 `["cloud", "hybrid"]`）。pydantic 校验失败 → 请求静默丢弃 → 无响应 → 边端超时回退。

**修复**（`edge-agent/src/main.py`，当前工作区已修复，待随 P7/P1 联调提交）：
```diff
- "mode": "review",   # 复核模式
+ "mode": "hybrid",   # 对齐 contracts 的 request_mode 枚举
- cloud_mode = "review"
+ cloud_mode = "hybrid"
```

**修复后复测**：云端日志出现 `request_mode:"hybrid" → validated → completed(confirm)`，
SQLite 回写正常；当前 checkout 的 edge-agent 测试为 86 项通过（7 项环境相关跳过）。

> ⚠️ 需要与你确认：云端 `RequestMode` 枚举当前只接受 `cloud/hybrid`。
> 若后续希望区分"纯云端卸载"与"混合复核"两种语义，建议明确是否在契约中增加
> 第三种枚举值（如 `review`），并同步 edge/cloud 两端——当前统一用 `hybrid` 标识复核请求。

## 六、复现方法（可在真实 broker 环境执行）

```bash
# 1. 启动 broker + cloud-llm-service（LLM_MODE=mock）
# 2. 启动边端，触发 CLOUD：
export SCENARIO_PROFILE=seizure        # P1 conf=0.85 → route=cloud
#    触发 HYBRID：
export SCENARIO_PROFILE=fall_prediction  # P1 conf=0.70 → route=hybrid

# 3. 抓包两个主题：
mosquitto_sub -h <broker> -p <port> -t "ward/+/node/+/inference/request" -v
mosquitto_sub -h <broker> -p <port> -t "node/+/inference/response" -v

# 4. 验证 SQLite 回写（进边端容器）：
docker exec edge-bed-01 python -c "
import sqlite3, json
db = sqlite3.connect('/app/data/edge_EDGE-W01-B01.db')
for r in db.execute(\"SELECT event_id,event_type,state,payload FROM safety_events ORDER BY rowid DESC LIMIT 3\"):
    ci = json.loads(r[3]).get('details',{}).get('cloud_inference',{})
    print(r[0], r[1], 'state='+r[2], 'status='+str(ci.get('status')), 'judgment='+str(ci.get('judgment')))
"
```

**成功判据**：① 请求/响应 trace_id 一致；② 响应 judgment ∈ {confirm,reject,escalate}；
③ SQLite 中该 event 的 `state` 变为 notified/false_positive/escalated，且 `details.cloud_inference.status=completed`。

## 七、避坑提示（路由预期）

以下事件**不会卸载云端**，联调时勿用作 cloud 测试事件（得分 ≥ 阈值 0.65，留在边缘）：
- `environment_anomaly`（conf=0.95, score=0.68）
- `device_fault`（conf=0.85, score=0.655）
- `nurse_call`（conf=1.0, score=0.73）

## 八、证据文件

联调原始日志与抓包已归档到仓库：
- `docs/evidence/20260818_p7_cloud-llm_mqtt-capture.jsonl`：完整 MQTT 抓包
- `docs/evidence/20260818_p7_cloud-llm_edge.log`：边端日志
- `docs/evidence/20260818_p7_cloud-llm_cloud.log`：云端追踪日志（含修复前后对比）
- 本记录：`docs/evidence/20260818_p7_cloud-llm_integration_evidence.md`
