# 变更日志

> 智慧病房云边协同系统版本变更记录。
> 版本号规则与提交规范见 [docs/12-上传规范.md](docs/12-上传规范.md)。
> 格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循语义化版本 SemVer。

---

## [v0.4.3] - 2026-08-26

### 新增（feat）

- **真实 Qwen2.5-14B/vLLM 端到端链路验证**（8/23，P1 亚伦 + P6 烽亮环境支持）：CLOUD/HYBRID 各 1 条真实请求（request_mode=cloud/hybrid、timeout_ms=10000），vLLM 真实推理 `judgment=confirm`、latency≈390–545ms；边缘日志 / MQTT 抓包 / SQLite / 云端阶段化日志四层证据 trace 全程一致。证据 `docs/evidence/20260823_vllm_real_link_5801d19/`
- **容错集成测试 阶段1–6 全部通过**（8/25–26，P1/P6/P7 三方协同，每场景 20 次）：①重复 request 去重（云端 requests=1/duplicates=19/responses=20）②重复 response 幂等（首条生效，19×duplicate 忽略，SQLite 仅 1 条）③非法 judgment（20 条 bogus → 20/20 fallback_edge/invalid_judgment，0 误判 completed）④未知 event（20 个伪造 event_id 落库 0 条）⑤trace 不匹配（20×trace_mismatch，completed=0）⑥云端不可用超时回退+恢复（25/25 fallback_edge/timeout，事件未丢失；恢复后正常 completed）。正式归档 `docs/evidence/20260825_fault_test_stage1-6/`（23 文件）
- **辅助脚本**：`scripts/send_duplicate_requests.py`（重复 request 发送）、`scripts/capture_mqtt_fault.py`（参数化 MQTT 抓包）
- **统一测试入口** `scripts/run_all_tests.py`：一条命令跑完 5 个套件（各自独立子进程），支持子串过滤，任一失败打印原始输出并以退出码 1 结束。分进程是必需的——cloud-backend / cloud-llm-service / diffusion-service / training-coordinator 顶层包**都叫 `app`**，同一解释器内 `sys.modules["app"]` 只能有一个，合并进一条 pytest 命令必然 collection error

### 修复（fix）

- **边缘端云端超时语义与死代码**（`edge-agent/src/main.py`）：`25b4722`/`70185a8` 新增的早返回分支使原 `status="timeout"` 分支永久不可达，`test_timeout_response_preserves_edge_result_and_marks_timeout` 因此变红。删除该死代码块（−20 行），并让云端主动超时回传使用 `reason="cloud_timeout"`，与本地超时守护线程的 `reason="timeout"` 区分（两者 `status` 统一为 `fallback_edge`）。阶段 6 证据全部走本地线程路径（`云端不可用，回退边缘`×25、`识别云端推理超时`×0），结论不受影响
- **上报日志被三元表达式吞掉**（`edge-agent/src/main.py`）：`print(f"..." if enhancement.llm_response else "")` 的三元作用于整个 f-string，`llm_response` 为 None 时整行事件上报日志不打印；三元收窄到 ttft 片段
- **Windows 控制台 emoji 崩溃**（`edge-agent/src/main.py`）：上一条修好后立即暴露——路由标记 `🟢/☁️/🔀/⚠️/🚨` 在 GBK 控制台抛 `UnicodeEncodeError`，宿主机直跑边缘代理时任一 hybrid 路由事件都会打断上报循环（Docker 内 UTF-8 无此问题）。新增 `_force_utf8_stdio()` 兜底
- **告警确认重复入库**（`cloud-backend`）：云端自身订阅 `ward/+/alert/+/ack`，而 `/api/events/{id}/ack` 先 `publish_ack()` 再本地处理，同一条确认经 broker 回环被处理两次，写出两条 `event_dispositions` 与两条 `audit_logs`（本地无 broker 时 `publish_ack` 提前返回，故此前未暴露）。`_handle_ack` 提升为公开 `apply_ack`（保留旧名别名），按信封 `source == "cloud"` 跳过自投递
- **时间口径不一致**（`cloud-backend`）：`datetime.utcnow()`（naive）与 `datetime.now(timezone.utc)`（aware）混用于 DATETIME 列查询，`/api/events` 与 `/api/events/by-type` 的 24 小时窗口口径并不相同；`utcnow()` 亦自 Python 3.12 起废弃。新增 `app/timeutil.py`，10 处调用统一到 `utc_now()` / `utc_now_iso()` / `parse_ts()`
- **diffusion-service MQTT 重连阻塞网络循环**：`_on_disconnect` 内 `time.sleep()` + 手动 `reconnect()` 会阻塞 paho 回调线程；改用 `reconnect_delay_set()`，与 cloud-backend 一致
- **diffusion-service 事件缓存淘汰错误**：`sorted(keys)[:100]` 排的是 event_id（UUID）字典序而非到达先后，会随机淘汰刚缓存的事件，导致误报回流取不到上下文；改为按 dict 插入序淘汰
- **`@property` 带参数**（`training-coordinator/app/scheduler.py`）：`SemiAsyncScheduler.staleness_of` / `FedBuffScheduler.staleness_of` 声明为 `@property` 却带 `client_id` 参数，调用必然 `TypeError`；去掉装饰器改为普通方法（无调用方，属死代码）
- **`edge-agent/conftest.py` 路径错误**：`dirname(__file__)/../src` 解析到不存在的 `smart-ward/src`（文件在 `edge-agent/` 根，`..` 多余），插入的是无效路径、等于空转；更正为同级 `src` 并加 `isdir` 守卫

