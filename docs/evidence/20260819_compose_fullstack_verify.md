# 主 Compose 全栈构建与验证记录

> 记录：烽亮 (P6) · 2026-08-19
> 环境：Windows 11 + Docker Desktop 4.87.0（WSL2 backend），镜像加速 daocloud/ustc
> 状态：9/10 服务验证通过，diffusion-service 镜像下载中（pytorch 3.7GB 基础镜像）

---

## 一、构建结果

`docker compose up --build`（8 服务 + 3 边缘节点）：

| 服务 | 镜像 | 状态 |
|------|------|------|
| mysql | mysql:8.0 | ✅ Healthy |
| mqtt-broker | eclipse-mosquitto:2.0 | ✅ Up |
| cloud-backend | smart-ward-cloud-backend | ✅ Up |
| training-coordinator | smart-ward-training-coordinator | ✅ Up |
| cloud-llm-service | smart-ward-cloud-llm-service | ✅ Up（LLM_MODE=mock） |
| cloud-frontend | smart-ward-cloud-frontend | ✅ Up |
| edge-bed-01/02/03 | smart-ward-edge-bed-* | ✅ Up |
| **diffusion-service** | pytorch 基础镜像 3.7GB 下载中断重试中 | ⏳ 待完成 |

## 二、服务端点验证

| 端点 | 结果 |
|------|------|
| `http://localhost:8001/` (cloud-backend) | ✅ `{"message":"智慧病房事件中心 API 运行中"}` |
| `http://localhost:8002/health` (training-coordinator) | ✅ `{"status":"ok","strategy":"sync_fedavg","rounds":0}` |
| `http://localhost:8005/health` (cloud-llm-service) | ✅ `llm_mode: mock` |
| `http://localhost:8081/` (护士站前端) | ✅ HTTP 200 |
| `localhost:1884` (MQTT) | ✅ LISTENING |

## 三、端到端链路验证

MQTT 事件 → cloud-backend → MySQL：

```bash
docker exec smart-ward-mqtt-broker-1 mosquitto_pub \
  -t ward/W-01/node/EDGE-W01-B01/event -m '{"message_id":"m-c1",...,"event_type":"fall_suspected","priority":"P1","confidence":0.85,...}'
```

结果：`GET /api/events` 返回 `evt-compose-001`（fall_suspected, P1, confidence 0.85）✅ 入库成功

## 四、遇到的问题

1. **pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime 镜像下载中断**：3.7GB 基础镜像经镜像加速下载不稳定（short read: unexpected EOF），重试中
2. 其余镜像（mysql/mosquitto/python-slim 系）均正常

## 五、待完成

- [ ] diffusion-service 镜像下载完成后构建 + 启动 + /health 验证
- [ ] compact compose（docker-compose.compact.yml）验证

> 说明：Docker Desktop Windows 的 GPU 支持依赖 WSL2 NVIDIA 驱动，diffusion-service 的 deploy.resources 段在 Windows 上可能需要调整；生成能力已在 AutoDL 4090 实测通过（见 20260819_diffusion-service_mqtt-backflow_2d378ac.md）。
