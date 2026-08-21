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
- **云边协同真实联调取证**（7 场景，每场景 ≥20 次，证据 `docs/evidence/mqtt-sync/`）

当前 Docker 演示默认使用 `mock` 摄像头和 LLM 推理。真实 YOLO 管线已接入边缘代理，但模型权重、摄像头设备和 Jetson 运行时仍需现场配置与复测（部署脚本与手册已就绪，缺真机实测）。**云端 Qwen2.5-14B/vLLM 真实环境已由 P6 烽亮验证可运行**（见 `docs/23-云端14B环境确认记录.md`，AutoDL RTX 4090）。

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

当前测试结果为：`edge-agent` 122 项、`training-coordinator` 15 项、`cloud-backend` 59 项（含时间敏感测试修复）、`cloud-llm-service` 13 项（pytest）、`diffusion-service` 11 项（pytest），全部通过。测试以 `unittest.TestCase` 子类组织，也可直接运行单个测试文件（云端 LLM 与扩散服务测试以 pytest 运行）。版本变更记录见 [CHANGELOG.md](CHANGELOG.md)。

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

## 边缘端交接班小 agent（LLM 生成自然交接班记录）

边缘端内置交接班小 agent：基于 YOLO 采集/融合产生的事件数据（含时间）+ 本地病人档案，
由边缘 LLM 生成**每床、带时间信息的自然交接班记录**（替代云端规则拼统计文本）。

```powershell
# 默认 mock 模式（无 GGUF 也可演示），数据来自边缘 SQLite
python scripts/gen_shift_handover.py --bed B02 --period evening

# 指定日期/节点；LLM_MODE=real 走 GGUF 真模型（需 llama-cpp-python + 模型文件）
LLM_MODE=real python scripts/gen_shift_handover.py --bed B01 --date 2026-08-19 --period day
```

- 病人档案：`edge-agent/config/patients.json`（每床：姓名/护理等级/诊断/跌倒·压疮风险/过敏/备注）
- 输出：写入边缘 SQLite `shift_handovers` 表 + 导出 Markdown（`edge-agent/data/handovers/`）
- 班次窗口与云端一致（白班 08-16 / 晚班 16-24 / 夜班 00-08，东八区）
- mock 模式基于真实事件数据确定性生成（含时间线/置信度/姿态）；real 模式由 GGUF 模型生成自然报告
- 单测覆盖窗口计算/mock 生成/病人档案/存储回读（`edge-agent/tests/test_shift_handover.py`）

## 蒸馏学生模型部署到边缘（LLM 运行时切换）

蒸馏链路：14B 教师 → 1.5B 学生（P5/AutoDL 产出 `qwen2.5-1.5b-ward-q4_k_m.gguf`，checksum 见
`datasets/ward-nlu-500-v1/distillation/reports/comparison.json`）。边缘 LLM 支持**运行时切换模型**
（`LLMEngine.switch_model` + `LLMAdvisor.switch_model`），可通过以下任一方式把蒸馏学生部署到边缘。

**方式一：拉取脚本（文件到位即生效）**
```powershell
# 从 P5/Artifact 拉取并 sha256 校验（不匹配不落盘），默认落到
# edge-agent/models/qwen2.5-1.5b-ward-distilled/qwen2.5-1.5b-ward-q4_k_m.gguf
python scripts/fetch_edge_llm.py --url http://<artifact>/qwen2.5-1.5b-ward-q4_k_m.gguf `
  --sha256 c86401b2befde9ddfa7b3e3b8c0f51a5ecaf5de01beb86a6877efb420c352986
