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

## 五、验证命令（GPU 服务器上执行）

```bash
# 1. 启动服务（含 mqtt-broker）
docker compose up --build diffusion-service mqtt-broker

# 2. 健康检查
curl http://localhost:8003/health

# 3. 模拟误报 ack（发布到 MQTT）
mosquitto_pub -h localhost -p 1884 -t ward/W-01/alert/test-fp-001/ack -m '{
  "message_id": "m1", "event_id": "test-fp-001", "schema_version": "v1",
  "occurred_at": "2026-08-19T00:00:00Z", "source": "cloud",
  "trace_id": "t1", "payload": {"event_id": "test-fp-001", "action": "false_positive"}
}'

# 4. 检查误报入库
curl http://localhost:8003/api/false-positives

# 5. 检查统计
curl http://localhost:8003/api/stats
```

## 六、待验证项

- [ ] GPU 实机：SD 模型加载 + 误报触发生成端到端
- [ ] 误报 → 自动生成 → YOLO 数据集导出闭环
- [ ] MQTT 断线重连
- [ ] 单元测试运行（tests/test_all.py 12 项）

> 说明：本机（Windows 开发机）无 Python/GPU 环境，验证需在 AutoDL 4090 服务器执行，完成后补充实测结果。