### 重构（refactor）

- **cloud-backend API 分层**：`app/main.py` 由 790 行拆为 108 行，仅保留应用装配（lifespan / CORS / 统一异常 / WebSocket / 健康检查）；21 个业务端点按领域移入 `app/routers/{wards,events,system,shifts}.py`，进程级单例移入 `app/deps.py`（`app.main.mqtt_handler` 引用路径保持可用）。拆分后经三重核对：端点清单与 `git show HEAD` 逐条 diff 无差异、运行时 OpenAPI 18 path / 21 operation 一致、`/api/events/by-type` 未被 `/{event_id}` 抢占
- **FastAPI 生命周期现代化**：`@app.on_event("startup"/"shutdown")` 改为 `lifespan` 上下文管理器（与 diffusion-service 一致），`asyncio.get_event_loop()` 改为 `get_running_loop()`

### 测试

- 新增 4 项回归：cloud-backend ack 回环去重 2 项（自投递跳过 / 外部来源仍处理）、diffusion-service 事件缓存淘汰 2 项（按到达序淘汰 / 无 event_id 忽略）
- 全量：`edge-agent` 100 / `cloud-backend` 61 / `training-coordinator` 16 / `cloud-llm-service` 18 / `diffusion-service` 13，`contracts` 7 项含在 edge-agent 内，全部通过；`docker compose config` 通过

### 文档（docs）

- **`docs/19-项目进度与下一步任务.md`**：§2.5 cloud-llm-service "真实 14B 运行环境尚未验证"缺口闭环；新增 §7 增量进展章节；测试计数与代码行数同步到当前值
- **SQLite 原始查询证据**：`docs/evidence/sqlite-query-vllm.txt`（解析版）/ `sqlite-query-vllm-raw.txt`（纯原始输出）/ `sqlite_raw_query.py`（可复现脚本）
- **`README.md`**：补统一测试入口用法；测试计数由 90/15/59/13/11 更正为 100/61/16/18/13；新增"不要把多个服务合并进同一条 pytest 命令"的说明与原因

### 说明

- 过程文件与中间 zip 统一移入 `docs/temp-evidence/`（该目录不入库）；正式归档以 `docs/evidence/20260825_fault_test_stage1-6/` 与 `docs/evidence/20260823_vllm_real_link_5801d19/` 为准

---

## [v0.4.2] - 2026-08-19

### 新增（feat）

- **云边协同真实联调取证（7 场景，每场景 ≥20 次）**（`3f408a5`）：正常链路、重复去重、超时回退、非法 judgment、未知事件、trace 不匹配、断网自治+恢复补传——证据入库 `docs/evidence/mqtt-sync/`（`scenario1..7_*.json` + `README.md`）
- **演示视频脚本**（`aa8b60a`，P6 烽亮）：5-8 分钟 6 段式结构含拍摄要求
- **Jetson Orin Nano 一键部署脚本 + 部署手册**（`9527e90`，P6 烽亮）：`setup_jetson.sh` + `docs/21-Jetson部署手册.md`，含性能指标测量说明
- **训练灰度发布/回滚演示 + edge health 证据**（`7c60902`，P4 振鑫）：`demo/run_release_demo.py` v1 健康/v2 失败自动回滚
- **diffusion-service 骨架模板调优 + 轮廓渲染管线**（`a2015de`，P6 烽亮）
- **护士站 UI 全量重构**（`4f1b855`，P2 景彬）：浅色临床风 + 多视图导航（总览/床位/告警/交班/系统 5 视图），Tailwind/PostCSS 移除，统一设计令牌由 `src/styles/theme.css` 驱动
- **边缘端交接班小 agent**：基于 YOLO 采集/融合事件数据 + 本地病人档案（`edge-agent/config/patients.json`），由边缘 LLM 生成**每床、带时间信息的自然交接班记录**——新增 `LLMAdvisor.generate_shift_handover`（mock 数据驱动 / real GGUF 双模式）、SQLite `shift_handovers` 表、独立脚本 `scripts/gen_shift_handover.py`（写库 + 导出 Markdown），+7 项测试
- **云端 LLM 推理全链路追踪日志**（`8b80d46`，P7 彦晗）：`mqtt_handler.py` 阶段化 `cloud_inference` JSON 日志（received/validated/inference_started/completed/dedup_cache_stored/response_published），联调取证中验证 trace_id 跨服务全程一致

