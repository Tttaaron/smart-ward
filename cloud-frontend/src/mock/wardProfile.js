/**
 * 演示用病区档案（前端集中维护，组件只读）
 *
 * 后端目前不提供患者/医护档案与值班表（仅有 patient_alias 与节点数据），
 * 因此这些展示数据由前端统一维护，避免散落在各组件中。
 * 事件/病区/摘要的演示兜底数据（后端不可用时的演示模式）也在此集中定义。
 */

// ---- 床位患者档案 ----
export const PATIENTS = {
  B01: {
    gender: '女',
    age: 68,
    careLevel: { label: '特级护理', tone: 'danger' },
    nurse: '张莉',
    doctor: '王主任',
    risks: [
      { text: '防跌倒', tone: 'danger' },
      { text: '防压疮', tone: 'warning' },
      { text: '禁食', tone: 'info' },
    ],
  },
  B02: {
    gender: '男',
    age: 74,
    careLevel: { label: 'Ⅰ级护理', tone: 'warning' },
    nurse: '李秀',
    doctor: '陈医师',
    risks: [
      { text: '防跌倒', tone: 'danger' },
      { text: '高龄', tone: 'info' },
    ],
  },
  B03: {
    gender: '女',
    age: 59,
    careLevel: { label: 'Ⅱ级护理', tone: 'info' },
    nurse: '王婷',
    doctor: '刘医师',
    risks: [{ text: '防坠床', tone: 'warning' }],
  },
}

/** 默认患者档案（未知床位时兜底） */
export const DEFAULT_PATIENT = {
  gender: '',
  age: null,
  careLevel: { label: '常规护理', tone: 'info' },
  nurse: '—',
  doctor: '—',
  risks: [],
}

export const patientOf = (bedId) => PATIENTS[bedId] || DEFAULT_PATIENT

// ---- 当前值守人员 ----
export const STAFF = {
  onDuty: { name: '张莉', role: '主管护师' },   // 值班护士
  doctor: { name: '王主任', role: '责任医生' },  // 责任医生
  successor: '李秀',                            // 接班护士（交接班签名）
}

// ---- 演示兜底数据（后端不可用时） ----
export const demoTimestamp = (secondsAgo = 0) =>
  new Date(Date.now() - secondsAgo * 1000).toISOString()

export const demoWards = () => [{
  id: 'W-01',
  name: '普通病房 W-01',
  location: '三楼东侧',
  pending_alerts: 2,
  nodes: [
    { id: 'EDGE-W01-B01', bed_id: 'B01', status: 'online', last_heartbeat: demoTimestamp(), model_version: 'edge-vision@1.0.0' },
    { id: 'EDGE-W01-B02', bed_id: 'B02', status: 'online', last_heartbeat: demoTimestamp(), model_version: 'edge-vision@1.0.0' },
    { id: 'EDGE-W01-B03', bed_id: 'B03', status: 'online', last_heartbeat: demoTimestamp(), model_version: 'edge-vision@1.0.0' },
  ],
  beds: [
    { id: 'B01', name: '1床', status: 'alert', pending_events: 1, patient_alias: '张阿姨' },
    { id: 'B02', name: '2床', status: 'occupied', pending_events: 1, patient_alias: '李伯伯' },
    { id: 'B03', name: '3床', status: 'occupied', pending_events: 0, patient_alias: '王奶奶' },
  ],
}]

export const demoEvents = () => [
  {
    event_id: 'demo-event-01', event_type: 'fall_prediction', priority: 'P1', state: 'new',
    confidence: 0.94, bed_id: 'B01', node_id: 'EDGE-W01-B01', occurred_at: demoTimestamp(42),
    model_name: 'edge-vision', model_version: '1.0.0',
    details: { route: 'edge', network: 'online', trace_id: 'demo-p1-01', inference_ms: 86, ttft_ms: 58 },
  },
  {
    event_id: 'demo-event-02', event_type: 'nurse_call', priority: 'P1', state: 'acknowledged',
    confidence: 0.91, bed_id: 'B02', node_id: 'EDGE-W01-B02', occurred_at: demoTimestamp(96),
    model_name: 'audio-fusion', model_version: '0.9.4',
    details: { route: 'hybrid', network: 'online', trace_id: 'demo-p1-02', inference_ms: 112, cloud_latency_ms: 186 },
  },
  {
    event_id: 'demo-event-03', event_type: 'long_still', priority: 'P2', state: 'notified',
    confidence: 0.82, bed_id: 'B03', node_id: 'EDGE-W01-B03', occurred_at: demoTimestamp(156),
    model_name: 'rule-fusion', model_version: '0.1.0',
    details: { route: 'edge', network: 'online', trace_id: 'demo-p2-03', inference_ms: 42 },
  },
]

export const demoShiftSummaries = () => [{
  id: 'demo-shift-01',
  shift_date: new Date().toISOString().slice(0, 10),
  shift_period: 'day',
  event_count: 3, p1_count: 2, p2_count: 1, resolved_count: 1, false_positive_count: 0,
  summary_text: 'B01床存在坠床风险，已提高巡视频次；B02床呼叫已到场处置。边缘节点运行稳定，未发现设备离线。',
}]
