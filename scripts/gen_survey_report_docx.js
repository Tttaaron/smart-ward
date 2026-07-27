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
  TabStopType,
  TabStopPosition,
  TableOfContents,
  LevelFormat,
  ImageRun
} = require('docx');

const OUTPUT = '智慧病房云边协同系统调研报告.docx';

// ---------- Helpers ----------
const border = { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 100, bottom: 100, left: 120, right: 120 };

function para(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 120, after: 120, line: 360 },
    ...opts,
    children: [new TextRun({ text, ...opts.run })]
  });
}

function heading(text, level = HeadingLevel.HEADING_1) {
  return new Paragraph({
    heading: level,
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text, bold: true })]
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: 'bullets', level },
    spacing: { before: 60, after: 60 },
    children: [new TextRun(text)]
  });
}

function numberItem(text, level = 0) {
  return new Paragraph({
    numbering: { reference: 'numbers', level },
    spacing: { before: 60, after: 60 },
    children: [new TextRun(text)]
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
        spacing: { before: 40, after: 40 },
        children: [
          new TextRun({
            text,
            bold: opts.bold || false,
            size: opts.size || 20,
            color: opts.color || '000000'
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
      tableCell(h, columnWidths[i], { shading: 'D9EAF7', bold: true, align: AlignmentType.CENTER })
    )
  });
  const dataRows = rows.map(row =>
    new TableRow({
      children: row.map((cell, i) => tableCell(cell, columnWidths[i]))
    })
  );
  return new Table({
    width: { size: width, type: WidthType.DXA },
    columnWidths,
    rows: [headerRow, ...dataRows]
  });
}

function coverPage() {
  return [
    new Paragraph({ spacing: { before: 1200 } }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [
        new TextRun({ text: '调研报告', size: 72, bold: true, color: '1F4E79' })
      ]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 200, after: 200 },
      children: [
        new TextRun({ text: '智慧病房云边协同系统', size: 56, bold: true, color: '1F4E79' })
      ]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 400, after: 400 },
      children: [
        new TextRun({ text: '行业背景 · 应用场景 · 技术选型 · 产品格局 · 应用价值', size: 28, color: '666666' })
      ]
    }),
    new Paragraph({ spacing: { before: 800 } }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: '调研时间：2026 年 7 月', size: 24, color: '666666' })]
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: '数据来源：smart-ward 项目文档、WHO / AACN / Red Hat / Ultralytics / KubeEdge / RKNN 等公开资料', size: 20, color: '999999' })]
    }),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

function tocPage() {
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 240, after: 240 },
      children: [new TextRun({ text: '目录', size: 36, bold: true })]
    }),
    new TableOfContents('Table of Contents', { hyperlink: true, headingStyleRange: '1-3' }),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

