const fs = require('fs');
const path = require('path');
const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  Table,
  TableRow,
  TableCell,
  HeadingLevel,
  AlignmentType,
  LevelFormat,
  WidthType,
  BorderStyle,
  ShadingType,
  TableOfContents,
  Header,
  Footer,
  PageNumber,
  PageBreak,
  VerticalAlign,
} = require('docx');

const output = path.resolve(__dirname, '..', '项目任务书-2026执行版.docx');
const CONTENT_WIDTH = 9506;
const CELL_MARGINS = { top: 90, bottom: 90, left: 120, right: 120 };
const COLORS = {
  navy: '1F4E78',
  blue: 'D9EAF7',
  pale: 'F4F7FA',
  green: 'E2F0D9',
  yellow: 'FFF2CC',
  red: 'FCE4D6',
  gray: '666666',
  border: 'B7C9D6',
};

const border = { style: BorderStyle.SINGLE, size: 1, color: COLORS.border };
const borders = { top: border, bottom: border, left: border, right: border };

function run(text, options = {}) {
  return new TextRun({ text, font: 'Microsoft YaHei', size: options.size || 21, color: options.color, bold: options.bold, italics: options.italics });
}

function p(text = '', options = {}) {
  return new Paragraph({
    alignment: options.alignment,
    spacing: options.spacing || { after: 120, line: 320 },
    indent: options.indent,
    keepNext: options.keepNext,
    pageBreakBefore: options.pageBreakBefore,
    children: options.children || [run(text, options)],
  });
}

function rich(label, value, options = {}) {
  return new Paragraph({
    spacing: options.spacing || { after: 100, line: 300 },
    children: [run(label, { bold: true, color: COLORS.navy }), run(value)],
  });
}

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [run(text, { bold: true })] });
}

function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [run(text, { bold: true })] });
}

function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [run(text, { bold: true })] });
}

function bullet(text, reference = 'bullets') {
  return new Paragraph({
    numbering: { reference, level: 0 },
    spacing: { after: 70, line: 280 },
    children: [run(text)],
  });
}

function numbered(text, reference = 'numbers') {
  return new Paragraph({
    numbering: { reference, level: 0 },
    spacing: { after: 70, line: 280 },
    children: [run(text)],
  });
}

function cell(text, width, options = {}) {
  const children = Array.isArray(text) ? text : [p(String(text), { spacing: { after: 0, line: 260 }, size: options.size || 19, bold: options.bold, color: options.color || (options.fill === COLORS.navy ? 'FFFFFF' : undefined) })];
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders,
    margins: CELL_MARGINS,
    shading: options.fill ? { fill: options.fill, type: ShadingType.CLEAR } : undefined,
    verticalAlign: options.verticalAlign || VerticalAlign.CENTER,
    children,
  });
}

function table(headers, rows, widths, options = {}) {
  const header = new TableRow({
    tableHeader: true,
    children: headers.map((item, index) => cell(item, widths[index], { fill: options.headerFill || COLORS.navy, bold: true, size: 19 })),
  });
  const body = rows.map((row, rowIndex) => new TableRow({
    cantSplit: true,
    children: row.map((item, index) => cell(item, widths[index], { fill: rowIndex % 2 ? COLORS.pale : 'FFFFFF', size: 18 })),
  }));
  return new Table({
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths: widths,
    rows: [header, ...body],
  });
}

