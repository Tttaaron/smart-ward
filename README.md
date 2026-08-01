# 智慧病房云边端协同系统

这是一个独立于原 `edge` 智能教室项目的新项目。它复用了智能教室已经验证过的技术路线——Vue、FastAPI、MQTT、MySQL、SQLite 离线缓存与 Docker Compose——但领域模型、数据契约、事件闭环、边缘推理和协同训练均面向智慧病房重新设计。

## 当前交付范围

- 1 个病房（`W-01`）、3 张床（`B01`～`B03`）
- 场景模拟与视觉事件融合：跌倒、离床、夜间徘徊、环境异常、门区异常离开、护士呼叫等
- 三个独立边缘代理，支持断网缓存、恢复补传和 MQTT QoS 1
- 云端事件中心，支持事件查询、确认、处置、审计记录和 WebSocket 推送
- 边缘侧 LLM 语义增强、护理建议、离线决策和云边任务路由
- 同步 FedAvg 与异步陈旧度加权聚合框架
- 独立护士站 Vue 页面和 Docker Compose 一键演示环境

当前 Docker 演示默认使用 `mock` 推理。云端 LLM 服务和 Jetson 实机验收仍在联调阶段。

## 目录

```text
smart-ward/
├── contracts/               # MQTT 消息 JSON Schema
├── edge-agent/              # 三床边缘采集、推理、决策和离线缓存
├── cloud-backend/           # FastAPI 事件中心与 MySQL 持久化
├── training-coordinator/    # 同步/异步协同训练调度
├── cloud-frontend/          # Vue 护士站工作台
├── mqtt-broker/             # Mosquitto 配置
├── cloud-llm-service/       # 云端 LLM 服务目录（待接入 vLLM/Qwen2.5-14B）
├── deploy/kubeedge/         # 阶段二云边部署清单
├── docs/                    # 架构、接口、测试与方案书
└── docker-compose.yml       # 本地演示编排
```

## 快速启动

```powershell
Copy-Item .env.example .env
docker compose up --build
```

启动后：

- 护士站工作台：http://localhost:8081
- 云端 API 文档：http://localhost:8001/docs
- 协同训练 API 文档：http://localhost:8002/docs
- MQTT：`localhost:1884`

三个边缘节点会输出节点状态，并按场景配置触发模拟事件，便于重复录制演示视频。默认边缘 LLM 为 `mock` 模式；接入真实 GGUF 模型时，不需要修改事件融合和 MQTT 接口。

## 本地核心测试

```powershell
python -m unittest discover edge-agent/tests -v
python -m unittest discover training-coordinator/tests -v
python -m compileall -q edge-agent/src edge-agent/tests cloud-backend/app training-coordinator/app
docker compose config --quiet
```

当前测试结果为：`edge-agent` 38 项、`training-coordinator` 8 项，全部通过。测试以 `unittest.TestCase` 子类组织，也可直接运行单个测试文件。版本变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 启用真实边缘 LLM

1. 确认模型文件位于 `edge-agent/models/`。模型文件默认被 `.gitignore` 忽略，不提交到代码仓库。
2. 设置真实推理模式：

```powershell
$env:LLM_MODE="real"
```

质量优先的 Qwen2.5-1.5B 路径：

```powershell
docker compose up --build
```

低内存的 Qwen2.5-0.5B 路径：

```powershell
docker compose -f docker-compose.yml -f docker-compose.compact.yml up --build
```

也可以运行 `edge-agent/scripts/download_compact_model.ps1` 下载 0.5B GGUF 模型。

## 当前性能证据

以下数据来自 Windows/x86 主机的真实 GGUF 推理，采用上下文 512、batch 128、8 个 CPU 线程，统计热身后的推理结果：

| 路径 | 模型 | 热身后 TTFT | 峰值 RSS | 状态 |
|---|---|---:|---:|---|
| 质量优先 | Qwen2.5-1.5B Q4，约 1.04GB | 约 31.9ms | 约 1.66GB | TTFT 达标，内存略超 1.5GB |
| 低内存 | Qwen2.5-0.5B Q4，约 469MB | 约 19.8ms | 约 516MB | 当前 x86 测试两项达标 |

上述结果不是 Jetson Orin Nano 实测结果。Jetson 上仍需重新测量冷启动、热身后 TTFT、总内存、吞吐量，以及与 YOLO-pose 同时运行时的资源占用。

## 云边协同状态

边缘侧已经实现：

- `event_id + trace_id` 请求关联
- pending 请求、超时回退和重复响应幂等
- `confirm/reject/escalate` 结果写回本地事件状态
- 请求主题：`ward/{ward_id}/node/{node_id}/inference/request`
- 响应主题：`node/{node_id}/inference/response`

云端 LLM 消费者、Qwen2.5-14B/vLLM 服务和端到端 Broker 联调尚未纳入当前 Compose，需要由云端负责成员接入后完成验证。