function chapter1() {
  return [
    heading('一、项目概述', HeadingLevel.HEADING_1),
    para('smart-ward 是一个面向病房患者安全的云边端协同智能监护系统。它从原智能教室项目复用技术路线，但领域模型、事件体系、数据契约、边缘推理和协同训练均针对智慧病房场景重新设计。'),
    heading('1.1 当前交付能力', HeadingLevel.HEADING_2),
    makeTable(
      ['维度', '内容'],
      [
        ['场景范围', '1 个病区（W-01）、3 张床位（B01/B02/B03）'],
        ['核心事件', '14 类安全事件：跌倒、坠床、离床、夜间徘徊、输液异常、抽搐、压疮、环境异常、设备故障、节点失联等'],
        ['智能功能', '10 项：坠床预警、跌倒检测、长时间静止、异常体态、抽搐检测、压疮预防、交接班摘要、环境自适应、空气质量联动、床位可视化'],
        ['技术栈', 'Vue 3 + FastAPI + MQTT + MySQL + SQLite + Docker Compose'],
        ['部署形态', '8 服务 Docker Compose 一键演示，目标硬件为 Orange Pi 5（RK3588 NPU）'],
        ['创新点', '边缘自治 + 云端集中 + 联邦学习协同训练 + 扩散模型困难样本生成']
      ],
      [2340, 7020]
    ),
    heading('1.2 系统架构', HeadingLevel.HEADING_2),
    para('系统采用“云-边-端”三层架构：云端提供护士站工作台、事件中心与协同训练；边缘端每床位部署独立代理，负责多源采集、融合推理与本地缓存；端侧连接摄像头、床垫传感器、输液监测与环境传感器。'),
    bullet('云端监控平台：cloud-frontend（Vue 3 护士站）、cloud-backend（FastAPI 事件中心）、training-coordinator（FastAPI 联邦学习调度器）、MySQL 8.0、Mosquitto MQTT Broker'),
    bullet('边缘代理：4 类采集适配器、融合引擎、推理引擎、SQLite 本地缓存、MQTT 客户端'),
    bullet('端侧设备：USB 摄像头、ESP32 + FSR402 床垫压力传感器、输液监测传感器、环境传感器（温湿度/CO₂/光照）'),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

function chapter2() {
  return [
    heading('二、行业背景与真实痛点', HeadingLevel.HEADING_1),
    heading('2.1 患者安全形势严峻', HeadingLevel.HEADING_2),
    para('根据世界卫生组织（WHO）数据，全球约 1/10 的患者在医疗过程中受到伤害，其中超过 50% 的伤害是可预防的。在医院病房中，最突出的安全问题包括跌倒、用药错误、压疮、输液异常与夜间徘徊等。'),
    makeTable(
      ['安全事件', '统计/影响'],
      [
        ['跌倒', '医院最常见的不良事件，发生率 3-5 例/1000 床日，超过 1/3 造成伤害'],
        ['用药错误', '占可预防伤害的近一半，1/30 患者受影响'],
        ['压疮', '长期卧床患者高发，增加感染风险和住院时间'],
        ['输液异常', '换药不及时、滴速异常、管路脱落等'],
        ['夜间徘徊', '老年痴呆/谵妄患者夜间游走，存在跌倒、走失风险']
      ],
      [2340, 7020]
    ),
    heading('2.2 护理资源严重短缺', HeadingLevel.HEADING_2),
    bullet('WHO 预测到 2030 年全球护士缺口将达 450 万人'),
    bullet('美国 HRSA 预测到 2028 年全职注册护士缺口达 26.7 万人'),
    bullet('中国护士人力同样紧张，一名护士常需同时看护 8-12 张床位，夜间值班人力更少'),
    para('这导致病房护理面临“三不过来”：看不过来、跑不过来、记不过来。'),
    heading('2.3 传统监护系统的局限', HeadingLevel.HEADING_2),
    makeTable(
      ['传统方案', '不足'],
      [
        ['呼叫按钮', '需患者主动触发，失能/昏迷/跌倒患者无法使用'],
        ['中央监护屏', '只能看视频，无法自动识别风险'],
        ['单一传感器', '误报率高（床垫误判翻身、摄像头遮挡）'],
        ['纯云端方案', '断网即瘫痪、时延高、隐私风险大'],
        ['纸质交接班', '信息滞后、易遗漏、难以追溯']
      ],
      [2340, 7020]
    ),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

function chapter3() {
  return [
    heading('三、智能病房核心应用场景', HeadingLevel.HEADING_1),
    para('智能病房通过多源感知、边缘智能、云边协同，实现从“被动响应”到“主动预防”的转变。smart-ward 覆盖的应用场景可分为以下几类：'),
    heading('3.1 患者安全实时监测', HeadingLevel.HEADING_2),
    heading('3.1.1 跌倒检测与坠床预警', HeadingLevel.HEADING_3),
    bullet('技术路径：YOLOv8n-pose 姿态估计 + 床垫压力传感融合'),
    bullet('事前预警：检测到患者处于床边危险体位（lying_edge）且跌倒置信度升高时，提前数秒告警'),
    bullet('事后检测：摄像头识别 falling 姿态 + fall_score 阈值 + 床位离床确认'),
    bullet('临床价值：将跌倒发现时间从“数分钟”缩短到“秒级”，降低骨折、颅脑损伤等严重后果'),
    heading('3.1.2 离床/夜间徘徊监测', HeadingLevel.HEADING_3),
    bullet('技术路径：床垫 FSR402 压力传感器 + 摄像头人员存在检测'),
    bullet('触发条件：床位 absence_seconds ≥ 30 秒（可调），夜间时段（22:00-06:00）+ 持续离床'),
    bullet('临床价值：防止术后患者擅自下床、老年痴呆患者夜间走失'),
    heading('3.1.3 长时间静止与异常体态', HeadingLevel.HEADING_3),
    bullet('长时间静止：同一体位持续 ≥ 5 分钟，可能提示昏迷、不适'),
    bullet('异常体态：蜷缩（curled）、前倾（leaning）、抓胸（grabbing_chest）可能是急症早期信号'),
    heading('3.1.4 抽搐检测', HeadingLevel.HEADING_3),
    bullet('技术路径：视觉姿态序列分析 + tremor_score 阈值'),
    bullet('临床价值：癫痫等神经系统疾病夜间发作可自动发现'),
    heading('3.2 治疗过程监护', HeadingLevel.HEADING_2),
    heading('3.2.1 输液监测', HeadingLevel.HEADING_3),
    bullet('感知设备：输液滴速/液位传感器'),
    bullet('异常类型：滴速异常、低液位、输液完成、管路中断'),
    bullet('临床价值：减少护士反复巡房，避免回血、空气栓塞等风险'),
    heading('3.2.2 压疮预防', HeadingLevel.HEADING_3),
    bullet('触发条件：同一体位持续 ≥ 2 小时'),
    bullet('处置方式：P3 提醒事件，提醒护士协助翻身'),
    bullet('临床价值：降低长期卧床患者压疮发生率'),
    heading('3.3 环境与设备管理', HeadingLevel.HEADING_2),
    heading('3.3.1 环境异常监测', HeadingLevel.HEADING_3),
    bullet('监测指标：温度、湿度、CO₂、光照'),
    bullet('联动控制：温度/CO₂ 超标可联动空调、新风、照明'),
    bullet('临床价值：改善患者康复环境，降低院内感染风险'),
    heading('3.3.2 设备故障与节点失联', HeadingLevel.HEADING_3),
    bullet('设备故障：传感器 quality.degraded 持续 ≥ 60 秒'),
    bullet('节点失联：云端检测边缘节点健康心跳超时'),
    bullet('临床价值：避免监护盲区，保证系统 7×24 可用'),
    heading('3.4 护理 workflow 数字化', HeadingLevel.HEADING_2),
    heading('3.4.1 告警闭环处置', HeadingLevel.HEADING_3),
    para('事件状态机：new → notified → acknowledged → resolved / false_positive / escalated'),
    bullet('护士到场确认（acknowledge）'),
    bullet('处置完成（resolve）'),
    bullet('标记误报（false_positive，回流训练）'),
    bullet('升级上级（escalate）'),
    heading('3.4.2 交接班摘要', HeadingLevel.HEADING_3),
    bullet('按班次（白班/晚班/夜班）自动汇总事件'),
    bullet('接班护士确认后归档'),
    bullet('减少信息遗漏，提升护理连续性'),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

function chapter4() {
  return [
    heading('四、关键技术栈与选型依据', HeadingLevel.HEADING_1),
    heading('4.1 边缘计算：从云端到床旁', HeadingLevel.HEADING_2),
    para('边缘计算将算力下沉到病床旁，解决时延、带宽、可靠性与隐私问题。'),
    makeTable(
      ['问题', '边缘计算价值'],
      [
        ['时延', '跌倒/坠床事件本地秒级识别，无需云端往返'],
        ['带宽', '3 张床位 1080p 视频全上云约 12 Mbps，边缘只传事件摘要 < 10 KB/s'],
        ['可靠性', '断网时仍可本地决策和告警'],
        ['隐私', '患者视频不出本地，仅上传脱敏事件摘要']
      ],
      [2340, 7020]
    ),
    heading('4.2 边缘平台对比', HeadingLevel.HEADING_2),
    makeTable(
      ['框架', '定位', '边缘自治', '适合病房'],
      [
        ['Docker Compose', '单机容器编排', '需自建', '演示阶段'],
        ['KubeEdge', 'K8s 原生云边协同', '原生支持', '真实病房交付'],
        ['OpenYurt', 'K8s 无侵入边缘扩展', '较好', '备选'],
        ['K3s', '轻量 K8s 发行版', '弱', '边缘单机'],
        ['EdgeX Foundry', 'IoT 边缘中间件', '部分', '设备接入层']
      ],
      [2340, 2340, 2340, 2340]
    ),
    para('smart-ward 选型：演示阶段 Docker Compose，交付阶段演进至 KubeEdge。'),
    heading('4.3 边缘推理与视觉模型', HeadingLevel.HEADING_2),
    heading('4.3.1 目标硬件', HeadingLevel.HEADING_3),
    bullet('Orange Pi 5：RK3588 6 TOPS NPU，8GB RAM'),
    bullet('单床位预算约 1400 元'),
    heading('4.3.2 推理框架对比', HeadingLevel.HEADING_3),
    makeTable(
      ['框架', '目标硬件', 'RK3588 支持', 'YOLOv8n-pose 性能'],
      [
        ['ONNX Runtime', '通用 CPU/GPU', '不支持', '5-8 FPS（CPU）'],
        ['OpenVINO', 'Intel CPU/iGPU/VPU', '间接', '8-12 FPS'],
        ['TensorRT', 'NVIDIA GPU', '不支持', '不适用'],
        ['RKNN', '瑞芯微 RK3588', '原生支持', '15-30 FPS']
      ],
      [2340, 2340, 2340, 2340]
    ),
    para('smart-ward 选型：开发用 OpenVINO，部署用 RKNN。'),
    heading('4.3.3 视觉模型对比', HeadingLevel.HEADING_3),
    makeTable(
      ['模型', '任务', '关键点', '跌倒分', 'INT8 量化', 'RK3588 FPS'],
      [
        ['YOLOv8n-pose', '姿态+检测', '17', '直接输出', '~6 MB', '15-30'],
        ['YOLOv10n', '纯检测', '无', '需后处理', '~4 MB', '25-40'],
        ['YOLO11n', '纯检测', '无', '需后处理', '~4 MB', '25-40'],
        ['MediaPipe Pose', '姿态', '33', '无', '不支持', '10-15（CPU）']
      ],
      [1560, 1560, 1560, 1560, 1560, 1560]
    ),
    para('smart-ward 选型：YOLOv8n-pose INT8。核心理由是唯一原生支持“姿态 + 跌倒置信度”双输出，且量化后仅 6MB，适合 Orange Pi 5 部署。'),
    heading('4.4 通信协议：MQTT QoS 1', HeadingLevel.HEADING_2),
    makeTable(
      ['维度', 'MQTT', 'HTTP', 'WebSocket'],
      [
        ['通信模式', '发布/订阅', '请求/响应', '双向长连接'],
        ['QoS 支持', '0/1/2', '无', '无'],
        ['断线重连', '自动', '需自建', '需自建'],
        ['单包开销', '极小（2 字节头）', '大', '中'],
        ['多对多', '天然支持', '需轮询', '需多连接']
      ],
      [2340, 2340, 2340, 2340]
    ),
    para('smart-ward 选型：MQTT QoS 1 + SQLite 本地缓存 + event_id 幂等去重。'),
    bullet('QoS 1 保证“至少一次送达”'),
    bullet('边缘 SQLite 落盘缓存，断网期间持续写入'),
    bullet('event_id 全局唯一，云端去重，补传不产生重复告警'),
    heading('4.5 联邦学习：隐私合规下的模型协同', HeadingLevel.HEADING_2),
    makeTable(
      ['框架', '厂商', '病房场景定制', '与 MQTT 集成'],
      [
        ['Flower', '开源社区', '需适配', '需额外适配'],
        ['NVIDIA FLARE', 'NVIDIA', '需适配', '需额外适配'],
        ['自研 FedAvg', '本项目', '按病房定制', '原生复用 MQTT 训练主题']
      ],
      [2340, 2340, 2340, 2340]
    ),
    para('smart-ward 选型：自研 FedAvg + 半异步陈旧度加权聚合。'),
    bullet('阶段 A：同步 FedAvg 基线'),
    bullet('阶段 B：半异步调度（超时窗口 + 最小参与节点数 + 陈旧度权重）'),
    bullet('阶段 C：异常剔除 + 训练日志全链路'),
    bullet('与云端扩散模型联动：误报回流 → 扩散生成困难样本 → 联邦训练 → 灰度下发'),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

function chapter5() {
  return [
    heading('五、国内外产品与厂商格局', HeadingLevel.HEADING_1),
    heading('5.1 国际厂商', HeadingLevel.HEADING_2),
    makeTable(
      ['厂商', '代表产品/方案', '特点'],
      [
        ['Philips', 'HealthSuite / Patient Monitoring', '医疗 IoT 平台，患者监测设备丰富'],
        ['GE HealthCare', 'Portrait Mobile / FlexAcuity', '统一监测平台，可穿戴设备，报警管理'],
        ['Medtronic', 'Continuous Patient Monitoring / RPM', '连续监测、远程患者管理'],
        ['Siemens Healthineers', 'Digital Health Solutions', '影像+监测+数字健康'],
        ['Cisco', 'Smart Hospital Networking', '网络基础设施与安全'],
        ['Microsoft / AWS / Google', 'Azure IoT / AWS IoT Greengrass / Cloud Healthcare API', '云边协同平台、医疗数据互操作']
      ],
      [2340, 3510, 3510]
    ),
    heading('5.2 国内厂商', HeadingLevel.HEADING_2),
    makeTable(
      ['厂商', '代表产品/方案', '特点'],
      [
        ['华为', 'IEF 智能边缘（KubeEdge 商业版）', '云边协同，K8s 原生'],
        ['海康威视', 'AI 摄像头、智慧病房视频方案', '视觉跌倒检测能力强'],
        ['大华', 'AIoT 智慧病房解决方案', '视频-centric，火灾/安全监控'],
        ['联想', '边缘计算解决方案', '智慧医疗边缘部署'],
        ['阿里', 'OpenYurt 边缘计算', 'K8s 无侵入扩展'],
        ['百度', 'Baetyl 边缘计算框架', '端边云一体化']
      ],
      [2340, 3510, 3510]
    ),
    heading('5.3 同类方案对比', HeadingLevel.HEADING_2),
    makeTable(
      ['方案类型', '典型做法', '不足', 'smart-ward 改进'],
      [
        ['纯云端方案', '视频全传云端识别', '断网瘫痪、时延高、隐私风险', '边缘自治 + 仅传事件摘要'],
        ['纯本地方案', '呼叫按钮 + 床垫报警', '无集中监控、无趋势分析', '云端护士站 + 交接班摘要'],
        ['单传感器方案', '仅床垫或仅摄像头', '误报率高', '四源融合 + 规则引擎'],
        ['商业封闭方案', '整体采购黑盒系统', '不可定制、成本高', '开源自研 + 可演进'],
        ['云边协同（smart-ward）', '边缘多源融合 + 云端集中 + 协同训练', '-', '兼顾自治、集中、隐私、演进']
      ],
      [1560, 2340, 2340, 2340]
    ),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

function chapter6() {
  return [
    heading('六、市场规模与发展趋势', HeadingLevel.HEADING_1),
    heading('6.1 医疗 IoT 市场', HeadingLevel.HEADING_2),
    para('医疗 IoT 是智慧病房的基础设施。公开信息一致显示：'),
    bullet('全球医疗 IoT 市场在 2024-2030 年间保持高速增长'),
    bullet('主要驱动因素：老龄化、慢性病增加、护理人力短缺、5G/边缘计算成熟、AI 视觉技术进步'),
    bullet('主要应用：远程患者监测、智能病床、可穿戴设备、环境监控、用药管理'),
    heading('6.2 智慧病房发展趋势', HeadingLevel.HEADING_2),
    numberItem('从被动响应到主动预防：从患者呼叫护士，到系统主动发现风险'),
    numberItem('从单点设备到多源融合：摄像头、床垫、输液、环境传感器融合决策'),
    numberItem('从云端集中到云边协同：边缘自治保证实时性和可靠性'),
    numberItem('从数据孤岛到联邦智能：隐私合规下的多节点协同训练'),
    numberItem('从固定病房到数字孪生：通过实时数据构建病房数字镜像'),
    numberItem('从辅助工具到护理 workflow 平台：告警闭环、交接班、审计一体化'),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

function chapter7() {
  return [
    heading('七、应用价值与创新点', HeadingLevel.HEADING_1),
    heading('7.1 应用价值', HeadingLevel.HEADING_2),
    makeTable(
      ['价值维度', '具体体现'],
      [
        ['患者安全', '跌倒/坠床/离床/抽搐等事件的秒级发现，缩短救治黄金时间'],
        ['护士效率', '减少无效巡房，自动汇总交接班，降低工作负荷'],
        ['护理质量', '事件全闭环、操作全审计，可追溯、可复盘'],
        ['部署成本', '单床位约 1400 元，适合规模化推广'],
        ['隐私合规', '原始视频留边缘，仅上传脱敏事件摘要']
      ],
      [2340, 7020]
    ),
    heading('7.2 核心创新点', HeadingLevel.HEADING_2),
    numberItem('多源融合降低误报：摄像头 + 床垫 + 输液 + 环境四源融合，规则引擎加权决策'),
    numberItem('平台无关的断网自治：SQLite 缓存 + event_id 去重，不依赖特定边缘平台'),
    numberItem('自研联邦学习框架：同步/半异步聚合，与 MQTT 业务链路解耦'),
    numberItem('扩散模型困难样本生成：云端生成困难样本，持续提升模型精度'),
    numberItem('模型灰度部署与回滚：支持按节点灰度下发、失败自动回退'),
    heading('7.3 当前状态与后续演进', HeadingLevel.HEADING_2),
    makeTable(
      ['阶段', '状态', '目标'],
      [
        ['演示阶段', '已完成', 'Docker Compose 8 服务联调，10 项智能功能，17+4 测试'],
        ['模型接入', '进行中', 'YOLOv8n-pose INT8 真实模型接入 Orange Pi 5'],
        ['训练闭环', '进行中', 'FedAvg 实现、半异步调度、扩散模型困难样本'],
        ['真实部署', '待启动', 'KubeEdge 多病区部署、真实硬件接入']
      ],
      [2340, 2340, 4680]
    ),
    new Paragraph({ children: [new PageBreak()] })
  ];
}

function chapter8() {
  return [
    heading('八、结论', HeadingLevel.HEADING_1),
    para('智慧病房是医疗数字化转型的核心场景之一。面对患者安全风险高、护理人力短缺、传统监护手段滞后等现实挑战，云边协同 + 多源感知 + AI 视觉 + 联邦学习已成为主流技术路线。'),
    para('smart-ward 项目技术选型务实、架构清晰、应用场景明确：'),
    bullet('演示阶段：Docker Compose 快速验证业务闭环'),
    bullet('目标硬件：Orange Pi 5 + RK3588 NPU 实现低成本边缘智能'),
    bullet('演进方向：KubeEdge 多病区部署 + 联邦学习持续优化模型'),
    para('项目当前已完成端到端骨架，后续重点在于真实模型接入、目标硬件实测、联邦学习闭环和扩散模型困难样本生成。若能按计划落地，将形成一个具有实际应用价值的智慧病房患者安全守护平台。'),
    new Paragraph({ spacing: { before: 480 } }),
    new Paragraph({
      alignment: AlignmentType.RIGHT,
      children: [
        new TextRun({ text: '调研时间：2026-07-22', size: 20, color: '666666' }),
        new TextRun({ break: true, text: '数据来源：smart-ward 项目代码库、docs/ 文档、WHO / AACN / Red Hat / Ultralytics / KubeEdge / RKNN / FastAPI / Vue / ECharts / SQLite / MySQL / Docker 等公开资料', size: 20, color: '999999' })
      ]
    })
  ];
}

// ---------- Build document ----------
const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: 'Arial', size: 22, color: '000000' }
      }
    },
    paragraphStyles: [
      {
        id: 'Heading1',
        name: 'Heading 1',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: { size: 36, bold: true, font: 'Arial', color: '1F4E79' },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 }
      },
      {
        id: 'Heading2',
        name: 'Heading 2',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: { size: 28, bold: true, font: 'Arial', color: '2E75B6' },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 }
      },
      {
        id: 'Heading3',
        name: 'Heading 3',
        basedOn: 'Normal',
        next: 'Normal',
        quickFormat: true,
        run: { size: 24, bold: true, font: 'Arial', color: '404040' },
        paragraph: { spacing: { before: 180, after: 90 }, outlineLevel: 2 }
      }
    ]
  },
  numbering: {
    config: [
      {
        reference: 'bullets',
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: '•',
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } }
          }
        ]
      },
      {
        reference: 'numbers',
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: '%1.',
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } }
          }
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
              children: [
                new TextRun({ text: '智慧病房云边协同系统调研报告', size: 18, color: '999999' })
              ]
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
                new TextRun({ text: '第 ', size: 18, color: '666666' }),
                new TextRun({ children: [PageNumber.CURRENT], size: 18, color: '666666' }),
                new TextRun({ text: ' 页', size: 18, color: '666666' })
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
        ...chapter7(),
        ...chapter8()
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
