# 扩散服务误报回流闭环验证记录

> 记录：烽亮 (P6) · 2026-08-19
> 提交：2d378ac（master）
> 状态：代码已提交，GPU 实机验证待执行

---

## 一、背景

diffusion-service（SD 1.5 + ControlNet OpenPose 困难样本生成）原为纯生成服务，
本次补充**误报回流闭环**：护士站标记误报 → MQTT ack → 扩散服务自动生成困难样本。

## 二、本次变更

| 文件 | 说明 |
|------|------|
| `diffusion-service/app/mqtt_handler.py` | 新增：订阅 `ward/+/alert/+/ack`（过滤 false_positive）+ `ward/+/node/+/event`（事件缓存），指数退避重连 |
| `diffusion-service/app/database.py` | 新增：SQLite 3 表（false_positive_events / generated_samples / dataset_exports） |
| `diffusion-service/app/logger.py` | 新增：统一日志工具 |
| `diffusion-service/app/main.py` | 修改：MQTT 生命周期（lifespan）+ 3 个新端点 + 误报自动生成回调；修复批量生成 `uuid4` NameError |
| `diffusion-service/app/config.py` | 修改：新增 MQTT_BROKER/MQTT_PORT/AUTO_GENERATE/GENERATION_BATCH_SIZE/DB_PATH |
| `diffusion-service/requirements.txt` | 新增 paho-mqtt |
| `docker-compose.yml` | diffusion-service 增加 MQTT 环境变量 + diffusion-data 卷 + depends_on mqtt-broker |
| `contracts/diffusion_request.json` | 新增：扩散生成请求契约 |

## 三、新增 API

| 端点 | 说明 |
|------|------|
| `GET /api/false-positives` | 误报事件列表 |
| `GET /api/stats` | 误报回流统计 |
| `POST /api/events/{event_id}/generate` | 按误报事件手动触发生成 |

## 四、闭环链路

```
护士站标记误报 (action=false_positive)
  → cloud-backend 发布 MQTT ack (ward/{ward_id}/alert/{event_id}/ack)
  → diffusion-service MqttHandler 收到，缓存 event 上下文
  → _handle_false_positive 后台线程调 generator.generate_batch(event_type)
  → curator.filter 质量筛选 → db.mark_processed
  → 新样本经 /generate/batch 导出为 YOLO 数据集（复用现有流程）
```

## 五、GPU 实机验证结果（2026-08-19 AutoDL RTX 4090）

环境：AutoDL 4090（24GB），conda env `diffusion`（diffusers 0.39.0 / torch 2.13.0 / CUDA 13.0），
mosquitto 2.0.11 本机 broker，uvicorn 直跑（AutoDL 容器无 systemd/NET_ADMIN，Docker 不可用）。

### 5.1 健康检查

```json
{"status":"ok","service":"diffusion-service","version":"0.2.0",
 "gpu":{"device":"NVIDIA GeForce RTX 4090","vram_total_gb":25.3,...},"models_loaded":false}
```
GPU 识别 ✓，MQTT 连接 + 订阅 2 主题 ✓

### 5.2 误报回流闭环（场景 1：fall_suspected）

```
mosquitto_pub ward/W-01/node/EDGE-W01-B01/event   # 事件缓存（fall_suspected）
mosquitto_pub ward/W-01/alert/evt-fp-003/ack      # false_positive
```

日志：
```
收到误报确认: event_id=evt-fp-003
误报回流触发生成: event_id=evt-fp-003 event_type=fall_suspected
Quality filter: 2/4 passed (50.0%)
误报生成完成: event_id=evt-fp-003 generated=4 passed=2
```
（首次运行需从 hf-mirror 下载 SD1.5 base ~4GB + ControlNet，后续有缓存）

### 5.3 误报回流闭环（场景 2：seizure + YOLO 数据集导出）

```
误报回流触发生成: event_id=evt-fp-004 event_type=seizure
Quality filter: 3/4 passed (75.0%)
误报生成完成: event_id=evt-fp-004 generated=4 passed=3
  dataset=/root/smart-ward/diffusion-service/output/datasets/fp-evt-fp-0
```

数据集结构（yolo-pose 格式）：
```
fp-evt-fp-0/
├── images/000000.jpg ~ 000002.jpg   # 3 张 640x640
├── labels/000000.txt ~ 000002.txt   # YOLO 标签
├── manifest.json                     # seed/night_mode/generation_time(~2.4s/张)
└── data.yaml                         # YOLO 训练配置
```

### 5.4 API 验证

```
GET /api/false-positives  → 3 条误报记录
GET /api/stats            → total_false_positives=3
误报入库 → evt-fp-003 processed=1 samples=2 ✓
```

### 5.5 验证中发现并修复的 bug

| Bug | 修复 |
|-----|------|
| `/api/events/{id}/generate` 参数顺序语法错误 | 调整 background 参数位置（ea18a87 前） |
| ack 主题解析索引错误（alert 在 index 2 非 3） | `topic_parts[2] == "alert"`（534cf30） |
| 批量生成 `uuid4()` NameError | `uuid.uuid4()`（2d378ac） |
| 误报生成后不保存图像 | 增加 export_dataset 导出 YOLO 数据集（ea18a87） |

## 六、待验证项

- [x] GPU 实机：SD 模型加载 + 误报触发生成端到端
- [x] 误报 → 自动生成 → YOLO 数据集导出闭环
- [x] MQTT 断线重连（服务重启自动重连已生效）
- [ ] 单元测试运行（tests/test_all.py 12 项，需在 diffusion env 执行）
- [ ] 与 training-coordinator 的导出对接（本次未联调）
