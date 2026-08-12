# 智慧病房云边端协同系统

这是一个独立于原 `edge` 智能教室项目的新项目。它复用了智能教室已经验证过的技术路线——Vue、FastAPI、MQTT、MySQL、SQLite 离线缓存与 Docker Compose——但领域模型、数据契约、事件闭环、边缘推理和协同训练均面向智慧病房重新设计。

## 当前交付范围

- 1 个病房（`W-01`）、3 张床（`B01`～`B03`）
- 场景模拟与视觉事件融合：跌倒、离床、夜间徘徊、环境异常、门区异常离开、护士呼叫等
- 可选真实 YOLO/YOLO-Pose 摄像头链路：人员检测、IoU 跟踪、连续帧姿态与行为摘要
- 三个独立边缘代理，支持断网缓存、恢复补传和 MQTT QoS 1
- 云端事件中心，支持事件查询、确认、处置、审计记录和 WebSocket 推送
- 边缘侧 LLM 语义增强、护理建议、离线决策和云边任务路由
- 同步 FedAvg 与异步陈旧度加权聚合框架
- 独立护士站 Vue 页面和 Docker Compose 一键演示环境

当前 Docker 演示默认使用 `mock` 摄像头和 LLM 推理。真实 YOLO 管线已接入边缘代理，但模型权重、摄像头设备和 Jetson 运行时仍需现场配置与复测。

## 目录

```text
smart-ward/
├── contracts/               # MQTT 消息 JSON Schema
├── edge-agent/              # 三床边缘采集、推理、决策和离线缓存
├── cloud-backend/           # FastAPI 事件中心与 MySQL 持久化
├── training-coordinator/    # 同步/异步协同训练调度
├── cloud-frontend/          # Vue 护士站工作台
├── mqtt-broker/             # Mosquitto 配置
├── cloud-llm-service/       # 云端 LLM 二次研判（mock/vLLM 双模式）
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
python -m unittest discover cloud-backend/tests -v
python -m pytest cloud-llm-service/tests -q
python -m compileall -q edge-agent/src edge-agent/tests cloud-backend/app training-coordinator/app
docker compose config --quiet
```

当前测试结果为：`edge-agent` 83 项、`training-coordinator` 15 项、`cloud-backend` 56 项、`cloud-llm-service` 9 项，全部通过。测试以 `unittest.TestCase` 子类组织，也可直接运行单个测试文件（云端 LLM 服务测试以 pytest 运行）。版本变更记录见 [CHANGELOG.md](CHANGELOG.md)。

## 启用真实 YOLO 行为分析

真实视觉链路由 `YOLO/YOLO-Pose -> IoUTracker -> BehaviorAnalyzer -> FusionEngine -> LLMAdvisor` 组成。YOLO 输出 person 检测框和可选姿态关键点，边缘端连续维护 `track_id`，再生成姿态序列、跌倒分数、静止时长和抖动分数；LLM 只接收结构化行为事件，不接收每一帧原始画面。

安装可选依赖：

```powershell
python -m pip install -r edge-agent/requirements-yolo.txt
```

准备模型后运行：

```powershell
$env:CAMERA_MODE="yolo"
$env:CAMERA_SOURCE="0"
$env:YOLO_MODEL_PATH="edge-agent/models/yolo11n-pose.pt"
$env:TICK_SECONDS="0.2"
python edge-agent/src/main.py
```

Docker/Jetson 部署时，将模型挂载到 `/app/models/`，设置同名环境变量，并根据 JetPack/PyTorch 版本安装兼容的 Ultralytics、PyTorch 和 OpenCV。没有可用模型或依赖时不要把 `CAMERA_MODE` 设为 `yolo`，否则代理会明确启动失败，而不是伪装成真实识别。

### 本机实时识别窗口

用于本机摄像头验收时，可以直接启动独立可视化工具。窗口显示 YOLO 姿态骨架、人员跟踪 ID、姿态、行为序列、FPS、推理耗时和 GPU 显存；按 `Q`/`ESC` 退出，按 `Space` 暂停，按 `S` 截图。

```powershell
$env:KMP_DUPLICATE_LIB_OK="TRUE"  # 仅针对部分 Anaconda OpenMP 冲突环境
python edge-agent/scripts/yolo_realtime_viewer.py `
  --camera 0 `
  --model edge-agent/models/yolo11n-pose.pt `
  --device 0
```

如果默认摄像头不是目标设备，将 `--camera 0` 改为 `--camera 1`。在当前开发机上，`0` 是 DroidCam Video，`1` 是 Iriun Webcam，因此 Iriun 手机摄像头应使用 `--camera 1`。该工具只做本机视觉验收，不发送 MQTT 告警。

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

### 跌倒检测评测（UR Fall Detection Dataset）

ShuffleNetV2+SA 模型（`edge-agent/models/shufflenetv2-sa-fall.pt`）在 UR Fall Detection Dataset 全量评测（修复 stride 采样口径后）：

| 口径 | 指标 | 结果 |
|---|---:|---:|
| 帧级 | 准确率 / 召回率 / F1 | 95.78% / 77.50% / 0.78 |
| 片段级 | 识别率 | 100% |

评测脚本与 JSON 证据见 `docs/21-UR-Fall数据集与跌倒评测说明.md`、`docs/evidence/ur-fall-eval-*.json`。

## 云边协同状态

边缘侧已经实现：

- `event_id + trace_id` 请求关联
- pending 请求、超时回退和重复响应幂等
- `confirm/reject/escalate` 结果写回本地事件状态
- 请求主题：`ward/{ward_id}/node/{node_id}/inference/request`
- 响应主题：`node/{node_id}/inference/response`
- 云端超时由独立守护线程判定，与主循环 TICK_SECONDS 解耦
- 日常活动识别结果随事件 `details.activity` 上报

云端侧已经实现：

- `cloud-llm-service` 已纳入 Compose（`LLM_MODE=mock` 默认）：MQTT 消费者订阅推理请求、去重/幂等、超时回退、`/health` 与 `/stats` 端点
- vLLM 真实模式已适配 OpenAI-compatible chat API（`/v1/chat/completions`，默认 `http://localhost:8501`，模型 `Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4`）
- 云边推理 request/response JSON Schema 与契约测试（`contracts/inference_*.json`）

**仍待完成**：真实 Qwen2.5-14B/vLLM 运行环境验证（P5/P6）、端到端真实 Broker 联调取证（7 场景）、断网保持率测试。

