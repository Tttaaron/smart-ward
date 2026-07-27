const fs = require('fs');
const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  Table,
  TableRow,
  TableCell,
  AlignmentType,
  HeadingLevel,
  BorderStyle,
  WidthType,
  ShadingType,
  PageBreak,
  Header,
  Footer,
  PageNumber,
  TableOfContents,
  LevelFormat,
  ExternalHyperlink
} = require('docx');

const OUTPUT = '智慧病房调研报告.docx';

// ---------- style helpers ----------
const border = { style: BorderStyle.SINGLE, size: 1, color: 'BFBFBF' };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 100, bottom: 100, left: 140, right: 140 };

const FONT = 'Microsoft YaHei';

function para(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 100, after: 100, line: 360 },
    alignment: opts.align || AlignmentType.JUSTIFIED,
    ...opts,
    children: [new TextRun({ text, font: FONT, ...opts.run })]
  });
}

function richPara(runs, opts = {}) {
  return new Paragraph({
    spacing: { before: 100, after: 100, line: 360 },
    alignment: opts.align || AlignmentType.JUSTIFIED,
    ...opts,
    children: runs.map(r => new TextRun({ font: FONT, ...r }))
  });
}

function heading(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({
    heading: level,
    spacing: { before: 280, after: 140 },
    children: [new TextRun({ text, bold: true, font: FONT })]
  });
}

function bullet(text, level = 0, ref = null) {
  const runs = [{ text }];
  if (ref) {
    runs.push({ text: '  [' + ref + ']', color: '888888', size: 18 });
  }
  return new Paragraph({
    numbering: { reference: 'bullets', level },
    spacing: { before: 50, after: 50, line: 320 },
    children: runs.map(r => new TextRun({ font: FONT, ...r }))
  });
}

function numberItem(text, level = 0) {
  return new Paragraph({
    numbering: { reference: 'numbers', level },
    spacing: { before: 50, after: 50, line: 320 },
    children: [new TextRun({ text, font: FONT })]
  });
}

function hyperlinkPara(text, url, opts = {}) {
  return new Paragraph({
    spacing: { before: 30, after: 30, line: 300 },
    ...opts,
    children: [
      new ExternalHyperlink({
        children: [new TextRun({ text, font: FONT, style: 'Hyperlink', size: 20 })],
        link: url
      })
    ]
  });
}

function tableCell(text, width, opts = {}) {
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    margins: cellMargins,
    shading: opts.shading ? { fill: opts.shading, type: ShadingType.CLEAR } : undefined,
    verticalAlign: 'center',
    children: [
      new Paragraph({
        alignment: opts.align || AlignmentType.LEFT,
        spacing: { before: 30, after: 30 },
        children: [
          new TextRun({
            text: String(text),
            bold: opts.bold || false,
            size: opts.size || 20,
            color: opts.color || '333333',
            font: FONT
          })
        ]
      })
    ]
  });
}

function makeTable(headers, rows, columnWidths) {
  const width = columnWidths.reduce((a, b) => a + b, 0);
  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) =>
      tableCell(h, columnWidths[i], { shading: '1F4E79', bold: true, align: AlignmentType.CENTER, color: 'FFFFFF' })
    )
  });
  const dataRows = rows.map((row, idx) =>
    new TableRow({
      children: row.map((cell, i) =>
        tableCell(cell, columnWidths[i], { shading: idx % 2 === 1 ? 'F2F6FA' : undefined })
      )
    })
  );
  return new Table({
    width: { size: width, type: WidthType.DXA },
    columnWidths,
    rows: [headerRow, ...dataRows]
  });
}

function spacer(h = 120) {
  return new Paragraph({ spacing: { before: h, after: 0 }, children: [new TextRun({ text: '' })] });
}

// ---------- content ----------
function coverPage() {
  return [
    new Paragraph({ spacing: { before: 1600 } }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: '调研报告', size: 80, bold: true, color: '1F4E79', font: FONT })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 200, after: 200 },
      children: [new TextRun({ text: '智慧病房云边协同系统', size: 60, bold: true, color: '2E75B6', font: FONT })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 300 },
      border: { top: { style: BorderStyle.SINGLE, size: 8, color: '2E75B6', space: 8 } },
      children: [new TextRun({ text: '项目背景 · 行业现状 · 核心需求 · 团队技术对应 · 数据指标 · 调研任务清单', size: 22, color: '666666', font: FONT })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 100 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: '2E75B6', space: 8 } },
      children: [new TextRun({ text: '参考来源：WHO / AACN / Red Hat / Deloitte / KubeEdge / Ultralytics / RKNN / HiveMQ / FastAPI / MySQL / SQLite', size: 18, color: '999999', font: FONT })]
    }),
    new Paragraph({ spacing: { before: 1400 } }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: '调研时间：2026 年 7 月', size: 24, color: '666666', font: FONT })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 60 },
      children: [new TextRun({ text: '所有数据与结论均标注真实网络来源', size: 18, color: '999999', font: FONT })]
    }),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