# 然后边缘设置（重启生效）：
$env:LLM_MODE="real"
$env:LLM_MODEL_PATH="/app/models/qwen2.5-1.5b-ward-distilled/qwen2.5-1.5b-ward-q4_k_m.gguf"
$env:LLM_MODEL_NAME="qwen2.5-1.5b-ward"
```

**方式二：通过 model/deploy 运行时下发**（`POST /api/models/deploy`，`runtime=gguf`）
- 边缘 `handle_model_deploy` 按 `runtime=="gguf"`（或模型名以 qwen 开头）路由到
  `llm_advisor.switch_model`，支持 sha256 校验与回滚；视觉模型仍走 `inference.load_model`
- 文件需已就位（`model_path` 或本地 `artifact_url`）；http(s) artifact 先用方式一下载
- 示例：
```bash
curl -X POST "http://localhost:8001/api/models/deploy?node_id=EDGE-W01-B01" \
  -H "Content-Type: application/json" \
  -d '{"model_name":"qwen2.5-1.5b-ward","model_version":"distilled-v2-q4_k_m",
       "artifact_url":"file:///app/models/qwen2.5-1.5b-ward-distilled/qwen2.5-1.5b-ward-q4_k_m.gguf",
       "runtime":"gguf","model_kind":"llm","checksum":"c86401b2..."}'
```
> 说明：mock 模式下 `switch_model` 更新模型元数据用于演示/测试；real 模式（需
> llama-cpp-python + GGUF）加载真实权重。云端 runtime 枚举已支持 `gguf`，
> `model_kind=vision|llm` 用于区分下发对象。

## 边缘端 Agent 能力（LLM 小 agent）

边缘 LLMAdvisor 已具备多类 agent 能力（mock/real 双模式，GPU real 模式已在本机 RTX 3060 验证）：

| 能力 | 说明 | 触发 |
|------|------|------|
| 事件语义增强 | 事件一句话描述 + 护理建议 | 主循环自动 |
| 离线自治决策 | 断网时多事件排序 + 应急动作 | 主循环自动 |
| **活动播报（模式A）** | 活动切换实时一句话播报（含跌倒风险提示） | 主循环自动（`ACTIVITY_BROADCAST=off` 关闭）|
| **时段活动摘要（模式B）** | 活动分布/切换次数/风险提示 | `python scripts/gen_activity_report.py` |
| **交接班生成（增强）** | 每床自然交接班 + 在床率/环境均值/活动分布 + 上次交接闭环跟踪 + 近7天风险趋势预警 | `python scripts/gen_shift_handover.py` |
| **问答（工具路由）** | 自然语言查历史（识别床位/时间/事件类型→检索→作答） | `python scripts/ask_ward_agent.py -q "李伯伯近7天发生了什么？"` |

```
python scripts/gen_shift_handover.py --bed B02 --period evening   # 增强交接班
python scripts/gen_activity_report.py --bed B02 --period evening  # 模式B 摘要
python scripts/ask_ward_agent.py --bed B02 -q "今晚离床几次？"     # 问答
LLM_MODE=real LLM_N_GPU_LAYERS=99 python scripts/gen_shift_handover.py --bed B02
```

- 病人档案：`edge-agent/config/patients.json`（活动播报/交接班/问答共用）
- 播报与交接班均写入边缘 SQLite（`activity_broadcasts` / `shift_handovers`，后者含结构化 `watch_points` 供下个班闭环跟踪）
- 交接班数据面：在床率（床垫观测）、环境均值、活动分布、近7天班均趋势（超 1.5 倍自动预警）

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

**仍待完成**：
- Jetson Orin Nano 真机性能、真实视觉模型与 LLM 并行运行时的资源占用实测（部署脚本与手册就绪，`docs/21-Jetson部署手册.md`）
- 断网保持率统计（≥90% 三指标分开）正式报告（断网自治与恢复补传功能已在 7 场景取证中验证）
- 三路线对比报告（1.5B/0.5B/14B 准确率/F1/TTFT/RSS/吞吐，截止 8/25）
- NLU 评测集 500+ 条标注（截止 8/25）
- 最终材料冻结（技术报告/PPT/提交包一致性）+ 5-8 分钟演示视频录制（截止 8/28-31）

**已完成（v0.4.2，2026-08-19）**：
- 云端 Qwen2.5-14B/vLLM 真实环境验证（`docs/23-云端14B环境确认记录.md`）
- 7 场景真实 MQTT Broker 联调取证（`docs/evidence/mqtt-sync/`）
- Jetson 一键部署脚本（`docs/21-Jetson部署手册.md`）
- 演示视频脚本、训练灰度发布/回滚演示
- 护士站 UI 全量重构（5 视图 + AppShell 布局）