### 修复（fix）

- **hybrid 路由请求对齐契约**（`667abbd`）：HYBRID 路径 `request_mode` 由 `review` 改为 `hybrid`，与 `contracts/inference_request.json` 枚举及 `cloud-llm-service/schemas.py` 的 `RequestMode` 对齐（联调中发现）
- **cloud-backend 交接班摘要测试时间敏感性**（`bba3242`）：`test_generate_shift_summary` 注入固定 `occurred_at`（当日 UTC 02:00，落在 day 班次窗口内），消除对运行时刻的依赖
- **`mqtt_cloud_sync_test.py` 重复场景判据修正**（`3f408a5`）：云端按 `event_id` 幂等去重——同一 event_id×N，推理仅执行 1 次（`requests+1`）、其余 N-1 次复用缓存（`duplicates+N-1`），但每请求均回响应（便于边端重试）；脚本增加 `/stats` 交叉验证

### 文档（docs）

- **`docs/22-云边联调验证记录.md` 补充 2026-08-19 七场景取证完成章节**：7 场景全部通过，附完整证据索引
- **`docs/23-云端14B环境确认记录.md`（P6 烽亮）**：AutoDL RTX 4090 + vLLM 0.10.1 实测启动命令、验证结果

### 测试

- `edge-agent` 90 项、`cloud-backend` 59 项（含时间敏感测试修复）、`training-coordinator` 15 项、`cloud-llm-service` 13 项（pytest）、`diffusion-service` 11 项（pytest）、`contracts` 7 项 全部通过
- docker compose config 通过

### 当前限制

- Jetson Orin Nano 实机性能数据、真实视觉模型与 LLM 并行运行时的资源占用待真机实测（脚本与手册就绪，缺设备）
- 断网保持率统计（≥90% 三指标分开统计）尚未产出正式报告（断网自治与恢复补传功能已在 7 场景取证中验证）
- 三路线对比报告（1.5B/0.5B/14B 准确率/F1/TTFT/RSS/吞吐）、NLU 评测集 500+ 条（截止 8/25）
- 最终材料冻结（技术报告/PPT/提交包一致性）+ 5-8 分钟演示视频录制（截止 8/28-31）

---

## [v0.4.1] - 2026-08-10

### 新增（feat）

- **跌倒检测切换至任务书方案**：YOLOv8 + ShuffleNetV2+SA 双模型（`985d77d`），UR Fall Detection Dataset 全量评测脚本与基线（`169cf8e`/`628ebc3`/`80de0f6`），修复 stride 采样口径后帧级准确率 95.78%、召回率 77.50%、F1 0.78，片段级 100%（`9278eb0`），证据见 `docs/21-UR-Fall数据集与跌倒评测说明.md`
- **云端超时独立守护线程**：与主循环 `TICK_SECONDS` 解耦（`7348d7a`）
- **日常活动识别接入 MQTT 上报链路**：`observation.activity` 与事件 `details` 透传（`41a0f2f`）
- **mock 摄像头日常活动模拟**：姿态→活动标签映射（sit/stand/lie/bend/fall），产生与 yolo 模式同构的切换事件（switched/previous/since），mock 演示模式亦可展示病人日常活动（+5 项测试）
- **云边推理契约**：`contracts/inference_request.json` + `inference_response.json` Schema 与 7 项契约测试（`5b22b35`）
- **边缘 LLM 性能基准脚本** `scripts/bench_jetson.py`：Jetson/x86 TTFT/RSS/吞吐测量（`03b77fd`）
- **协同训练 FedBuff 异步聚合 + MiniLLM/Hinton 蒸馏**（`dddfcf3`，P3 建鸿/P4 振鑫/P7 彦晗）
- **全员任务清单看板生成脚本** `scripts/gen_task_board.py`（`804af19`）

