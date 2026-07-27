# 变更日志

> 智慧病房云边协同系统版本变更记录。
> 版本号规则与提交规范见 [docs/12-上传规范.md](docs/12-上传规范.md)。
> 格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循语义化版本 SemVer。

---

## [v0.3.0] - 2026-07-27

### 变更（breaking）- 移除输液监测功能

因输液监测传感器选型复杂、硬件接入成本高，移除输液监测（infusion_anomaly）相关全部代码与文档，聚焦摄像头/床垫/环境三源融合。

- **删除** `edge-agent/src/adapters/infusion.py`（InfusionAdapter）
- **移除** `main.py` 的 InfusionAdapter 实例化（适配器 4 类 -> 3 类）
- **移除** `fusion.py` 规则3 输液异常（规则 12 -> 11，规则编号重排）
- **移除** `scenario.py` 的 `get_infusion_state()` + infusion_anomaly 场景
- **移除** `test_fusion.py` 的 test_infusion_anomaly + 适配器冒烟输液段（测试 27 -> 26）
- **更新契约** `safety_event.json` event_type 枚举（移除 infusion_anomaly，14 类 -> 13 类）、`observation.json` source_type 枚举（移除 infusion）、`contracts/README.md`
- **更新** 前端 `App.vue` 事件标签映射、后端 `init.sql` 注释
- **更新 15 份文档**：事件字典/需求分析/架构设计/接口规范/测试用例/技术调研/PPT大纲/技术报告骨架/上传规范/技术报告第3-4-6-7章，统一"四源->三源""4类适配器->3类""14类事件->13类""12规则->11规则"

### 影响范围

- 事件类型 14 -> 13（移除 infusion_anomaly）
- 采集适配器 4 -> 3（Camera/BedSensor/Environment）
- 融合规则 12 -> 11
- 单元测试 27 -> 26（全绿）

---

## [v0.2.1] - 2026-07-27

### 文档（docs）

- 新增技术报告第 4/5/7/10 章：边缘端设计与实现、云端设计与实现、智能功能实现、部署与运维（1350 行）

---

## [v0.2.0] - 2026-07-27

### 新增（feat）- 边缘端功能补全

- **inference.py 推理引擎增强**：predictions 透传字段从 4 个扩展到 8 个（+tremor_score/position_duration/pose_keypoints/bbox），覆盖 fusion 所有规则；新增 `load_model()`/`rollback()` 模型版本管理；新增 `_build_evidence_refs()` 按风险等级填充脱敏证据指针（image/pose_keypoints）。
- **fusion.py 新增规则12 nurse_call 透传（P1）**：camera.call_requested=True 时生成 nurse_call 事件，补全契约 14 类事件中边缘端原本缺失的这一类。
- **fusion.py 规则2 bed_leave 双源校验**：床垫主导触发不变，新增 bbox 中心点床区多边形交叉验证（`BED_REGION_POLYGON` 环境变量配置），双源一致置信度 0.92，床垫误报置信度 0.50，未配置时退化为 0.85 向后兼容。
- **main.py handle_model_deploy 完整实现**：原 TODO 占位，现调用 `inference.load_model()`/`rollback()`，加载后立即上报 health 携带新 model_version + model_status，完成模型灰度发布闭环。
- **mqtt_client.py 修复 model/deploy|rollback 路由 bug**：原 `len(topic_parts)==3` 永远匹配不到 4 段主题，且 action 三元判断恒为 "deploy"，修正为正确路由。
- **scenario.py + camera.py nurse_call 透传链路**：nurse_call 场景注入 call_requested 标志，CameraAdapter 透传该字段。

### 文档（docs）

- 新增 `docs/02-边缘模型选型对比.md`：亚伦任务1，对比 YOLOv8n-pose/v10n/v11n/MediaPipe、OpenVINO/RKNN/TensorRT、INT8 量化方案，含 14 类事件支撑度对照、模型转换流水线、后处理算法、性能目标（实测待填）。
- 新增 `docs/13-技术报告-第3章-架构.md`：亚伦负责章节，云边端三层架构、8 服务划分、部署演进、技术选型汇总。
- 新增 `docs/14-技术报告-第6章-通信与数据.md`：亚伦负责章节，MQTT 主题树、信封设计、14 类事件数据模型、QoS 可靠性、通信安全。

### 测试（test）

- edge-agent 测试从 17 项增至 **27 项**：新增 inference 全字段透传/evidence_refs 填充/模型版本管理、nurse_call 透传（含端到端链路）、bed_leave 双源校验（双源一致/床垫误报/无多边形降级）3 类共 10 项测试。

---

## [v0.1.1] - 2026-07-27

### 修复（fix）

