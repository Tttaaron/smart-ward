# 主 Compose 全栈构建与验证记录

> 记录：烽亮 (P6) · 2026-08-19
> 环境：Windows 11 + Docker Desktop 4.87.0（WSL2 backend），镜像加速 1ms.run/daocloud
> 状态：✅ 10/10 服务全部运行验证通过

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
| **diffusion-service** | smart-ward-diffusion-service | ✅ Up（/health 200，GPU: RTX 4050, CUDA 12.1） |

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

## 四、遇到的问题与修复

1. **pytorch 基础镜像下载中断**：3.7GB 经镜像加速不稳定（short read EOF）→ 更换镜像源（1ms.run/xuanyuan.me）后 4 分钟下载完成
2. **requirements.txt 的 `torch>=2.3.0` 无上限**：pip 解析到最新 cu13 版 torch，额外下载数 GB CUDA 依赖（cudnn 366MB/nccl 206MB 等）→ **固定 `torch==2.3.0` + `torchvision==0.18.0`**（基础镜像自带版本），构建时间从 1 小时+ 降到 ~5 分钟
3. **Dockerfile pip 未配镜像源**：diffusion-service 的 Dockerfile 缺少 `--index-url`（其他服务都有）→ 已补阿里云镜像
4. Windows Docker 上 deploy.resources GPU 段正常工作（WSL2 直通 RTX 4050，/health 识别 CUDA 12.1）

## 五、待完成

- [x] diffusion-service 镜像构建 + 启动 + /health 验证
- [ ] compact compose（docker-compose.compact.yml）验证
- [ ] compose 内误报回流端到端（diffusion-service ↔ mqtt-broker 已订阅确认，完整生成闭环见 AutoDL 实测）

> 生成能力已在 AutoDL 4090 实测通过（见 20260819_diffusion-service_mqtt-backflow_2d378ac.md）。
