# 云边协同推理 7 场景联调取证

> 取证时间：2026-08-19 ｜ 环境：本地真实 MQTT Broker（amqtt 0.11.4，完整 MQTT 3.1.1/QoS1）
> 组件：edge-agent（master）、cloud-llm-service（LLM_MODE=mock）、edge-agent 场景驱动
> 验收口径：每场景 ≥20 次（docs/22 与 docs/19 要求）

## 结果总览

| # | 场景 | 方法 | 次数 | 结果 | 证据文件 |
|---|---|---|--:|:--:|---|
| 1 | 正常链路 | 云端 20 次直接请求 + 边端 seizure 场景全量回写 | 20+28 | ✅ | scenario1_normal.json |
| 2 | 重复去重 | 同 event_id 连发 20 次 | 20 | ✅ | scenario2_duplicate.json |
| 3 | 超时回退 | 停 cloud 后边端事件无响应→3s 超时 | 28 | ✅ | scenario3_timeout.json |
| 4 | 非法判断 | 注入 judgment=bogus 响应 | 26 | ✅ | scenario4_invalid.json |
| 5 | 未知事件 | 注入指向不存在 event_id 的响应 | 25 | ✅ | scenario5_unknown.json |
| 6 | trace 不匹配 | 注入 trace 被篡改的响应 | 28 | ✅ | scenario6_tracemismatch.json |
| 7 | 断网自治+补传 | 断 broker→24 条缓存→恢复→补传 | 24+ | ✅ | scenario7_offline.json |

## 各场景判据与实测

### 1. 正常链路 ✅
- 云端侧：`mqtt_cloud_sync_test.py --scenario normal --count 20` → 20 请求 / 20 响应，trace 关联 PASS；`/stats` total_requests=20, total_responses=20, errors=0
- 边端侧：seizure 场景累积 28 条事件，`details.cloud_inference.status=completed` 28/28，state=notified，synced=1

### 2. 重复去重 ✅
- 同 event_id 连发 20 次：云端**推理仅执行 1 次**（total_requests +1），其余 19 次命中去重缓存（total_duplicates +19），每请求均回响应
- 说明：云端按 event_id 幂等去重（300s TTL），不重复执行推理；仍对每个请求回响应以便边端重试

### 3. 超时回退 ✅
- 停 cloud-llm-service，边端事件卸载云端后 3s 无响应 → `cloud_inference.status=fallback_edge, reason=timeout` 28 条，state=new，边缘不崩溃
- 伴随现象（自适应阈值自愈）：连续失败后 TaskRouter 边缘阈值 0.95→0.40，事件转边缘自治

### 4. 非法判断 ✅
- 受控响应器注入 `judgment=bogus` 26 次 → 边端识别非法 → `fallback_edge/invalid_judgment` 26 条，不崩溃、本地决策生效

### 5. 未知事件 ✅
- 注入 25 条指向不存在 event_id 的响应 → 边端全部忽略（日志 `status=unknown` 25 次），DB 零污染（无 UNKNOWN- 事件），正常链路不受影响

### 6. trace 不匹配 ✅
- 注入 trace 被篡改的响应 28 次 → 边端全部丢弃（`status=trace_mismatch`），无 completed 误采纳；未决请求最终超时回退

### 7. 断网自治+恢复补传 ✅
- 断 broker 后边端继续值守：离线缓存 24 条（synced=0）
- 恢复 broker 后：边端自动重连，`补传 39 条离线事件`，最终 54/54 全部 synced=1（synced=0 归零）

## 原始证据

- `scenario{1..7}_*.json`：本目录结构化结果
- 原始日志与抓包：`.zcode/联调/7场景/`（edge*.log、cloud-llm.log、capture*.log、responder-*.log）
- 受控响应器：`.zcode/联调/7场景/controlled_responder.py`（invalid/wrongtrace/unknown 三模式）
- 复现脚本：`scripts/mqtt_cloud_sync_test.py`（normal/duplicate/timeout/offline 等 7 场景 CLI）

## 修复联动

取证过程中修复：
1. `fix(edge) 667abbd`：HYBRID 请求 `request_mode` review→hybrid，对齐契约
2. `fix(test) bba3242`：cloud-backend 交接班摘要时间敏感测试
3. `scripts/mqtt_cloud_sync_test.py`：duplicate 判据修正（推理 1 次 + 复用 N-1，非"仅回 1 响应"）