- **修复测试无法被 `unittest discover` 发现的问题**：`edge-agent/tests/test_fusion.py`（17 项）与 `training-coordinator/tests/test_scheduler.py`（4 项）原以裸函数形式定义，`unittest` 默认只发现 `TestCase` 子类，导致 README 中的 `python -m unittest discover` 命令返回 `Ran 0 tests`。已重构为 `unittest.TestCase` 子类，现 discover 与直接运行两种方式均能发现并执行全部 21 项测试。
- **修复 `test_device_fault` 导入错误**：原 `from src.adapters.base import Quality` 找不到模块（文件顶部用的是 `from adapters.base import ...`），导致第 17 项测试报 `ModuleNotFoundError`。已统一为顶部导入，17 项测试全绿。
- **修复 `inference.py` 字段命名与契约不一致**：`InferenceResult` 原用 `evidence_ref`（单数），但 `contracts/safety_event.json`、`cloud-backend`（database.py / mqtt_handler.py / main.py）、`fusion.py` 均用 `evidence_refs`（复数）。已统一为 `evidence_refs`，同步更新 docstring、生成脚本与骨架交付说明文档。
- **修复云端 MQTT 断连重连阻塞**：`cloud-backend/app/mqtt_handler.py` 的 `_on_disconnect` 原在 paho 回调线程内 `time.sleep` 后手动 `reconnect`，会阻塞网络循环线程导致消息处理停滞。已改用 paho 原生 `reconnect_delay_set()` 自动管理退避重连，回调仅记录日志。

### 变更（chore）

- `.gitignore` 新增 `*.docx` 规则：调研报告、演讲稿等 docx 文档产物不再纳入版本库（源脚本保留在 `scripts/`，可随时重新生成）。
- 移除已跟踪的 `docs/*.docx`（4 份），改由脚本生成，本地文件保留。

### 文档（docs）

- 修正 `docs/12-上传规范.md`：PR 测试命令由 `pytest` 改为 `unittest discover`（项目实际用标准库 unittest）；更新 commit 数与代码行数统计；检查清单同步更新。
- 新增 `CHANGELOG.md`。

---

## [v0.1.0] - 2026-07-21

### 新增（feat）- 首个骨架版本

- **edge-agent 边缘代理**：4 类采集适配器（摄像头 / 床垫压力 / 输液 / 环境）+ 推理引擎空壳 + 11 条规则融合引擎 + 场景驱动器 + SQLite 离线缓存 + MQTT 客户端（QoS 1，断网补传）。
- **cloud-backend 云端事件中心**：FastAPI + 11 表 ORM（wards / beds / edge_nodes / observations / safety_events / alert_tasks / event_dispositions / model_versions / model_deployments / audit_logs / shift_summaries）+ 21 个 REST API + WebSocket 实时推送 + MQTT 消息处理。
- **training-coordinator 协同训练调度**：TrainingScheduler 骨架 + 三阶段策略枚举（sync_fedavg / async_stale / robust）+ 4 项冒烟测试。
- **cloud-frontend 护士站工作台**：Vue 3 + Vite，三栏布局（病区床位 / 告警工作台 / 交接班面板）+ WebSocket 实时事件 + P1 闪烁告警。
- **MQTT 消息契约**：6 份 JSON Schema（envelope / observation / safety_event / alert_ack / node_health / model_deploy）+ 主题树规范 + 事件状态机。
- **Docker Compose 一键编排**：8 服务（mqtt-broker / mysql / cloud-backend / training-coordinator / cloud-frontend / 3 × edge-bed）。
- **10 项智能功能**：坠床预警 / 长时间静止 / 异常体态 / 抽搐检测 / 压疮预防 / 设备故障 / 交接班摘要 / 环境自适应 / 空气质量联动 / 床位占用可视化。
- **文档体系**：13 份 Markdown（事件字典 / MQTT 契约 / 骨架说明 / 团队分工 / 需求分析 / 架构设计 / 接口规范 / 测试用例 / 部署指南 / 技术调研 / 演示 PPT / 技术报告 / 上传规范），约 6500 行。
- **单元测试**：edge-agent 17 项 + training-coordinator 4 项（注：v0.1.0 阶段需直接运行测试文件，discover 不可用，此问题在 v0.1.1 修复）。

---

## 版本号规划

| 版本 | 阶段 | 目标 |
|------|------|------|
| v0.1.x | 骨架 + bug 修复 | 框架可用、测试可发现、契约一致 |
| v0.2.x | 模型接入 | 真实 YOLO/姿态模型接入 inference.py、1 床位硬件闭环 |
| v0.3.x | 协同训练 | FedAvg 同步基线 + 半异步陈旧度加权 |
| v0.4.x | 扩散模型 | 困难样本生成 + 数据集扩充 |
| v1.0.0 | 赛事交付 | 全链路打通 + 演示视频 + 申报材料 |
