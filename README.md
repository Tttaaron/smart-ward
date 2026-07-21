# 智慧病房云边端协同系统

这是一个独立于原 `edge` 智能教室项目的新项目。它复用了智能教室已经验证过的技术路线——Vue、FastAPI、MQTT、MySQL、SQLite 离线缓存与 Docker Compose——但领域模型、数据契约、事件闭环、边缘推理和协同训练均面向智慧病房重新设计。

## 当前交付范围

- 1 个病房（`W-01`）、3 张床（`B01`～`B03`）
- 六类演示事件：跌倒、离床、夜间徘徊、环境异常、门区异常离开、护士呼叫
- 三个独立边缘代理，支持断网缓存、恢复补传和 MQTT QoS 1
- 云端事件中心，支持事件查询、确认、处置和审计记录
- 同步 FedAvg 与异步陈旧度加权聚合框架
- 独立护士站 Vue 页面和 Docker Compose 一键演示环境

## 目录

```text
smart-ward/
├── contracts/               # MQTT 消息 JSON Schema
├── edge-agent/              # 三床边缘采集、推理、决策和离线缓存
├── cloud-backend/           # FastAPI 事件中心与 MySQL 持久化
├── training-coordinator/    # 同步/异步协同训练调度
├── cloud-frontend/          # Vue 护士站工作台
├── mqtt-broker/             # Mosquitto 配置
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

三个边缘节点会先输出正常状态，再按固定节奏触发六类场景，便于重复录制赛事演示视频。当前模型输出由可替换的模拟推理适配器产生；接入真实摄像头与 TensorRT 模型时，不需要修改 MQTT、事件引擎或云端接口。

## 本地核心测试

```powershell
python -m unittest discover edge-agent/tests -v
python -m unittest discover training-coordinator/tests -v
```

说明：方案书中的性能、精度和通信指标均为验收目标，不代表当前模拟框架已经完成实测。