function tocPage() {
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 200, after: 240 },
      children: [new TextRun({ text: '目  录', size: 36, bold: true, font: FONT, color: '1F4E79' })]
    }),
    new TableOfContents('Table of Contents', { hyperlink: true, headingStyleRange: '1-3' }),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

// ---------- Chapter 1: 项目背景 ----------
function chapter1() {
  return [
    heading('一、项目背景', HeadingLevel.HEADING_1),
    heading('1.1 项目定位', HeadingLevel.HEADING_2),
    para('smart-ward 是面向病房患者安全的云边端协同智能监护系统。系统复用智能教室项目已验证的技术路线（云边端三层架构、Docker Compose 编排、MQTT 通信、FastAPI + Vue3 + MySQL 技术栈、断网自治能力），但领域对象、事件契约、融合规则、边缘推理与协同训练均针对病房安全监护重新设计。'),
    para('项目目标：通过边缘多源融合 + 云端集中监控 + 联邦学习协同训练，在病房断网情况下仍能本地识别风险并告警，同时保证患者隐私不出本地。'),
    heading('1.2 病房护理的现实痛点', HeadingLevel.HEADING_2),
    para('现代医院病房护理长期面临“三不过来”的核心矛盾——护士人手长期不足与患者护理风险点高发之间的矛盾：'),
    bullet('看不过来：一名护士通常需同时看护 8-12 张床位，夜间值班人力更少；摄像头、床垫、输液、环境多源信息分散在不同屏幕，护士难以同时关注所有床位的安全状态。'),
    bullet('跑不过来：跌倒、坠床、抽搐、夜间徘徊等高风险事件往往发生在一瞬间，等护士听到动静赶到时往往已造成伤害；夜间跨病区巡查存在 3-5 分钟的盲区。'),
    bullet('记不过来：交接班、巡视记录、输液进度、压疮翻身提醒等大量依赖纸质记录与人工记忆，信息滞后且易遗漏；高危患者的体位变化、长时间静止等早期信号几乎无人记录。'),
    heading('1.3 现有监护手段的局限', HeadingLevel.HEADING_2),
    makeTable(
      ['传统方案', '典型做法', '不足'],
      [
        ['呼叫按钮', '患者主动触发', '失能/昏迷/跌倒患者无法使用'],
        ['中央监护屏', '集中显示视频', '只能看视频，无法自动识别风险'],
        ['单一传感器', '仅床垫或仅摄像头', '误报率高（床垫误判翻身、摄像头遮挡）'],
        ['纯云端方案', '视频全传云端识别', '断网即瘫痪、时延高、隐私风险大'],
        ['纸质交接班', '人工记录与记忆', '信息滞后、易遗漏、难追溯']
      ],
      [1800, 2700, 4860]
    ),
    heading('1.4 项目目标与范围', HeadingLevel.HEADING_2),
    para('当前交付范围：1 个病房（W-01）、3 张床位（B01/B02/B03）；14 类安全事件；10 项智能功能；8 服务 Docker Compose 一键演示。后续演进至真实硬件（Orange Pi 5 + RK3588 NPU）与 KubeEdge 多病区部署。'),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

// ---------- Chapter 2: 行业现状 ----------
function chapter2() {
  return [
    heading('二、行业现状', HeadingLevel.HEADING_1),
    heading('2.1 患者安全形势严峻（WHO）', HeadingLevel.HEADING_2),
    richPara([
      { text: '世界卫生组织（WHO）指出：' },
      { text: '"Around 1 in every 10 patients is harmed in health care and more than 3 million deaths occur annually due to unsafe care."', italics: true },
      { text: ' 其中超过 50% 的伤害是可预防的，' },
      { text: '"half of this harm is attributed to medications"', italics: true },
      { text: '。' }
    ], { ref: 'WHO-PS' }),
    para('与病房安全直接相关的 WHO 关键数据：', { run: { bold: true } }),
    makeTable(
      ['安全事件', 'WHO 数据', '与本项目关联'],
      [
        ['跌倒', '发生率 3-5 例/1000 床日，超过 1/3 造成伤害', 'fall_suspected / fall_prediction 事件'],
        ['用药错误', '影响 1/30 患者，超 1/4 严重或危及生命', 'infusion_anomaly 输液异常事件'],
        ['压力性溃疡', '影响超过 1/10 的成年住院患者', 'bedsore_risk 压疮预防事件'],
        ['静脉血栓', '占住院并发症的 1/3', 'long_still 长时间静止提醒翻身'],
        ['诊断错误', '发生在 5-20% 的医患就诊中', 'abnormal_posture 异常体态早期信号'],
        ['院内感染', '全球发生率 0.14%/年', 'environment_anomaly 环境监测联动']
      ],
      [1800, 3780, 3780]
    ),
    para('WHO 行动计划：Global Patient Safety Action Plan 2021-2030，目标为最大限度减少不安全医疗造成的可避免伤害；每年 9 月 17 日为世界患者安全日。', { ref: 'WHO-PS' }),
    heading('2.2 护理人力短缺（WHO / AACN）', HeadingLevel.HEADING_2),
    richPara([
      { text: 'WHO 数据：全球约 2900 万护士、220 万助产士，预测' },
      { text: '"a shortage of 4.5 million nurses and 0.31 million midwives by the year 2030"', italics: true },
      { text: '，2030 年护士与助产士总缺口约 480 万。' }
    ], { ref: 'WHO-NM' }),
    richPara([
      { text: '美国 AACN 报告：HRSA 2025 年 12 月预测' },
      { text: '"a shortage of 267,330 full-time RNs by 2028"', italics: true },
      { text: '；BLS 预测 2024-2034 年 RN 劳动力增长 5%（3.39M→3.56M），每年 189,100 个 RN 空缺；急性护理 RN 空缺率 8.6%、离职率 17.6%；2025 年护理学校拒收 92,672 份合格申请。' }
    ], { ref: 'AACN' }),
    para('护士配置与患者结局的关联研究（多项权威研究）：', { run: { bold: true } }),
    makeTable(
      ['研究', '关键结论', '来源'],
      [
        ['Lasater 等 (Medical Care, 2024)', 'RN 比例降低 10 个百分点 → 住院死亡几率高 7%；每年可致 10,947 例可避免死亡', 'AACN 引用'],
        ['Aiken 等 (JAMA, 2003)', 'BSN 护士比例提高 10% → 患者死亡与抢救失败风险降 5%', 'AACN 引用'],
        ['Needleman 等 (NEJM, 2011)', '人力不足病区患者死亡风险比满员病区高约 6%', 'AACN 引用'],
        ['Cimiotti 等 (AJIC, 2012)', '护士患者负荷每增加一名患者 → 感染率升高', 'AACN 引用']
      ],
      [2520, 5220, 1620]
    ),
    para('结论：护理人力短缺是全球性问题，直接导致更高的患者死亡率、感染率与住院成本。智慧病房通过多源感知与边缘智能，可在不增加人力的前提下提升监护覆盖面，是缓解该矛盾的现实路径。'),
    heading('2.3 边缘计算已成为主流架构（Red Hat / Deloitte）', HeadingLevel.HEADING_2),
    richPara([
      { text: 'Red Hat 定义：' },
      { text: '"Edge computing is computing that takes place at or near the physical location of either the user or the source of the data."', italics: true },
      { text: ' 边缘计算将算力下沉到数据源旁，可显著降低时延、减少带宽消耗，并在核心站点故障时' },
      { text: '"regional sites can continue to operate independently from a core site"', italics: true },
      { text: '（区域站点可独立运行）。Red Hat 还明确将“clinical decision making”（临床决策）列为边缘 AI/ML 能改善的业务交互之一。' }
    ], { ref: 'REDHAT' }),
    richPara([
      { text: 'Deloitte《2026 技术趋势》指出企业正从单一云优先策略转向战略混合模式：' },
      { text: '"cloud for elasticity, on-premises for consistency, and edge for immediacy."', italics: true },
      { text: ' 边缘计算用于满足对实时响应的需求。同时 Gartner 预测' },
      { text: '"40% of agentic projects will fail by 2027"', italics: true },
      { text: '，失败主因是“automating broken processes instead of redesigning operations”（自动化旧流程而非重设计）。' }
    ], { ref: 'DELOITTE' }),
    heading('2.4 智慧病房国内外厂商格局', HeadingLevel.HEADING_2),
    makeTable(
      ['分类', '厂商', '代表产品/方案', '特点'],
      [
        ['国际', 'Philips', 'HealthSuite / Patient Monitoring', '医疗 IoT 平台'],
        ['国际', 'GE HealthCare', 'Portrait Mobile / FlexAcuity', '统一监测平台，可穿戴'],
        ['国际', 'Medtronic', 'Continuous Patient Monitoring', '连续监测、远程患者管理'],
        ['国际', 'Microsoft / AWS / Google', 'Azure IoT / AWS IoT Greengrass', '云边协同平台'],
        ['国内', '华为', 'IEF 智能边缘（KubeEdge 商业版）', '云边协同，K8s 原生'],
        ['国内', '海康威视', 'AI 摄像头、智慧病房视频方案', '视觉跌倒检测'],
        ['国内', '大华', 'AIoT 智慧病房解决方案', '视频-centric，火灾/安全监控'],
        ['国内', '阿里', 'OpenYurt 边缘计算', 'K8s 无侵入扩展']
      ],
      [900, 1800, 2700, 3960]
    ),
    heading('2.5 同类方案对比', HeadingLevel.HEADING_2),
    makeTable(
      ['方案类型', '典型做法', '不足', 'smart-ward 改进'],
      [
        ['纯云端', '视频全传云端识别', '断网瘫痪、时延高、隐私风险', '边缘自治 + 仅传事件摘要'],
        ['纯本地', '呼叫按钮 + 床垫报警', '无集中监控、无趋势分析', '云端护士站 + 交接班摘要'],
        ['单传感器', '仅床垫或仅摄像头', '误报率高', '四源融合 + 规则引擎'],
        ['商业封闭', '整体采购黑盒系统', '不可定制、成本高', '开源自研 + 可演进'],
        ['云边协同（本项目）', '边缘多源融合 + 云端集中 + 协同训练', '-', '兼顾自治、集中、隐私、演进']
      ],
      [1620, 2340, 2340, 3060]
    ),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

// ---------- Chapter 3: 核心需求 ----------
function chapter3() {
  return [
    heading('三、核心需求', HeadingLevel.HEADING_1),
    heading('3.1 功能需求：14 类安全事件', HeadingLevel.HEADING_2),
    para('系统需识别并闭环处置 14 类病房安全事件，按优先级分为三级：'),
    makeTable(
      ['优先级', '事件类型', '中文名', '默认来源'],
      [
        ['P1 紧急', 'fall_suspected', '疑似跌倒', '边缘端'],
        ['P1 紧急', 'fall_prediction', '坠床预警', '边缘端'],
        ['P1 紧急', 'seizure', '抽搐检测', '边缘端'],
        ['P1 紧急', 'nurse_call', '护士呼叫', '前端/按钮'],
        ['P2 高', 'bed_leave', '离床', '边缘端'],
        ['P2 高', 'infusion_anomaly', '输液异常', '边缘端'],
        ['P2 高', 'door_departure', '门区异常离开', '边缘端'],
        ['P2 高', 'night_wandering', '夜间徘徊', '边缘端'],
        ['P2 高', 'long_still', '长时间静止', '边缘端'],
        ['P2 高', 'abnormal_posture', '异常体态', '边缘端'],
        ['P3 提醒', 'environment_anomaly', '环境异常', '边缘端'],
        ['P3 提醒', 'bedsore_risk', '压疮预防', '边缘端'],
        ['P3 提醒', 'device_fault', '设备故障', '边缘端'],
        ['P3 提醒', 'node_offline', '节点失联', '云端']
      ],
      [1440, 2160, 2160, 3600]
    ),
    heading('3.2 10 项智能功能', HeadingLevel.HEADING_2),
    makeTable(
      ['编号', '智能功能', '对应事件', '临床价值'],
      [
        ['1', '坠床预警', 'fall_prediction', '事前预警，比跌倒更早触发'],
        ['2', '跌倒检测', 'fall_suspected', '秒级发现，缩短救治黄金时间'],
        ['3', '长时间静止', 'long_still', '提示昏迷/不适'],
        ['4', '异常体态', 'abnormal_posture', '急症早期信号（蜷缩/前倾/抓胸）'],
        ['5', '抽搐检测', 'seizure', '癫痫夜间发作自动发现'],
        ['6', '压疮预防', 'bedsore_risk', '2 小时未翻身提醒'],
        ['7', '交接班摘要', 'shift_summaries', '自动汇总班次事件，减少遗漏'],
        ['8', '环境自适应', 'environment_anomaly', '温/湿度/CO₂/光照监测'],
        ['9', '空气质量联动', 'env/control', '联动空调/灯光/新风'],
        ['10', '床位可视化', 'beds/occupancy', '全病区床位占用一览']
      ],
      [720, 2160, 2160, 4320]
    ),
    heading('3.3 非功能需求', HeadingLevel.HEADING_2),
    makeTable(
      ['维度', '指标', '依据'],
      [
        ['性能', '边缘推理 15-30 FPS；P1 事件告警时延 ≤ 2 秒', 'RK3588 NPU + YOLOv8n-pose INT8'],
        ['可靠性', '断网自治；事件不丢不重', 'SQLite 缓存 + event_id 去重'],
        ['可用性', '护士站 7×24 小时在线', '云端 FastAPI + WebSocket'],
        ['隐私性', '原始视频留边缘，仅上传脱敏事件摘要', '病房隐私合规要求'],
        ['可扩展性', '从 3 床位扩展到多病区', 'Docker Compose → KubeEdge'],
        ['安全性', '操作全审计；MQTT 匿名→ACL/TLS', '生产环境收紧'],
        ['经济性', '单床位约 1400 元', 'Orange Pi 5 + 低成本传感器']
      ],
      [1440, 4320, 3600]
    ),
    heading('3.4 事件状态机（闭环处置）', HeadingLevel.HEADING_2),
    para('所有事件必须走完闭环：new → notified → acknowledged → resolved / false_positive / escalated。'),
    bullet('new：边缘端新生成'),
    bullet('notified：已推送到护士站'),
    bullet('acknowledged：护士到场确认'),
    bullet('resolved：已处置'),
    bullet('false_positive：误报，标记后回流训练'),
    bullet('escalated：升级上级'),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

// ---------- Chapter 4: 团队分布式技术方向对应关系 ----------
function chapter4() {
  return [
    heading('四、团队分布式技术方向对应关系', HeadingLevel.HEADING_1),
    para('smart-ward 为 7 人团队分布式协作项目。下表列出每位成员的技术方向、负责模块、对应技术栈与依赖关系，确保职责清晰、接口对齐。'),
    heading('4.1 成员-技术方向-模块对应表', HeadingLevel.HEADING_2),
    makeTable(
      ['成员', '角色/方向', '负责模块', '关键技术', '依赖/协作'],
      [
        ['亚伦 (P1)', '边缘模型选型 + 技术框架', 'edge-agent 推理/融合、contracts/', 'YOLOv8n-pose、RKNN、OpenVINO、MQTT', '为景彬提供推理输出'],
        ['景彬 (P2)', '场景脚本 + 前端展示', 'scenario.py、cloud-frontend', 'Vue 3、ECharts、WebSocket', '依赖亚伦推理输出'],
        ['建鸿 (P3)', '项目统筹 + 训练 + 方案', 'training-coordinator、docs/', 'FedAvg、FastAPI、方案撰写', '统筹振鑫/先伟/烽亮'],
        ['振鑫 (P4)', '协同训练底层调度', 'scheduler.py', 'FedAvg、半异步陈旧度加权', '与建鸿联调'],
        ['先伟 (P5)', '扩散模型调优 + 数据集', 'diffusion-service（待建）', '扩散模型、困难样本筛选', '为烽亮提供数据'],
        ['烽亮 (P6)', '扩散模型开发 + 视频', 'diffusion-service（待建）', '扩散模型代码、部署', '依赖先伟数据'],
        ['彦晗 (P7)', '云边模型协同', 'docs/、链路打通', '云边协同方案、稳定性', '保障端到端链路']
      ],
      [1080, 1980, 2160, 1980, 2160]
    ),
    heading('4.2 技术方向与外部技术来源对应', HeadingLevel.HEADING_2),
    para('每个技术方向均有明确的外部技术依据，避免闭门造车：'),
    makeTable(
      ['技术方向', '本项目选型', '外部技术来源', '引用要点'],
      [
        ['边缘编排', 'Docker Compose → KubeEdge', 'KubeEdge 官方文档', '边缘自治、云边协同、DeviceTwin 设备管理'],
        ['边缘推理框架', 'OpenVINO（开发）/ RKNN（部署）', 'RKNN-Toolkit2 GitHub', 'RK3588 原生支持，PC 转换模型→板上推理'],
        ['视觉模型', 'YOLOv8n-pose INT8', 'Ultralytics YOLOv8 文档', '支持 pose/keypoints 检测，可导出 ONNX/TensorRT'],
        ['通信协议', 'MQTT QoS 1', 'HiveMQ MQTT Essentials', '发布订阅、QoS 0/1/2、retained、last will'],
        ['云端后端', 'FastAPI', 'FastAPI 官方', '高性能、类型提示、自动校验、Swagger'],
        ['云端数据库', 'MySQL 8.0', 'MySQL 8.0 官方手册', '关系型、可扩展、ACID'],
        ['边缘缓存', 'SQLite', 'SQLite 官方', '小型、自包含、高可靠、嵌入式'],
        ['联邦学习', '自研 FedAvg', 'Red Hat / Deloitte 趋势', '边缘 for immediacy，混合架构'],
        ['患者安全背景', '14 类事件设计依据', 'WHO 患者安全事实', '跌倒 3-5/1000 床日，1/10 患者受害'],
        ['护理人力背景', '“三不过来”痛点依据', 'WHO 护理 / AACN 缺口', '2030 缺口 450 万，美国 2028 缺 26.7 万']
      ],
      [1440, 2160, 2520, 3240]
    ),
    heading('4.3 模块间数据流与协作链路', HeadingLevel.HEADING_2),
    para('端到端数据流：传感器 → 边缘适配器 → 融合引擎 → 推理引擎 → SQLite 缓存 → MQTT 上行 → 云端事件中心 → WebSocket → 护士站前端。训练链路与实时业务隔离：误报回流 → 扩散模型生成困难样本 → 联邦训练 → 灰度下发。'),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

// ---------- Chapter 5: 数据指标 ----------
function chapter5() {
  return [
    heading('五、数据指标', HeadingLevel.HEADING_1),
    heading('5.1 行业背景数据指标', HeadingLevel.HEADING_2),
    makeTable(
      ['指标', '数值', '来源'],
      [
        ['全球患者受害比例', '1/10 患者受害；超 50% 可预防', 'WHO'],
        ['全球每年不安全医疗致死', '> 300 万', 'WHO'],
        ['医院跌倒发生率', '3-5 例/1000 床日；> 1/3 造成伤害', 'WHO'],
        ['用药错误影响', '1/30 患者；> 1/4 严重或危及生命', 'WHO'],
        ['压力性溃疡', '> 1/10 成年住院患者', 'WHO'],
        ['全球护士数量', '约 2900 万', 'WHO'],
        ['2030 护士缺口', '450 万（含助产士共 480 万）', 'WHO'],
        ['美国 2028 RN 缺口', '267,330 名', 'HRSA via AACN'],
        ['美国 RN 年空缺', '189,100/年（2024-2034）', 'BLS via AACN'],
        ['美国急性护理 RN 空缺率', '8.6%', 'NSI 2026 via AACN'],
        ['美国 RN 离职率', '17.6%', 'NSI 2026 via AACN'],
        ['美国护理学校拒收申请', '92,672 份（2025）', 'AACN']
      ],
      [2880, 3600, 2880]
    ),
    heading('5.2 技术性能指标（验收目标）', HeadingLevel.HEADING_2),
    makeTable(
      ['类别', '指标', '目标值', '技术依据'],
      [
        ['边缘推理', 'YOLOv8n-pose INT8 FPS', '15-30 FPS', 'RK3588 NPU + RKNN'],
        ['边缘推理', '模型大小（INT8 量化后）', '~6 MB', 'YOLOv8n-pose INT8'],
        ['事件时延', 'P1 紧急事件告警', '≤ 2 秒', '边缘本地决策'],
        ['事件时延', '事件上报延迟', '< 1 秒', 'MQTT QoS 1'],
        ['可靠性', '断网自治', '本地持续告警', 'SQLite 缓存'],
        ['可靠性', '事件不丢不重', 'event_id 去重', 'QoS 1 + 幂等'],
        ['带宽', '3 床位事件上报带宽', '< 10 KB/s', '边缘只传摘要'],
        ['带宽', '3 床位 1080p 全上云（对比）', '~12 Mbps', '边缘避免'],
        ['可用性', '护士站在线', '7×24', 'Docker restart: unless-stopped'],
        ['并发', '8 服务 Docker Compose', '一键启动', 'docker compose up'],
        ['成本', '单床位硬件预算', '~1400 元', 'Orange Pi 5 + 传感器'],
        ['测试', 'edge-agent 单元测试', '17 项全绿', 'test_fusion.py'],
        ['测试', 'training-coordinator 测试', '4 项全绿', 'test_scheduler.py']
      ],
      [1080, 2880, 2160, 3240]
    ),
    heading('5.3 事件优先级与处置时限', HeadingLevel.HEADING_2),
    makeTable(
      ['优先级', '含义', '处置要求', '前端表现'],
      [
        ['P1', '紧急', '立即确认；边缘端不等待云端', '置顶闪烁'],
        ['P2', '高', '5 分钟内确认', '待办队列'],
        ['P3', '提醒', '可批量处理', '待办队列']
      ],
      [1440, 2160, 3600, 2160]
    ),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

// ---------- Chapter 6: 调研任务清单 ----------
function chapter6() {
  return [
    heading('六、调研任务清单', HeadingLevel.HEADING_1),
    para('以下为支撑本项目技术选型与方案撰写需完成的调研任务，标注负责人、交付物与已参考来源。'),
    makeTable(
      ['编号', '调研任务', '负责人', '交付物', '已参考来源', '状态'],
      [
        ['T1', '边缘识别模型选型对比（YOLOv8n-pose / YOLOv10n / YOLO11n / MediaPipe）', '亚伦', '模型选型对比文档', 'Ultralytics YOLOv8 文档', '进行中'],
        ['T2', '边缘推理框架对比（ONNX/OpenVINO/TensorRT/RKNN）', '亚伦', '推理框架对比文档', 'RKNN-Toolkit2 GitHub', '进行中'],
        ['T3', 'INT8 量化方案与精度损失评估', '亚伦', '量化方案文档', 'Ultralytics / RKNN', '待启动'],
        ['T4', '目标硬件实测（Orange Pi 5 FPS/延迟/召回/误报）', '亚伦', '实测报告', 'RK3588 硬件手册', '待启动'],
        ['T5', 'MQTT 通信可靠性与断网补传验证', '亚伦/彦晗', '通信测试报告', 'HiveMQ MQTT Essentials', '进行中'],
        ['T6', '场景脚本完整 4 阶段实现', '景彬', 'scenario.py 更新', '项目内部需求', '进行中'],
        ['T7', '护士站前端组件化与可视化', '景彬', 'Vue 组件 + ECharts', 'Vue 3 / ECharts 官方', '进行中'],
        ['T8', 'FedAvg 同步基线实现', '振鑫', 'scheduler.py 聚合算法', '联邦学习论文', '进行中'],
        ['T9', '半异步陈旧度加权调度', '振鑫', '半异步策略对比', '联邦学习论文', '待启动'],
        ['T10', '云端扩散模型困难样本生成', '烽亮/先伟', 'diffusion-service', '扩散模型论文', '待启动'],
        ['T11', '云边模型协同链路打通', '彦晗', '端到端联调报告', 'KubeEdge 文档', '待启动'],
        ['T12', 'KubeEdge 多病区部署清单', '建鸿/彦晗', 'deploy/kubeedge/', 'KubeEdge 文档', '待启动'],
        ['T13', '患者安全行业背景调研', '建鸿', '行业现状章节', 'WHO 患者安全', '已完成'],
        ['T14', '护理人力短缺调研', '建鸿', '行业现状章节', 'WHO 护理 / AACN', '已完成'],
        ['T15', '边缘计算行业趋势调研', '建鸿', '行业现状章节', 'Red Hat / Deloitte', '已完成'],
        ['T16', '国内外厂商产品调研', '建鸿', '厂商格局章节', '各厂商官网', '已完成']
      ],
      [540, 2700, 1080, 1800, 2160, 1080]
    ),
    para('注：T1-T4 为亚伦近期里程碑（7/25 前选型文档，7/30 前 1 床位真实硬件接入）；T8-T9 为振鑫近期里程碑（7/30 前 FedAvg 同步基线，8/15 前半异步策略对比）。'),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

// ---------- Chapter 7: 参考来源 ----------
function chapter7() {
  return [
    heading('七、参考来源（真实网络来源）', HeadingLevel.HEADING_1),
    para('本报告所有数据与结论均来自以下公开网络来源，按主题分类列出：'),
    heading('7.1 患者安全与护理人力', HeadingLevel.HEADING_2),
    richPara([
      { text: '[WHO-PS] ' },
      { text: 'WHO — Patient Safety Fact Sheet', bold: true },
      { text: '. 世界卫生组织患者安全事实表，提供全球患者受害比例、跌倒发生率、用药错误、压力性溃疡等数据，以及 Global Patient Safety Action Plan 2021-2030。' }
    ]),
    hyperlinkPara('https://www.who.int/news-room/fact-sheets/detail/patient-safety', 'https://www.who.int/news-room/fact-sheets/detail/patient-safety'),
    richPara([
      { text: '[WHO-NM] ' },
      { text: 'WHO — Nursing and Midwifery Fact Sheet', bold: true },
      { text: '. 世界卫生组织护理与助产事实表，提供全球护士数量（2900 万）与 2030 年缺口（450 万）数据。' }
    ]),
    hyperlinkPara('https://www.who.int/news-room/fact-sheets/detail/nursing-and-midwifery', 'https://www.who.int/news-room/fact-sheets/detail/nursing-and-midwifery'),
    richPara([
      { text: '[AACN] ' },
      { text: 'AACN — Nursing Shortage Fact Sheet', bold: true },
      { text: '. 美国医学院护理学院协会护理短缺事实表，引用 HRSA 2028 年缺口、BLS 2024-2034 增长、NSI 2026 离职率及多项护士配置-患者结局研究。' }
    ]),
    hyperlinkPara('https://www.aacnnursing.org/news-information/fact-sheets/nursing-shortage', 'https://www.aacnnursing.org/news-information/fact-sheets/nursing-shortage'),
    heading('7.2 边缘计算与行业趋势', HeadingLevel.HEADING_2),
    richPara([
      { text: '[REDHAT] ' },
      { text: 'Red Hat — What is edge computing?', bold: true },
      { text: '. 边缘计算定义、架构分层（core/edge/device edge）、对延迟/带宽/可靠性的价值，以及临床决策应用。' }
    ]),
    hyperlinkPara('https://www.redhat.com/en/topics/edge-computing/what-is-edge-computing', 'https://www.redhat.com/en/topics/edge-computing/what-is-edge-computing'),
    richPara([
      { text: '[DELOITTE] ' },
      { text: 'Deloitte — Tech Trends 2026', bold: true },
      { text: '. 企业转向“cloud for elasticity, on-premises for consistency, and edge for immediacy”战略混合模式；Gartner 预测 40% agentic 项目失败。' }
    ]),
    hyperlinkPara('https://www.deloitte.com/us/en/insights/topics/technology-management/tech-trends.html', 'https://www.deloitte.com/us/en/insights/topics/technology-management/tech-trends.html'),
    heading('7.3 边缘编排与设备管理', HeadingLevel.HEADING_2),
    richPara([
      { text: '[KUBEEDGE] ' },
      { text: 'KubeEdge 官方文档', bold: true },
      { text: '. CNCF 毕业项目，将 K8s 容器编排与设备管理扩展到边缘节点。核心组件：CloudHub、EdgeHub、DeviceTwin、MetaManager（SQLite 边缘元数据）。' }
    ]),
    hyperlinkPara('https://kubeedge.io/zh/docs/', 'https://kubeedge.io/zh/docs/'),
    heading('7.4 边缘推理与视觉模型', HeadingLevel.HEADING_2),
    richPara([
      { text: '[ULTRALYTICS] ' },
      { text: 'Ultralytics YOLOv8 Documentation', bold: true },
      { text: '. YOLOv8 支持 detect/segment/classify/pose 任务，pose 变体含 yolov8n-pose 至 yolov8x-pose，可导出 PyTorch/ONNX/TensorRT 等格式。' }
    ]),
    hyperlinkPara('https://docs.ultralytics.com/models/yolov8/', 'https://docs.ultralytics.com/models/yolov8/'),
    richPara([
      { text: '[RKNN] ' },
      { text: 'Rockchip RKNN-Toolkit2 (GitHub)', bold: true },
      { text: '. 瑞芯微 AI 模型部署 SDK，支持 RK3588/RK3568 等芯片，工作流为 PC 转换模型 → 板上运行推理，支持 ONNX OPSET 12-19。' }
    ]),
    hyperlinkPara('https://github.com/rockchip-linux/rknn-toolkit2', 'https://github.com/rockchip-linux/rknn-toolkit2'),
    heading('7.5 通信协议', HeadingLevel.HEADING_2),
    richPara([
      { text: '[HIVEMQ] ' },
      { text: 'HiveMQ — MQTT Essentials', bold: true },
      { text: '. MQTT 定义（轻量级 IoT 消息协议）、发布/订阅模式、QoS 0/1/2 三级语义、retained message、last will 机制。' }
    ]),
    hyperlinkPara('https://www.hivemq.com/mqtt-essentials/', 'https://www.hivemq.com/mqtt-essentials/'),
    heading('7.6 云端与边缘数据存储', HeadingLevel.HEADING_2),
    richPara([
      { text: '[FASTAPI] ' },
      { text: 'FastAPI Official Documentation', bold: true },
      { text: '. 高性能 Python Web 框架，基于标准 Python 类型提示，自动校验（减少 40% 人为错误），自动生成 OpenAPI/Swagger 文档。' }
    ]),
    hyperlinkPara('https://fastapi.tiangolo.com/', 'https://fastapi.tiangolo.com/'),
    richPara([
      { text: '[MYSQL] ' },
      { text: 'MySQL 8.0 Reference Manual — What is MySQL?', bold: true },
      { text: '. 关系型数据库，数据存储在独立表中并强制关系规则保证一致性；可扩展至集群；MySQL HeatWave 集事务/实时分析/ML 于一体。' }
    ]),
    hyperlinkPara('https://dev.mysql.com/doc/refman/8.0/en/what-is-mysql.html', 'https://dev.mysql.com/doc/refman/8.0/en/what-is-mysql.html'),
    richPara([
      { text: '[SQLITE] ' },
      { text: 'SQLite Official Site', bold: true },
      { text: '. 小型、快速、自包含、高可靠性的 SQL 数据库引擎，全球最广泛使用的数据库，作为 C 语言库嵌入应用，适合边缘缓存。' }
    ]),
    hyperlinkPara('https://www.sqlite.org/index.html', 'https://www.sqlite.org/index.html'),
    heading('7.7 容器化部署', HeadingLevel.HEADING_2),
    richPara([
      { text: '[DOCKER] ' },
      { text: 'Docker — What is a Container?', bold: true },
      { text: '. 容器将应用与依赖打包，实现跨环境一致性、轻量高效、快速部署、隔离性。' }
    ]),
    hyperlinkPara('https://www.docker.com/resources/what-container/', 'https://www.docker.com/resources/what-container/'),
    new Paragraph({ spacing: { before: 400 } }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      border: { top: { style: BorderStyle.SINGLE, size: 6, color: '2E75B6', space: 8 } },
      children: [new TextRun({ text: '— 报告结束 —', size: 22, color: '666666', font: FONT })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 60 },
      children: [new TextRun({ text: '所有数据均标注真实网络来源，可直接核查', size: 18, color: '999999', font: FONT })]
    })
  ];
}

// ---------- Build document ----------
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: FONT, size: 22, color: '222222' } }
    },
    paragraphStyles: [
      {
        id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, font: FONT, color: '1F4E79' },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 }
      },
      {
        id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: FONT, color: '2E75B6' },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 }
      },
      {
        id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: FONT, color: '404040' },
        paragraph: { spacing: { before: 180, after: 90 }, outlineLevel: 2 }
      }
    ]
  },
  numbering: {
    config: [
      {
        reference: 'bullets',
        levels: [
          { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } } }
        ]
      },
      {
        reference: 'numbers',
        levels: [
          { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } } }
        ]
      }
    ]
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
        }
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              alignment: AlignmentType.RIGHT,
              border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: '2E75B6', space: 4 } },
              children: [new TextRun({ text: '智慧病房云边协同系统调研报告', size: 18, color: '888888', font: FONT })]
            })
          ]
        })
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ text: '第 ', size: 18, color: '666666', font: FONT }),
                new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '666666', font: FONT }),
                new TextRun({ text: ' 页  /  共 ', size: 18, color: '666666', font: FONT }),
                new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: '666666', font: FONT }),
                new TextRun({ text: ' 页', size: 18, color: '666666', font: FONT })
              ]
            })
          ]
        })
      },
      children: [
        ...coverPage(),
        ...tocPage(),
        ...chapter1(),
        ...chapter2(),
        ...chapter3(),
        ...chapter4(),
        ...chapter5(),
        ...chapter6(),
        ...chapter7()
      ]
    }
  ]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(OUTPUT, buffer);
  console.log(`已生成：${OUTPUT}`);
}).catch(err => {
  console.error('生成失败：', err);
  process.exit(1);
});