### 修复（fix）

- **cloud-llm-service 适配 vLLM chat API**（`226f68f`）：`/v1/completions` → `/v1/chat/completions`，默认端口 8000 → 8501，模型名对齐 vLLM 注册名 `Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4`，请求格式 `prompt` → `messages`，响应解析 `choices[0].message.content`
- **同步 docker-compose 的 `VLLM_ENDPOINT` 默认值**为新端点（`fb70712`），确保 Compose 部署下适配生效
- **对齐 `model_name`/`model_version`** 与 vLLM 注册名，请求体模型名改为引用 `self._model_name` 防止漂移（`bcf24c7`）
- **修复 cloud-backend ack 主题路由索引 bug**：`topic_parts[3]` → `[2]`，此前经 Broker 转发的告警确认消息被丢弃（测试驱动发现）
- **云端研判回写不再被事件幂等拦截**：cloud-backend `_handle_event` 改为"首达入库、回写更新"——边缘收到云端 judgment 后重报的事件携带 `details.cloud_inference` 时更新详情与状态，并广播 `event_update`；无回写的重复上报仍保持幂等跳过（+3 项测试）
- **护士站展示云端二次研判**：事件卡新增云端判断徽章（☁️ 确认/误报/升级），详情抽屉新增云端研判区块（judgment/护理建议/置信度/延迟/trace），WebSocket 处理 `event_update` 实时刷新——"摄像头→YOLO→边缘LLM→云端LLM→前端展示"全链路闭环
- 融合测试禁用夜间判定，消除时间敏感失败（`426456b`）

### 文档（docs）

- 文档与仓库治理对齐：模型选型、周报脚本、NLU 说明、数据集忽略（`f79ae93`）
- README/技术报告第 5 章/测试用例/上传规范同步当前实现状态与测试口径（78/15/9）

### 测试

- `edge-agent` 90 项、`training-coordinator` 15 项、`cloud-backend` 59 项（unittest）、`cloud-llm-service` 13 项（pytest）全部通过
- 合并 P7 彦晗 cloud-llm 重构：配置环境变量化（CLOUD_LLM_MODEL_NAME/VERSION、VLLM_MAX_TOKENS/TEMPERATURE、CLOUD_DEDUP_TTL_SECONDS）、paho 2.x CallbackAPIVersion、CachedInference 去重统计、Pydantic 契约校验（d236541，已实测验证）
- cloud-backend 新增测试：SQLite 内存库 + 假 paho/WS，无需真实 MySQL/MQTT

### 当前限制

- 云端真实 Qwen2.5-14B/vLLM 运行环境验证、端到端真实 Broker 联调取证（7 场景）与断网保持率测试尚未完成
- Jetson Orin Nano 实机性能、真实视觉模型同时运行时的资源占用和精度对比尚未完成

---

## [v0.4.0 边缘侧补充] - 2026-07-31

### 新增 - 边缘 LLM 双路径

- 新增 `LLMEngine` 的 real/mock 双模式配置，支持 GGUF 模型加载、mmap、上下文窗口、batch、CPU 线程和生成长度配置。
- 新增 Qwen2.5-1.5B Q4 质量优先路径，保留较强的事件语义增强和护理建议能力。
- 新增 Qwen2.5-0.5B Q4 低内存路径，新增 `docker-compose.compact.yml` 和模型下载脚本，支持按 Compose override 切换。
- 缩短边缘护理 Prompt，限制生成长度，降低首 token 延迟和推理工作区占用。
- 在 health 状态中上报模型名称、模型版本和 LLM runtime 配置。

### 新增 - 边缘侧云边协同闭环

- 新增 `InferenceTracker`，按 `event_id + trace_id` 管理 pending 请求生命周期。
- MQTT 推理请求支持外层和 payload 内的 `event_id`、`trace_id`，便于云端回传关联。
- 新增云端响应幂等处理，重复响应、未知事件和 trace 不匹配响应不会重复消费。
- 支持 `confirm`、`reject`、`escalate` 三类云端判断，并分别映射到边缘事件状态。
- 云端响应会写回 SQLite 事件 payload/state，并记录云端置信度、建议、延迟和接收时间。
- 云端发送失败、响应超时或返回非法 judgment 时，自动记录失败原因并继续使用边缘决策。
- TaskRouter 增加云端成功数和云端结果延迟统计。

### 性能实测

