# P1 边缘端验证——六项证据确认

> 时间：2026-08-22 晚 ｜ 场景：CLOUD 正常 / HYBRID 正常 / CLOUD 超时(timeout_ms=500)
> Broker：127.0.0.1:1883（amqtt）｜ 云端 LLM：mock（模型 Qwen/Qwen2.5-14B 名义）

## ① 实际运行的 commit

| 角色 | commit | 说明 |
|------|--------|------|
| 云端 | `5801d19` | P6/P7 指定（含慢 adapter `MOCK_INFERENCE_DELAY_MS` 与 `inference_timeout` 检测）|
| 边端 阶段4/5 | `5801d19` | 按 P6/P7 钉版运行 |
| 边端 阶段6 | `70185a8` | 分支 `p1/edge-timeout-fix` = 5801d19 + status=timeout 识别 |
| master HEAD | `ff83e2a91da1ea29d50b92fd3952396c0476b8bf` | 含以上全部修复 |

## ② 工作区状态

```
## master...origin/master [ahead 3]
?? docs/temp-evidence/    （原始证据目录，按协议不提交）
```

无未提交的代码改动。Python 3.12.13（独立 anaconda 环境，无 cloud-llm venv 混用）。

## ③ 边缘测试结果

```
Ran 129 tests in 1.816s
OK
```

## ④ SQLite observations 表确认

- 实例路径：`.zcode/wt-edge-timeout/edge-agent/src/data/edge_EDGE-W01-B02.db`
  （阶段6运行实例的 cwd 相对路径，与实际运行一致；188 KB）
- 列结构：`id, ward_id, node_id, bed_id, source_type, data, quality, timestamp, synced`
- 行数：306（运行期间持续写入）

## ⑤ 日志无 "no such table: observations"

对全部 10 个日志文件 grep（边端×4 / 云端×2 / 抓包×2 / broker / 记录）：

```
命中总数: 0
```

## ⑥ 超时事件 SQLite 回写确认

阶段 6 实例共 16 条超时事件，全部成功回写：

| event_id | state | cloud_status | reason | judgment |
|----------|-------|--------------|--------|----------|
| bb1f0934… 等 16 条 | new（边缘判断保留，未被 escalate 覆盖） | fallback_edge | timeout | None |

`event_id` 唯一性：16/16。

## 附：三场景结果表

| 场景 | event_id | trace_id | request_mode | 云端结果 | 边缘结果 | SQLite |
|---|---|---|---|---|---|---|
| CLOUD 正常 | `9a0ad5b0-f01e-4182-81d3-41ccd34a7915` | `5db313af-4bcf-482a-b904-4eeec51eb6dc` | cloud | 成功（judgment=confirm）| 已更新（notified）| 正常 |
| HYBRID 正常 | `e2cf989e-6034-4b9c-a83f-dd03a0b7a83a` | `5f9e8bb0-7d87-4be7-b94c-85fb9c7570e7` | hybrid | 成功（confirm）| 已更新（notified）| 正常 |
| CLOUD 超时 ×N | `5831a9d5-a3a8-4bf8-bc10-9988e79bd813` 等 | `703cd0a8-04f1-4d7e-aae2-ba092632efde` 等 | cloud / timeout_ms=500 | `inference_timeout` → status=timeout / escalate | 识别并保留边缘判断，本地回退 | 正常 |

云端超时日志样例：
```json
{"stage": "inference_timeout", "timeout_ms": 500,
 "action": "publish_escalate_and_allow_edge_fallback",
 "event_id": "5831a9d5…", "trace_id": "703cd0a8…"}
```
MQTT 线路抓包样例（capture.jsonl）：
```json
{"topic": "node/EDGE-W01-B02/inference/response",
 "payload": {"status": "timeout", "judgment": "escalate", "latency_ms": 500.0}}
```

## 待确认项

阶段 6 边端版本 `70185a8`（= 5801d19 + status=timeout 识别）需 P6/P7 认可；
分支已推送远端：`p1/edge-timeout-fix`。