function spacer() {
  return p('', { spacing: { after: 90, line: 100 } });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

function statusCell(status) {
  const fill = status === '已完成' ? COLORS.green : status === '进行中' ? COLORS.yellow : COLORS.red;
  return [p(status, { spacing: { after: 0 }, alignment: AlignmentType.CENTER, bold: true, size: 18 })];
}

const children = [];

// Cover
children.push(spacer(), spacer(), spacer());
children.push(p('智慧病房云边端协同系统', { alignment: AlignmentType.CENTER, size: 38, bold: true, color: COLORS.navy, spacing: { after: 220 } }));
children.push(p('项目任务书（2026 执行版）', { alignment: AlignmentType.CENTER, size: 30, bold: true, spacing: { after: 420 } }));
children.push(p('面向 2026 年 8 月 31 日最终提交的团队执行与验收依据', { alignment: AlignmentType.CENTER, size: 22, color: COLORS.gray, spacing: { after: 260 } }));
children.push(spacer(), spacer());
children.push(table(['项目项', '当前约定'], [
  ['项目名称', '智慧病房云边端协同系统'],
  ['执行版本', '2026 执行版；以 master 合并提交 ebac0a3 为基线'],
  ['编制日期', '2026 年 7 月 31 日'],
  ['最终截止', '2026 年 8 月 31 日'],
  ['适用对象', 'P1 亚伦、P2 景彬、P3 建鸿、P4 振鑫、P5 先伟、P6 烽亮、P7 彦晗'],
], [2100, 7406], { headerFill: COLORS.navy }));
children.push(spacer());
children.push(p('使用说明：本任务书是当前阶段的执行版，不替代已有历史任务书。所有“已完成”必须以代码、测试日志或截图为证；所有“待完成”必须形成可复查的代码提交、测试结果或材料文件。', { size: 19, color: COLORS.gray, spacing: { after: 100, line: 300 } }));
children.push(pageBreak());

// TOC and overview
children.push(h1('目录'), new TableOfContents('目录', { hyperlink: true, headingStyleRange: '1-3' }), pageBreak());

children.push(h1('一、项目概况与执行原则'));
children.push(h2('1.1 项目范围'));
children.push(p('本项目面向一个病房 W-01、三张床位 B01～B03，构建“端侧感知、边缘推理、云端协同、护士站处置”的闭环系统。系统覆盖摄像头、床垫和环境三类数据源，支持跌倒、离床、夜间徘徊、长时间静止、环境异常、门区异常离开、护士呼叫等病房安全事件，并通过 MQTT、SQLite 离线缓存、云端事件中心和 Vue 护士站完成事件的发现、研判、确认、处置、审计和展示。'));
children.push(h2('1.2 当前基线'));
children.push(table(['维度', '当前事实', '对后续工作的影响'], [
  ['代码基线', '当前工作分支 codex/edge-llm-cloud-sync 的 HEAD 为 74e3a44，远端 origin/master 为 ebac0a3；两者均包含边缘 LLM 双路径和边缘侧云边闭环。本地 master 仍为 f3f7bba，尚未同步远端 master。', '后续开发从最新 origin/master 或当前功能分支继续；最终提交前由 P3 确认本地 master 与远端 master 一致。'],
  ['测试基线', 'edge-agent 38 项、training-coordinator 8 项测试通过；Python 编译检查和 Compose 配置检查通过。', '新增功能不得降低现有测试通过率；联调测试需要补充到可复现脚本或日志。'],
  ['边缘模型', '1.5B Q4：热身后 TTFT 约 31.9ms，峰值 RSS 约 1658MB；0.5B Q4：TTFT 约 19.8ms，峰值 RSS 约 516MB。数据来自 Windows/x86。', '1.5B 作为质量优先路径，0.5B 作为低内存兜底；两条路径必须在 Jetson 上重新实测。'],
  ['云端模型', 'cloud-llm-service/app 目前为空；云端消费者、Qwen2.5-14B/vLLM 和真实 Broker 端到端链路尚未接入 Compose。', 'P7 为第一责任人，P6 负责环境，P1 负责边缘联调；这是当前最高优先级缺口。'],
  ['前端构建', 'cloud-frontend 具备 Vue/Vite/ECharts 页面和 Dockerfile；当前 npm run build 实际失败，Rollup 无法从 src/main.js 解析 element-plus，Docker 构建尚待验证。', 'P2 先修复依赖安装/锁定和 Docker 构建，再接入协同指标和异常状态。'],
  ['未纳入主线文件', '.zcode、对话总结、宿主机跌倒检测脚本、报告生成脚本等仍在工作区，未作为本次 master 基线的一部分。', '未经 P3 记录和对应负责人确认，不得把实验文件直接作为最终交付物。'],
], [1550, 4850, 3106]));
children.push(h2('1.3 执行原则'));
['先闭环，后扩展：8 月 20 日前优先打通真实请求、响应、回写和前端展示，不以新增功能替代主链路。',
 '先证据，后结论：每个指标必须有测试命令、环境、样本量、原始日志和汇总表；Windows/x86 结果不得冒充 Jetson 结果。',
 '双路径并行：1.5B 保留质量优先能力，0.5B 保证 8GB Jetson 场景的低内存可运行；最终采用哪条路径由 P1、P5 根据实测数据共同确认。',
 '接口先行：云端和边缘端围绕 event_id、trace_id、judgment、confidence、advice、latency_ms 共同验收，字段变更必须同步 Schema、代码和文档。',
 '材料可追溯：报告、视频、截图必须能够回指到具体提交、版本、命令和测试数据。'].forEach(item => children.push(bullet(item)));

children.push(h1('二、当前完成情况与问题清单'));
children.push(h2('2.1 已完成内容'));
['边缘 LLM real/mock 双模式推理引擎，支持 GGUF、mmap、上下文窗口、batch、线程数和最大生成长度配置。',
 'Qwen2.5-1.5B Q4 质量优先路径、Qwen2.5-0.5B Q4 低内存路径，以及对应的 Compose override 和模型下载脚本。',
 '边缘侧 InferenceTracker，支持 event_id + trace_id 关联、pending 生命周期、超时回退、重复响应幂等和非法 judgment 处理。',
 '云端响应 confirm/reject/escalate 写回 SQLite 事件状态和 payload，并记录置信度、建议、延迟与接收时间。',
 'TaskRouter 已具备置信度、复杂度、网络状态的路由决策框架及云端统计字段。',
 'README、CHANGELOG、.env.example、docker-compose 配置和现有 46 项测试已同步到主线。'].forEach(item => children.push(bullet(item)));
children.push(h2('2.2 必须解决的问题'));
children.push(table(['优先级', '问题', '责任人', '完成判定'], [
  ['P0', '云端 LLM 服务目录为空，真实 request/response 链路未实现。', 'P7 主责；P6、P1 协作', '云端订阅请求主题，调用模型或可替换 mock，按契约回传；真实 Broker 端到端通过。'],
  ['P0', 'Jetson Orin Nano 未完成实机性能和资源验收。', 'P1 主责；P6 提供环境；P5 记录数据', '冷启动、热身后 TTFT、峰值 RSS、吞吐量和视觉模型并行占用均有原始日志。'],
  ['P0', '边缘超时处理仍需独立于 TICK_SECONDS 的定时机制验证。', 'P1', '云端不响应时按配置超时回退，且不阻塞下一轮事件；有自动化测试。'],
  ['P1', '前端本地构建和 Docker 构建未完成验证。', 'P2', 'npm run build 和 docker compose build cloud-frontend 均成功，生成可访问页面。'],
  ['P1', '训练协调器已有框架，但版本一致性、异步陈旧度、蒸馏和回滚证据不足。', 'P4 主责；P5 协作', '至少一组可复现实验、版本表、聚合日志和回滚演示。'],
  ['P1', '病房 NLU 数据集和三种路线对比实验尚未形成正式报告。', 'P5', '不少于 500 条有标签样本，完成准确率、召回率、F1、延迟、RSS、断网保持率对比。'],
  ['P1', '最终报告、视频、答辩材料尚未按当前 master 状态统一。', 'P3 主责；全员供稿', '验收矩阵、技术报告、视频脚本、PPT 和提交包一致。'],
], [800, 3800, 1800, 3106]));

children.push(h2('2.3 截至 2026 年 7 月 31 日的完整进度')); 
children.push(p('以下进度以当前工作区实际检查结果、Git 分支关系和可复现命令为准。状态“已完成”只代表对应阶段交付已经具备证据，不代表整个项目已经完成；项目当前仍处于“边缘侧主线完成、云端和实机闭环待完成”的阶段。'));
children.push(table(['领域', '当前已完成与证据', '当前状态', '下一步与责任人'], [
  ['Git 与版本', '当前分支 codex/edge-llm-cloud-sync，HEAD 74e3a44；origin/master 为 ebac0a3；本地 master 为 f3f7bba，落后远端 master 1 个提交。', '功能分支完成；本地分支同步未完成', 'P3 在最终提交前同步本地 master、记录 PR/合并关系；全员从统一基线开发。'],
  ['边缘 LLM 双路径', '1.5B Q4 质量优先路径和 0.5B Q4 低内存路径已实现；主 Compose 与 compact Compose 已配置；模型目录已有 0.5B、1.5B 和 qwen3-4b 本地文件夹。', '已完成代码；实机验收未完成', 'P1/P6 在 Jetson 上测冷启动、热身后 TTFT、RSS、吞吐和视觉模型并行占用；P5 归档数据。'],
  ['边缘云边机制', 'event_id + trace_id、pending、超时回退、重复响应幂等、confirm/reject/escalate、SQLite 状态回写已实现；edge-agent 38 项测试通过。', '边缘侧已完成；云端真实响应未接入', 'P1 完善独立超时定时器和 Schema；P1/P7 完成真实 Broker request/response 联调。'],
  ['训练协调', 'training-coordinator 基础框架保留同步/异步策略；8 项测试实际通过。', '基础框架完成；训练闭环未完成', 'P4 补充陈旧度、一致性、版本发布、蒸馏和回滚证据；P5 提供统一评测集。'],
  ['云端 LLM', 'cloud-llm-service/app 当前为空，尚无云端消费者、Qwen2.5-14B/vLLM 适配器和服务健康检查。', '未开始，当前最高优先级阻塞', 'P7 从空目录实现最小 consumer 和 response；P6 准备运行环境；P1 负责边缘接收和回写。'],
  ['护士站前端', 'Vue/Vite/ECharts 页面源码和 Dockerfile 已存在；当前 npm run build 失败，错误为 Rollup 无法解析 element-plus。', '基线页面存在；构建阻塞', 'P2 修复依赖和构建；再接入路由、TTFT、RSS、云端延迟、网络和处置状态。'],
  ['性能与精度', 'Windows/x86 已有 1.5B TTFT 约 31.9ms、RSS 约 1658MB；0.5B TTFT 约 19.8ms、RSS 约 516MB。', 'x86 基线完成；Jetson/正式精度集未完成', 'P5 建立不少于 500 条 NLU 评测集，完成三路线延迟、资源、准确率、召回率、F1 和断网保持率。'],
  ['部署与演示', '主 Compose 和 compact Compose 配置校验均通过；完整镜像构建、云端环境、Jetson 环境和视频尚未验收。', '配置完成；部署演示未完成', 'P6 完成 Docker build、Jetson/云端环境和 5～8 分钟演示；P2/P7/P1 提供联动场景。'],
  ['项目材料', 'README、CHANGELOG 和配置说明已按边缘双路径更新；执行版任务书已生成。', '阶段材料完成；最终材料未冻结', 'P3 统一报告、验收矩阵、PPT、视频、截图和提交清单；所有数字回指证据。'],
  ['工作区未提交文件', '.zcode、对话梳理文档、宿主机跌倒检测脚本、报告生成脚本以及本任务书生成脚本仍未提交；其中部分属于实验或材料辅助文件。', '需分类处理', 'P3 逐项判断是否纳入最终提交；代码负责人补充提交说明，禁止把临时文件误当成主线功能。'],
], [1450, 4050, 1900, 2106]));
children.push(h3('按成员划分的当前状态'));
children.push(table(['成员', '已经完成', '当前未完成/阻塞', '当前结论'], [
  ['P1 亚伦', '边缘 LLM 双路径、TaskRouter、InferenceTracker、MQTT 关联、SQLite 回写、边缘测试。', 'Jetson 实测、独立超时定时器、Schema、真实云端响应联调。', '边缘侧主线完成，进入实机和云边联调阶段。'],
  ['P2 景彬', '护士站 Vue 页面基础和可视化方向。', 'npm build 被 element-plus 解析失败阻塞；看板、WebSocket 异常态和 Docker 构建未验收。', '先恢复构建，再做可演示看板。'],
  ['P3 建鸿', '统筹、方案和 README/CHANGELOG 协调方向；执行版任务书已生成。', '验收矩阵、最终报告、PPT、视频和提交包尚未冻结。', '负责把分散成果收敛成可提交证据。'],
  ['P4 振鑫', '训练协调器基础框架和 8 项测试。', 'FedAvg/异步陈旧度、一致性、蒸馏、版本发布和回滚证据。', '研究框架有基础，交付闭环不足。'],
  ['P5 先伟', '已有 x86 性能数据和测评方向。', '500+ 数据集、统一 benchmark、Jetson数据、三路线对比和断网保持率。', '负责把“能运行”转成量化验收结论。'],
  ['P6 烽亮', 'Compose 配置校验和部署/视频方向。', '完整镜像构建、云端/Jetson 环境、故障演示和最终视频。', '负责把代码变成可复现演示环境。'],
  ['P7 彦晗', '云端协同方向和接口责任已明确。', 'cloud-llm-service/app 为空，云端 consumer、模型适配和真实 MQTT 回传均未完成。', '当前最紧急开发任务，必须先完成最小可用服务。'],
], [1150, 3200, 3700, 1456]));
children.push(rich('整体判断：', '项目已完成边缘侧基础能力和可测试的云边协议框架，当前完成度不能按“全链路完成”描述。真正的剩余主线是 P7 云端服务、P1/P6 Jetson 实测、P2 前端构建与看板、P5 正式测评，以及 P3 最终证据整合；这五项完成后才进入全链路彩排。'));

children.push(h1('三、系统架构与模块边界'));
children.push(h2('3.1 业务链路'));
['端侧采集：摄像头、床垫和环境适配器生成 observation。',
 '边缘融合：规则引擎和边缘 LLM 生成 safety event、置信度和初步护理建议。',
 '路由决策：TaskRouter 根据置信度、复杂度和网络状态决定 edge、cloud 或 hybrid。',
 '云端研判：边缘以 event_id + trace_id 发起 inference/request，云端调用 Qwen2.5-14B/vLLM 或可替换的 mock consumer。',
 '状态回写：云端返回 confirm/reject/escalate，边缘按幂等规则写回 SQLite，护士站通过云端 API/WebSocket 展示状态。',
 '离线恢复：网络中断时事件持续本地处理与缓存，网络恢复后按 QoS 1 和补传逻辑同步。'].forEach(item => children.push(numbered(item, 'flow')));
children.push(h2('3.2 接口边界'));
children.push(table(['接口', '约定', '主责', '协作要求'], [
  ['边缘请求主题', 'ward/{ward_id}/node/{node_id}/inference/request', 'P1', '外层和 payload 均携带 event_id、trace_id；请求可重试。'],
  ['云端响应主题', 'node/{node_id}/inference/response', 'P7', '必须回传 event_id、trace_id、judgment、confidence、advice、latency_ms。'],
  ['judgment 枚举', 'confirm / reject / escalate', 'P1 + P7', '边缘映射到本地事件状态，非法值进入失败回退，不得覆盖有效结果。'],
  ['前端实时事件', '云端 WebSocket 增量推送 + REST 查询', 'P2 + 云端现有模块负责人', '展示路由、模型、延迟、网络和状态变化，断线时显示降级状态。'],
  ['模型版本', 'model_name、model_version、model_status、聚合版本', 'P4', '部署、灰度、回滚和边缘 health 上报使用同一版本命名。'],
], [1850, 2900, 1500, 3256]));
children.push(h2('3.3 代码边界'));
children.push(table(['模块', '主要目录/文件', '本阶段不得遗漏的验证'], [
  ['边缘推理与路由', 'edge-agent/src/llm_engine.py、llm_advisor.py、task_router.py、inference_tracker.py、main.py、mqtt_client.py', '真实模型、超时、重复响应、SQLite 回写和性能统计。'],
  ['云端 LLM', 'cloud-llm-service/app、docker-compose.yml', '消费者、模型适配器、请求去重、响应契约、健康检查。'],
  ['护士站前端', 'cloud-frontend/src、Dockerfile、package.json', '构建、页面状态、WebSocket、路由和性能看板。'],
  ['协同训练', 'training-coordinator/app、tests', 'FedAvg、异步陈旧度、版本一致性、蒸馏和回滚证据。'],
  ['数据与测评', 'tests、scripts、docs/benchmark 或等价目录', '数据集版本、评测脚本、原始日志和对比结论。'],
  ['部署与材料', 'docker-compose*.yml、deploy/、docs/、视频/PPT 源文件', '一键启动、环境说明、录屏和最终提交包。'],
], [2100, 4500, 2906]));

children.push(h1('四、工作包与总体分工'));
children.push(table(['工作包', '目标', '主责', '协作', '截止', '状态'], [
  ['T1 边缘 LLM 双路径实机验收', '完成 1.5B/0.5B 在 Jetson 上的部署、性能和资源证据。', 'P1 亚伦', 'P5、P6', '8/12', '进行中'],
  ['T2 云端 LLM 服务', '实现 request 消费、14B/vLLM 调用、response 回传和幂等。', 'P7 彦晗', 'P1、P6', '8/07', '未完成'],
  ['T3 云边真实链路', '打通 MQTT Broker、云边回写、超时回退和前端状态变化。', 'P1 亚伦', 'P2、P7、P6', '8/15', '未完成'],
  ['T4 护士站与可观测性', '完成构建，展示路由、延迟、内存、网络和处置状态。', 'P2 景彬', 'P1、P7', '8/20', '进行中'],
  ['T5 训练与模型更新', '完成 FedAvg/异步一致性、蒸馏、版本发布、灰度和回滚证据。', 'P4 振鑫', 'P5、P1', '8/22', '进行中'],
  ['T6 数据与对比实验', '形成不少于 500 条数据集和三路线可复现测评报告。', 'P5 先伟', '全员', '8/25', '未完成'],
  ['T7 部署与演示', '完成 Docker、Jetson/云端环境、故障演示和 5～8 分钟视频。', 'P6 烽亮', 'P1、P2、P7', '8/28', '未完成'],
  ['T8 统筹与最终材料', '统一任务书、报告、README、CHANGELOG、验收矩阵和提交包。', 'P3 建鸿', '全员', '8/31', '进行中'],
], [1050, 3000, 1300, 1800, 900, 1456]));

children.push(h1('五、个人任务书'));

function personSection(code, name, role, completed, tasks, deliverables, acceptance, dependencies) {
  children.push(h2(`${code} ${name}：${role}`));
  children.push(rich('当前已完成：', completed));
  children.push(h3('必须完成的具体任务'));
  tasks.forEach(item => children.push(numbered(item, `${code}-tasks`)));
  children.push(h3('必须提交的交付物'));
  deliverables.forEach(item => children.push(bullet(item, `${code}-deliverables`)));
  children.push(h3('个人验收标准'));
  acceptance.forEach(item => children.push(bullet(item, `${code}-acceptance`)));
  children.push(rich('前置依赖与联调对象：', dependencies));
}

personSection('P1', '亚伦', '边缘 AI 与云边协同边缘侧负责人',
  '已完成边缘 LLM 双路径、LLM 参数配置、性能统计、TaskRouter、InferenceTracker、MQTT trace 透传、SQLite 结果写回、超时回退和重复响应幂等等主线实现。',
  [
    '在 Jetson Orin Nano 上完成 Qwen2.5-1.5B Q4 和 Qwen2.5-0.5B Q4 两条路径的部署，记录冷启动、热身后 TTFT、总延迟、峰值 RSS、生成吞吐量，以及与视觉模型同时运行时的资源占用。',
    '把云端超时处理从依赖 TICK_SECONDS 的轮询中独立出来，使用明确的请求超时定时机制；超时后写入失败原因并继续使用边缘决策，不得阻塞后续事件。',
    '补齐 inference request/response JSON Schema 或等价的字段校验，明确外层 envelope 与 payload 的 event_id、trace_id、judgment、confidence、advice、latency_ms。',
    '与 P7 使用真实 MQTT Broker 联调 request、response、重复 request、重复 response、trace 不匹配、未知 event、非法 judgment 和云端不可用等场景。',
    '保证边缘事件状态、云端回传状态、SQLite payload 和前端显示状态一致，形成至少一条可追踪 trace_id 的完整日志。',
    '维护 1.5B 质量优先路径和 0.5B 低内存路径的配置说明；若 1.5B 在 Jetson 上超过内存目标，必须给出明确的 compact 路径切换结论，而不是继续牺牲业务输出质量。',
  ],
  ['edge-agent/src/llm_engine.py、llm_advisor.py、task_router.py、inference_tracker.py、main.py、mqtt_client.py 的实现提交。', 'Jetson 性能原始日志和汇总表，包含硬件、系统、模型哈希、环境变量和测试命令。', 'request/response Schema、联调记录和异常场景测试。', '边缘部署说明、模型路径选择建议和最终答辩可用截图。'],
  ['Jetson 两条路径均能启动；TTFT 目标为热身后小于 200ms。', '低内存路径峰值 RSS 不高于 1.5GB；质量路径即使略超目标，也必须保留可量化的超标数据和切换方案。', '云端无响应时能够在配置超时时间内回退；重复响应不重复改状态；trace 不匹配响应不污染事件。', '现有 edge-agent 38 项测试继续全绿，并新增超时定时器和真实/模拟响应场景测试。'],
  'P7 提供云端消费者和响应契约；P6 提供 Jetson、Broker、模型文件和部署权限；P5 负责统一计时口径和原始数据归档；P2 接收路由与状态字段。');

personSection('P2', '景彬', '护士站 Vue 前端与可观测性负责人',
  '已承担 Vue 护士站页面、协同推理和性能看板方向；当前前端依赖和 Docker 构建仍需确认。',
  [
    '修复 cloud-frontend 本地构建环境，确认 package-lock 与 package.json 一致，解决 tailwindcss 等依赖缺失问题；执行 npm run build 并保留日志。',
    '完成 Docker 镜像构建和容器访问验证，确保护士站页面在 http://localhost:8081 可打开。',
    '在事件详情和病床卡片中展示 edge、cloud、hybrid 路由，模型名称/版本、TTFT、云端延迟、内存、网络状态和当前处置状态。',
    '对接 WebSocket 增量事件和 REST 查询，展示 pending、confirmed、rejected、escalated、timeout/fallback 等状态变化。',
    '补齐断网、云端超时、MQTT 重连和数据补传等异常状态的视觉提示；恢复后能显示恢复时间和补传结果。',
    '制作前端演示截图和录屏素材，截图必须标注测试场景、时间和对应 trace_id，供 P3 写报告和 P6 剪辑视频。',
  ],
  ['前端构建日志和 Docker 构建日志。', '护士站路由/性能/网络/状态看板代码。', 'WebSocket 异常状态演示截图和 3～5 个典型场景素材。', '前端使用说明和演示脚本中的页面操作步骤。'],
  ['npm run build 成功；docker compose build cloud-frontend 成功；容器页面可访问。', '一次事件从边缘产生到云端返回再到前端显示，状态和 trace_id 可追踪。', '断网和云端超时场景有明确降级提示，页面不出现空白、重叠或无法区分的状态。', '前端新增功能至少有基本交互验证；不得依赖只有开发机才存在的本地路径。'],
  'P1 提供字段和路由统计；P7 提供云端响应与延迟；P6 负责容器环境；P3 负责截图命名、材料归档和报告引用。');

personSection('P3', '建鸿', '项目统筹、需求与最终材料负责人',
  '已承担项目统筹、需求、方案书、作品报告和最终材料整合方向；当前需要把所有材料状态统一到 master 和 8 月执行计划。',
  [
    '维护一份验收矩阵，至少包含指标、目标值、实现位置、测试命令、证据文件、负责人、协作人、状态和风险。',
    '冻结 8 月 1 日之后的需求范围；新增功能必须说明对主链路、工期和材料的影响，未经全员确认不得改变验收口径。',
    '统一任务书、README、CHANGELOG、架构方案、作品报告和答辩 PPT 中的模型名称、服务数量、事件数量、测试数量和当前限制。',
    '每周组织一次联调验收，至少在 8/7、8/15、8/22、8/28 形成会议结论、阻塞项、负责人和下一截止时间。',
    '将历史任务书与本执行版区分，避免覆盖已有文件；最终提交包中明确 master 合并提交和各成员有效提交。',
    '负责最终材料审校：技术报告、性能报告、演示视频、答辩 PPT、部署说明、任务书和代码提交清单内容一致。',
  ],
  ['验收矩阵.xlsx 或 Markdown 版本。', '每周联调纪要和问题闭环清单。', '最终版技术报告、任务书、答辩 PPT、提交清单。', '材料版本号和证据索引。'],
  ['所有硬指标都能指向一份原始证据；未达标项不得标为“已完成”。', '8/28 前完成材料初稿，8/30 完成全链路彩排和材料冻结，8/31 只允许修复阻断性问题。', '报告不得使用 Windows/x86 数据描述为 Jetson 实测；云端未接入的内容必须标注限制。', '最终提交包能由另一名成员按清单复核，缺文件、错版本、错链接均视为未通过。'],
  '全员按节点提交证据；P5 提供指标数据；P6 提供部署和视频；P1/P7 提供链路日志；P2 提供截图；P4 提供训练材料。');

personSection('P4', '振鑫', '协同训练、一致性与模型更新负责人',
  '已具备 training-coordinator 的同步/异步训练调度框架和基础测试；模型版本、陈旧度加权、一致性和蒸馏闭环仍需形成可验收证据。',
  [
    '明确节点模型版本、聚合版本、教师模型版本、学生模型版本和发布批次的命名规则，形成版本关系表。',
    '完善 FedAvg 和异步陈旧度加权训练流程，定义客户端迟到、重复上传、版本冲突和聚合失败的处理规则。',
    '实现或补齐聚合结果校验、模型元数据登记、灰度发布、失败回滚和边缘 health 确认；不能只保留接口空壳。',
    '配合 P5 准备病房 NLU 数据，完成 14B 教师到 1.5B 学生的任务特定蒸馏方案；如实际训练资源不足，至少交付可复现实验脚本、配置和小规模结果。',
    '对比原始 1.5B、蒸馏后 1.5B 和 0.5B 在同一评测集上的指标，说明蒸馏收益或失败原因。',
    '把训练日志、模型哈希、聚合版本和部署版本提交到材料目录，供 P1 做边缘加载和 P3 写报告。',
  ],
  ['训练协调器代码、配置和新增测试。', '模型版本/聚合版本/发布批次说明。', 'FedAvg、异步陈旧度和蒸馏实验日志。', '灰度发布、回滚和边缘 health 确认记录。'],
  ['现有 training-coordinator 8 项测试继续通过；新增版本冲突、迟到节点和回滚测试。', '至少完成一组可复现的聚合或蒸馏实验，日志中包含数据版本、参数、模型哈希和结果。', '模型发布后边缘能识别 model_version；失败发布能回滚到已知可运行版本。', '蒸馏结果按同一数据集和同一指标报告，不用主观描述代替准确率、召回率或 F1。'],
  'P5 提供数据集和测评；P1 提供边缘加载、health 和回滚接口；P7/P6 提供云端训练环境；P3 负责将结果纳入验收矩阵。');

personSection('P5', '先伟', '数据集、性能测试与精度评测负责人',
  '已承担数据、性能测试、精度评测和对比实验方向；正式病房 NLU 数据集、统一 benchmark 和 Jetson 实测记录尚未完成。',
  [
    '构建不少于 500 条病房 NLU 评测数据，覆盖事件描述、风险等级、优先级、护理建议和云端处置判断；保留原始样本、标签规范和版本号。',
    '制定训练/验证/测试划分，避免同一事件模板泄漏到不同集合；记录标注者、复核方式、争议处理和脱敏规则。',
    '统一测试 1.5B、0.5B、云端 14B 三种路径，至少输出准确率、召回率、F1、置信度校准、TTFT、总延迟、峰值 RSS 和吞吐量。',
    '完成纯边缘、云边协同、纯云端三种方案对比，并明确测量口径、网络条件、并发量、热身轮数和统计分位数。',
    '在断网、延迟、丢包和云端不可用条件下测试业务保持率，目标不低于 90%；区分边缘仍能生成事件、护士站可见和云端补传成功三个指标。',
    '将 P1 的 Jetson 原始数据和 P2 的前端链路数据汇总为最终测评报告，所有结论保留原始日志路径和提交版本。',
  ],
  ['数据集、标签说明和版本记录。', '可重复执行的 benchmark 脚本或命令。', '三种路线对比表、断网保持率报告和图表。', '最终性能与精度测评报告，含测试环境和限制说明。'],
  ['数据集不少于 500 条且标签字段完整；测试集独立。', '所有指标均有明确分母、样本量、统计方法和原始日志；不得只给单次最好结果。', '断网业务保持率目标不低于 90%；若未达标，必须给出失败分类和整改方案。', '确认 1.5B/0.5B 采用哪条作为现场主路径，并记录质量与资源的权衡。'],
  'P1 提供推理统计和 Jetson 设备数据；P4 提供蒸馏/训练结果；P7 提供云端延迟和错误日志；P3 负责证据编号。');

personSection('P6', '烽亮', '部署、环境与演示视频负责人',
  '已承担部署、云端环境和演示视频方向；当前需要完成全量 Compose 构建、云端模型环境、Jetson 准备和可复现演示。',
  [
    '完成 docker compose config、主 Compose 构建、compact Compose 构建和 cloud-frontend 镜像构建；记录镜像版本、失败原因和修复结果。',
    '准备云端 Qwen2.5-14B/vLLM 或团队确认的等价服务环境，提供 P7 可调用的地址、模型配置、健康检查和资源说明。',
    '准备 Jetson Orin Nano 的系统、CUDA/运行时、模型挂载、MQTT 地址、日志目录和监控命令，协助 P1 完成实机测量。',
    '设计 5～8 分钟演示脚本：正常事件、边缘快速响应、云端复杂研判、护士站处置、断网保持、网络恢复补传、模型路径切换。',
    '录制真实硬件/容器/护士站联动视频，保留原始录屏和最终剪辑版；视频中不得展示未实现功能或无法复现的指标。',
    '输出部署手册，明确 Windows/x86 验证、Jetson 部署、云端部署、模型下载、环境变量、端口和故障恢复步骤。',
  ],
  ['Docker 构建和启动日志。', 'Jetson/云端环境清单和部署手册。', '演示脚本、原始录屏、最终视频和截图素材。', '故障恢复场景操作记录。'],
  ['主 Compose 和 compact Compose 能按文档启动；前端可访问，边缘节点能产生事件。', '视频中的每个场景都能由当前 master 或明确标注的有效提交复现。', '云端服务健康检查、MQTT Broker、前端、边缘节点的地址和端口在手册中明确。', '演示至少包含一次断网和恢复，不得只播放静态页面。'],
  'P1 提供边缘启动参数；P7 提供云端服务；P2 提供页面操作；P3 提供最终脚本和材料命名规范。');

personSection('P7', '彦晗', '云端 LLM 与云边协同云端侧负责人',
  '云端 LLM 服务目录目前基本为空，因此本阶段以“从空目录到真实 MQTT request/response 服务”为第一优先级。',
  [
    '在 cloud-llm-service/app 中创建可运行的云端服务入口、配置读取、健康检查、日志和依赖说明；服务必须能被 Compose 或独立命令启动。',
    '订阅 ward/{ward_id}/node/{node_id}/inference/request，解析 envelope 和 payload，校验 event_id、trace_id、事件内容和模型参数。',
    '调用云端 Qwen2.5-14B/vLLM；若真实模型环境尚未就绪，先提供接口一致的 mock adapter，但必须将真实模型接入列为明确的上线前置项。',
    '向 node/{node_id}/inference/response 回传 judgment、confidence、advice、latency_ms、event_id、trace_id、model_name 和 model_version。',
    '实现 request 去重、response 幂等和错误处理；重复 request 不重复执行，重复 response 不导致边缘状态二次变更。',
    '与 P1 完成真实 Broker 联调，覆盖正常、超时、重复、非法 judgment、未知 event、trace 不匹配和云端模型不可用场景。',
    '修复云端重复 event_id 时只跳过而不更新状态的逻辑问题，明确 event_id 已存在但 trace 或 judgment 更新时的处理规则并写测试。',
  ],
  ['cloud-llm-service/app 源码、Dockerfile/requirements 或等价运行说明。', 'request/response Schema 和字段映射表。', '云端健康检查、调用日志、去重/幂等测试和真实 Broker 联调记录。', 'Qwen2.5-14B/vLLM 接入说明或 mock 到真实服务的切换说明。'],
  ['服务可启动并订阅正确主题；正常请求能在配置时限内回传有效 response。', 'response 必须包含 event_id、trace_id、judgment、confidence、advice、latency_ms；缺字段不得进入成功路径。', '重复 request/response、未知事件和 trace 不匹配不会污染边缘状态。', 'P1 的 edge-agent 测试、P7 的云端测试和一条真实 Broker 端到端日志均可复核。'],
  'P6 提供模型和运行环境；P1 提供边缘契约和状态写回；P2 接收云端延迟/状态字段；P3 负责接口文档和证据归档。');

children.push(h1('六、里程碑、依赖与会议节奏'));
children.push(table(['时间', '里程碑', '必须完成', '出口条件'], [
  ['8/1～8/3', '任务冻结与接口确认', 'P3 发布验收矩阵；P1/P7 冻结 request/response；P2 确认看板字段。', '所有成员知道自己的提交物和依赖；接口字段不再口头变更。'],
  ['8/4～8/7', '云端服务最小闭环', 'P7 完成 mock consumer、健康检查和响应协议；P6 完成运行环境。', '一条 request 经 Broker 到 response；P1 能收到并处理。'],
  ['8/8～8/11', '云边真实联调', '正常、超时、重复、非法响应和断网场景联调。', '状态写回、日志关联和前端状态变化可见。'],
  ['8/12～8/16', 'Jetson 与双路径验收', 'P1/P6 完成 Jetson 部署；P5 按统一口径采集数据。', '两条路径均有性能证据；确定主路径和兜底路径。'],
  ['8/17～8/20', '前端与演示闭环', 'P2 完成看板和异常状态；P6 完成第一版演示。', '正常/云端/断网/恢复四类场景可演示。'],
  ['8/21～8/25', '精度、稳定性与训练实验', 'P4/P5 完成训练或蒸馏证据、三路线对比、保持率测试。', '所有指标有数据；未达标项有降级方案和文字说明。'],
  ['8/26～8/28', '报告、视频、答辩材料', 'P3 汇总报告；P6 固化视频；全员完成代码和截图交付。', '材料初审通过，版本、数字和截图一致。'],
  ['8/29～8/30', '全链路彩排与冻结', '按最终清单从干净环境启动并演示；修复阻断项。', '彩排通过；不再引入非必要功能。'],
  ['8/31', '最终提交', '提交代码、文档、报告、视频、PPT、部署说明和证据包。', 'P3 按提交清单逐项勾选并留存最终版本。'],
], [1400, 2200, 3900, 2006]));
children.push(h2('6.1 固定协作节奏'));
['每天由各负责人在群内同步：昨日完成、今日目标、阻塞项、需要谁在何时提供什么。',
 '每周至少一次全员联调，优先复现 P0 问题；联调结论必须写入纪要，不用口头承诺替代。',
 'P0 问题 24 小时内响应，P1 问题 48 小时内给出修复或降级方案；无法按期完成时由 P3 更新验收矩阵和风险等级。',
 '成员之间交付接口时必须同时给出：代码提交、运行命令、输入样例、预期输出、日志位置和已知限制。'].forEach(item => children.push(bullet(item, 'meeting')));

children.push(h1('七、验收指标与证据要求'));
children.push(table(['指标类别', '目标/通过线', '测量方法', '证据要求', '责任'], [
  ['边缘 TTFT', '热身后小于 200ms', '同一模型、同一 prompt、至少 30 次；报告 p50、p95、最大值。', 'Jetson 原始日志；x86 仅作为基线。', 'P1/P5'],
  ['低内存 RSS', '峰值不高于 1.5GB', '启动、热身、连续事件和视觉模型并行运行时记录峰值。', 'psutil/系统监控日志，注明是否包含视觉模型。', 'P1/P5'],
  ['质量路径', '保留 1.5B；若超过内存线，必须提供 compact 切换。', '统一评测集比较 1.5B 与 0.5B 的任务指标。', '模型版本、数据集版本、准确率/召回率/F1。', 'P1/P5'],
  ['云边闭环', '正常请求成功率不低于 95%；异常场景不污染状态。', '正常、超时、重复、非法、未知、断网各不少于 20 次。', 'trace_id 日志、状态前后快照、失败分类。', 'P1/P7'],
  ['断网保持率', '业务保持率不低于 90%', '模拟断网、延迟、丢包；分别统计边缘事件、本地展示、恢复补传。', '网络条件、样本数、成功数、恢复时间。', 'P5/P1'],
  ['前端构建', '本地 npm run build 和 Docker build 均成功。', '干净依赖环境执行；禁止依赖未提交 node_modules。', '命令日志、镜像标签、页面截图。', 'P2/P6'],
  ['训练/蒸馏', '至少一组可复现实验；版本和回滚可验证。', '固定数据和配置，记录聚合、蒸馏、发布和回滚。', '日志、模型哈希、版本表、指标对比。', 'P4/P5'],
  ['材料一致性', '代码、数字、截图、报告和视频一致。', 'P3 依据验收矩阵逐项抽查。', '证据索引、提交号、材料版本号。', 'P3/全员'],
], [1450, 2050, 2800, 2200, 1006]));
children.push(h2('7.1 性能测试最低记录格式'));
children.push(p('每次性能结果至少记录：测试日期、设备型号、操作系统、CUDA/运行时版本、模型名称和哈希、量化方式、上下文长度、batch、线程、最大生成 token、热身轮数、样本数、p50/p95/最大值、峰值 RSS、吞吐量、是否同时运行视觉模型、网络条件和代码提交号。缺少任一关键环境信息的结果只能作为参考，不得作为最终达标证据。'));

children.push(h1('八、Git、分支与交付规范'));
children.push(h2('8.1 分支策略'));
['master 只接收经过验证的功能分支或修复分支；当前功能分支 HEAD 为 74e3a44，远端 origin/master 为 ebac0a3，本地 master 为 f3f7bba；最终提交前必须完成本地同步。',
 '个人分支建议使用 codex/ 或 feature/ 前缀，并按工作包命名，例如 feature/cloud-llm-consumer、feature/jetson-benchmark、feature/nurse-dashboard。',
 '每个 PR 只解决一个工作包或一组紧密相关问题；PR 描述必须包含目标、变更文件、测试命令、测试结果、已知限制和证据位置。',
 '合并前必须 rebase 或同步最新 master，解决冲突后重新运行受影响模块测试；P3 维护合并记录。'].forEach(item => children.push(bullet(item, 'git')));
children.push(h2('8.2 提交规范'));
children.push(table(['场景', '建议格式', '示例'], [
  ['功能', 'feat(scope): 描述', 'feat(cloud-llm): add mqtt inference consumer'],
  ['修复', 'fix(scope): 描述', 'fix(edge): decouple inference timeout timer'],
  ['测试', 'test(scope): 描述', 'test(benchmark): add compact profile metrics'],
  ['文档', 'docs(scope): 描述', 'docs(report): update acceptance matrix'],
  ['禁止提交', '模型大文件、密钥、个人虚拟环境、未经确认的临时日志', '模型文件放在本地挂载目录；密钥使用 .env，不进入 Git。'],
], [1900, 3300, 4306]));
children.push(h2('8.3 交付命名'));
children.push(p('证据文件统一使用“日期_模块_场景_提交号”命名，例如 20260812_edge-llm_jetson-1.5b_ebac0a3.txt；截图、视频和报告中的数字必须能通过该命名回查。生成的 Word 任务书属于本地材料产物，不覆盖任务书.docx、项目任务书.docx 和项目任务书-云边协同AI.docx。'));

children.push(h1('九、风险、降级与决策门槛'));
children.push(table(['风险', '触发条件', '立即措施', '决策人'], [
  ['Jetson 无法及时使用', '8/8 仍无设备或驱动不可用。', '先用 x86 完成协议和脚本；P6 继续准备设备；报告明确“非 Jetson 证据”，不得宣称实机达标。', 'P3/P6'],
  ['1.5B RSS 超标', 'Jetson 峰值超过 1.5GB。', '启用 0.5B compact 路径；保留 1.5B 质量结果，说明质量/资源权衡。', 'P1/P5'],
  ['云端 14B 资源不足', 'vLLM 无法稳定启动或延迟不可接受。', '先用接口一致 mock consumer 打通闭环，再切换真实模型；视频和报告区分两种环境。', 'P7/P6/P3'],
  ['前端依赖继续失败', '8/3 仍不能 build。', '锁定 package-lock、清理非必要依赖、优先保证 Docker build 和核心页面；P2 提供失败原因。', 'P2/P6'],
  ['训练/蒸馏时间不足', '8/21 尚无稳定实验。', '保留 FedAvg/异步框架和可复现实验；将蒸馏结果标为研究性增强，优先保障云边主链路。', 'P4/P3'],
  ['指标未达标', 'TTFT、RSS、保持率或 F1 未达到目标。', '不得修改统计口径掩盖问题；给出失败数据、原因、fallback 路径和最终可交付能力。', '对应负责人/P3'],
], [1800, 2400, 4300, 1006]));

children.push(h1('十、最终提交清单'));
['代码：最新 master、各功能合并记录、无密钥和无个人虚拟环境，主线测试可重复通过。',
 '边缘：1.5B/0.5B 配置、模型下载说明、Jetson 性能日志、超时/幂等测试、部署说明。',
 '云端：cloud-llm-service 源码、模型适配说明、MQTT request/response 契约、健康检查和联调日志。',
 '前端：构建日志、Docker 镜像验证、护士站截图、WebSocket 和异常状态演示。',
 '训练：FedAvg/异步一致性或蒸馏实验、模型版本表、聚合日志、发布/回滚证据。',
 '测评：数据集与标签规范、benchmark 命令、三路线对比、断网保持率、性能和精度报告。',
 '部署：主 Compose 和 compact Compose 配置检查、云端/Jetson 环境清单、端口和故障恢复步骤。',
 '材料：执行版任务书、技术方案、作品报告、答辩 PPT、5～8 分钟视频、创新点说明、验收矩阵和证据索引。',
 '最终复核：P3 逐项检查文件存在、版本一致、数字一致、链接有效、截图可辨、视频可播放，并在 8/31 前完成提交。'].forEach(item => children.push(numbered(item, 'final')));
children.push(spacer(), p('本任务书的核心判断：当前项目已经完成边缘侧能力和主线基础，真正决定最终质量的是云端服务落地、Jetson 实测、前端可演示、统一测评和证据闭环。所有成员按本书执行时，应优先保证这五项结果。', { bold: true, color: COLORS.navy, spacing: { before: 180, after: 0, line: 320 } }));

const doc = new Document({
  creator: 'Codex',
  title: '智慧病房云边端协同系统项目任务书（2026执行版）',
  subject: '团队执行分工、里程碑与验收标准',
  description: '基于 master 当前进度编制的项目执行任务书。',
  styles: {
    default: { document: { run: { font: 'Microsoft YaHei', size: 21 }, paragraph: { spacing: { after: 120, line: 320 } } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Microsoft YaHei', size: 29, bold: true, color: COLORS.navy }, paragraph: { spacing: { before: 300, after: 180 }, outlineLevel: 0, keepNext: true } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Microsoft YaHei', size: 24, bold: true, color: COLORS.navy }, paragraph: { spacing: { before: 220, after: 120 }, outlineLevel: 1, keepNext: true } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Microsoft YaHei', size: 21, bold: true, color: COLORS.navy }, paragraph: { spacing: { before: 160, after: 90 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: {
    config: [
      { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
      { reference: 'numbers', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
      { reference: 'flow', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
      { reference: 'meeting', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
      { reference: 'git', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
      { reference: 'final', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
      ...['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7'].flatMap(code => [
        { reference: `${code}-tasks`, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
        { reference: `${code}-deliverables`, levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
        { reference: `${code}-acceptance`, levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
      ]),
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1200, right: 1200, bottom: 1200, left: 1200 },
      },
    },
    headers: {
      default: new Header({ children: [p('智慧病房云边端协同系统｜2026 执行版任务书', { alignment: AlignmentType.RIGHT, size: 16, color: COLORS.gray, spacing: { after: 0 } })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [run('第 ', { size: 16, color: COLORS.gray }), new TextRun({ children: [PageNumber.CURRENT], font: 'Microsoft YaHei', size: 16, color: COLORS.gray }), run(' 页', { size: 16, color: COLORS.gray })] })] }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(output, buffer);
  console.log(`OK: ${output} (${(buffer.length / 1024).toFixed(1)} KB)`);
});