- Windows/x86 主机、上下文 512、batch 128、8 个 CPU 线程下，Qwen2.5-1.5B Q4 热身后 TTFT 约 `31.9ms`，峰值 RSS 约 `1658MB`。
- 同一环境下，Qwen2.5-0.5B Q4 热身后 TTFT 约 `19.8ms`，峰值 RSS 约 `516MB`。
- 以上数据不代表 Jetson Orin Nano 实测结果；Jetson 冷启动、热身后 TTFT、总内存和吞吐量仍待验证。

### 文档与配置

- 更新 `README.md`，同步当前 8 个 Compose 服务、38 项边缘测试、8 项训练测试、真实 LLM 启动方式和性能证据。
- 更新 `.env.example`、`docker-compose.yml` 和 `.gitignore`，补充 LLM 参数、模型挂载和模型文件忽略规则。

### 测试

- `edge-agent`：38 项测试全部通过。
- `training-coordinator`：8 项测试全部通过。
- Python 源码编译检查通过。
- 主 Compose 与低内存 Compose 配置检查通过。

### 当前限制

- 云端 LLM 消费者、Qwen2.5-14B/vLLM 服务和真实 MQTT 端到端链路尚未纳入当前 Compose。
- Jetson Orin Nano 实机性能、真实视觉模型同时运行时的资源占用和精度对比尚未完成。
- 前端本地构建环境仍需补齐依赖并完成 Docker 镜像构建验证。

---

## [v0.4.0] - 2026-08-04

### 新增（feat）- 护士站前端可观测性看板（P2 景彬）

围绕任务书 P2“护士站 Vue 前端与可观测性”补齐路由 / 性能 / 网络 / 状态看板：

- **推理链路 route 展示**：`src/utils/eventMeta.js` 统一判定 edge/cloud/hybrid（`details.route` 显式字段 > `cloud_reviewed` > 云端模型名 > 默认边缘）；事件卡片、病床卡片、详情抽屉三处展示 `⚡边缘 / ☁️云端 / 🔁协同` 徽章
- **性能指标展示**：事件卡与详情抽屉展示模型名称@版本、边缘推理耗时、TTFT、云端延迟、峰值内存（`details` 读取，缺失显示 —）
- **系统状态栏**：新增 `SystemStatusBar.vue`，常驻展示云端链路/云端 API/边缘节点/离线缓存/MQTT/最近断开六项状态；断网橙色横幅“边缘继续本地值守”、恢复绿色横幅（恢复时间+重连次数+补传条数）
- **WebSocket 可观测**：`api/websocket.js` 增加连接状态跟踪（connecting/connected/reconnecting/disconnected）、指数退避重连、重连计数、消息计数、状态回调
- **事件详情抽屉**：新增 `EventDetailDrawer.vue`，展示 event_id/trace_id/node_id、链路摘要、性能四宫格、模型、时间线、规则命中、证据引用、处置记录，trace 可复制用于截图标注
- **超时/降级状态**：`resolveFallback` 判定（`details.state_fallback` 或等待超阈值），事件卡橙色虚线徽章 + 右侧提示条 + “超时/降级”筛选
- **调试注入增强**：`SceneInjector.vue` 支持选择推理链路、模拟网络状态（在线/降级/断网）、模拟云端超时回退
- **病床卡片增强**：`BedCard.vue` 增加最新事件 route 徽章、节点网络状态、模型版本
- **修复** `package-lock.json` 与 `package.json` 不一致（旧 0.1.0 lockfile 缺失 element-plus/tailwindcss/postcss/autoprefixer），重新生成 lockfile

- **节点心跳检测**：SystemStatusBar 增加"节点心跳"芯片，对比 REST `/api/nodes` 的 last_heartbeat 与当前时间，Broker 断开时心跳过期自动变橙/红（实测 mqtt 停/启场景）
- **截图标注**：新增 `scripts/annotate_screenshot.py` / `scripts/annotate_all_screenshots.py`，按任务书 §6 给全部截图叠加"场景|时间|trace_id"标注条；详情抽屉截图标注真实 trace_id
- **录屏素材**：新增 `scripts/record_demo_video.py`（Playwright 录制演示流程 webm），MQTT 场景截图脚本 `scripts/capture_mqtt_reconnect.py`

### 文档

- 新增 `docs/20-护士站Vue前端使用说明与演示脚本.md`：页面操作步骤、5~8 分钟演示脚本、异常场景演示、截图素材规范、联调字段说明
- 截图索引 `docs/evidence/screenshots/README.md` 补充 MQTT 场景截图与录屏素材清单

### 影响范围

- 前端页面 v0.3.0 -> v0.4.0
- 无后端接口破坏性变更；新增字段（route/ttft_ms/cloud_latency_ms/memory_mb/network/state_fallback）走 `details` JSON，向后兼容

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
