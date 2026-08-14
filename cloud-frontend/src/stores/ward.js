/**
 * 护士站全局状态（组合式单例 store，零依赖）
 *
 * 从原 App.vue 迁入：所有 REST/WS 数据加载、演示降级保护、告警处置、
 * 交班摘要与浮层开关统一在此维护，各视图共享同一份实时状态。
 * 图表刷新通过 refreshTick 计数驱动（处置/WS 事件后自增）。
 */
import { reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api/index.js'
import ws from '../api/websocket.js'
import { demoWards, demoEvents, demoShiftSummaries } from '../mock/wardProfile.js'

const state = reactive({
  // ---- 业务数据 ----
  wards: [],
  events: [],
  nodes: [],
  stats: {},
  currentTime: '',
  shiftSummaries: [],
  shiftDate: new Date().toISOString().slice(0, 10),
  shiftPeriod: 'day',
  generating: false,

  // ---- 浮层 ----
  monitorVisible: false,
  monitorBedId: 'B01',
  monitorEventType: 'fall_suspected',
  monitorConfidence: 0.9,
  modelVisible: false,
  detailVisible: false,
  detailEventId: '',

  // ---- 链路可观测性 ----
  wsStatus: {
    status: 'disconnected',
    reconnectCount: 0,
    connectedAt: null,
    disconnectedAt: null,
    messageCount: {},
  },
  apiHealthy: true,
  demoMode: false,
  presentationFallback: false,

  // ---- 图表刷新信号 ----
  refreshTick: 0,

  // ---- 生命周期 ----
  started: false,
})

const detailEvent = computed(
  () => state.events.find((event) => event.event_id === state.detailEventId) || null
)

const liveSources = new Set()
const preferLiveData = new URLSearchParams(window.location.search).get('live') === '1'

const OPERATOR = {
  operator_id: 'nurse-demo',
  operator_name: '演示护士',
  operator_role: 'nurse',
}

const numericValue = (value) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const hasPresentationOutliers = (nextStats = {}, nextWards = []) => {
  if (preferLiveData) return false
  if (
    numericValue(nextStats.pending_events) > 100 ||
    numericValue(nextStats.p1_pending) > 20 ||
    numericValue(nextStats.events_today) > 200
  ) return true
  return nextWards.some((ward) => (
    numericValue(ward.pending_alerts) > 100 ||
    ward.beds?.some((bed) => numericValue(bed.pending_events) > 100)
  ))
}

const useDemoFallback = ({ replace = false } = {}) => {
  state.demoMode = true
  if (replace || !state.wards.length) state.wards = demoWards()
  if (replace || !state.events.length) state.events = demoEvents()
  if (replace || !state.nodes.length) state.nodes = state.wards[0]?.nodes || []
  if (replace || !state.shiftSummaries.length) state.shiftSummaries = demoShiftSummaries()
  if (replace || !Object.keys(state.stats).length) {
    state.stats = {
      total_beds: 3, occupied_beds: 3, leave_beds: 1,
      online_nodes: 3, total_nodes: 3, p1_pending: 1,
      pending_events: 3, events_today: 12,
    }
  }
}

const activatePresentationFallback = () => {
  if (state.presentationFallback) return
  state.presentationFallback = true
  useDemoFallback({ replace: true })
}

const markLiveSource = (source) => {
  if (state.presentationFallback) return
  liveSources.add(source)
  if (['wards', 'events', 'nodes', 'stats', 'shifts'].every((key) => liveSources.has(key))) {
    state.demoMode = false
  }
}

const bumpCharts = () => {
  state.refreshTick += 1
}

// ---- 数据加载 ----
const loadWards = async () => {
  try {
    const res = await api.getWards()
    const nextWards = res.data.data || []
    if (hasPresentationOutliers({}, nextWards)) {
      activatePresentationFallback()
      return
    }
    if (state.presentationFallback) return
    state.wards = nextWards
    markLiveSource('wards')
  } catch (e) {
    console.error('加载病区失败', e)
    state.apiHealthy = false
    useDemoFallback()
  }
}

const loadEvents = async () => {
  try {
    const res = await api.getEvents({ hours: 24, limit: 50 })
    if (state.presentationFallback) return
    state.events = res.data.data || []
    markLiveSource('events')
  } catch (e) {
    console.error('加载事件失败', e)
    state.apiHealthy = false
    useDemoFallback()
  }
}

const loadNodes = async () => {
  try {
    const res = await api.getNodes('W-01')
    if (state.presentationFallback) return
    state.nodes = res.data.data || []
    markLiveSource('nodes')
  } catch (e) {
    console.error('加载节点失败', e)
    useDemoFallback()
  }
}

const loadStats = async () => {
  try {
    const res = await api.getStats()
    state.apiHealthy = true
    const nextStats = res.data.data || {}
    if (hasPresentationOutliers(nextStats)) {
      activatePresentationFallback()
      return
    }
    if (state.presentationFallback) return
    state.stats = nextStats
    markLiveSource('stats')
  } catch (e) {
    console.error('加载统计失败', e)
    state.apiHealthy = false
    useDemoFallback()
  }
}

const loadShiftSummaries = async () => {
  try {
    const res = await api.getShiftSummaries({ ward_id: 'W-01', limit: 10 })
    if (state.presentationFallback) return
    state.shiftSummaries = res.data.data || []
    markLiveSource('shifts')
  } catch (e) {
    console.error('加载摘要失败', e)
    useDemoFallback()
  }
}

// ---- 告警处置 ----
const ACK_STATE_MAP = {
  acknowledge: 'acknowledged',
  resolve: 'resolved',
  false_positive: 'false_positive',
  escalate: 'escalated',
}

const onAck = async (evt, action) => {
  if (state.demoMode) {
    evt.state = ACK_STATE_MAP[action] || evt.state
    bumpCharts()
    return
  }
  try {
    await api.ackEvent(evt.event_id, { action, ...OPERATOR })
    evt.state = ACK_STATE_MAP[action] // 乐观更新
    loadWards()
    loadStats()
    bumpCharts()
  } catch (e) {
    console.error('确认失败', e)
    ElMessage.error('处置失败，请查看后端日志')
  }
}

// ---- 交班摘要 ----
const onGenerateSummary = async () => {
  state.generating = true
  try {
    if (state.demoMode) {
      state.shiftSummaries = demoShiftSummaries()
      return
    }
    await api.generateShiftSummary({
      ward_id: 'W-01',
      shift_date: state.shiftDate,
      shift_period: state.shiftPeriod,
      operator_id: OPERATOR.operator_id,
    })
    await loadShiftSummaries()
    bumpCharts()
  } catch (e) {
    console.error('生成摘要失败', e)
    ElMessage.error('生成失败，请查看后端日志')
  } finally {
    state.generating = false
  }
}

const onDeleteSummary = async (summaryId) => {
  try {
    await ElMessageBox.confirm('确定删除该交接班摘要？删除后不可恢复。', '删除摘要', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch (e) {
    return // 用户取消
  }

  if (state.demoMode) {
    state.shiftSummaries = state.shiftSummaries.filter((summary) => summary.id !== summaryId)
    return
  }
  try {
    await api.deleteShiftSummary(summaryId)
    await loadShiftSummaries()
    ElMessage.success('摘要已删除')
  } catch (e) {
    console.error('删除摘要失败', e)
    ElMessage.error('删除失败')
  }
}

// ---- 实时监护浮层 ----
const openMonitor = (bed) => {
  state.monitorBedId = bed.id || bed.bed_id || 'B01'
  const activeEvent = state.events.find(
    (e) => e.bed_id === state.monitorBedId && ['new', 'notified', 'acknowledged'].includes(e.state)
  )
  if (activeEvent) {
    state.monitorEventType = activeEvent.event_type
    state.monitorConfidence = activeEvent.confidence || 0.9
  } else {
    state.monitorEventType = bed.status === 'alert' ? 'fall_suspected' : 'nurse_call'
    state.monitorConfidence = 0.95
  }
  state.monitorVisible = true
}

const openMonitorFromEvent = (evtData) => {
  state.monitorBedId = evtData.id || 'B01'
  state.monitorEventType = evtData.eventType || 'fall_suspected'
  state.monitorConfidence = evtData.confidence || 0.9
  state.monitorVisible = true
}

// ---- 事件详情抽屉 ----
const openDetail = (eventId) => {
  state.detailEventId = eventId
  state.detailVisible = true
}

// ---- WebSocket 消息处理 ----
const onWsMessage = (msg) => {
  // 展示保护模式使用一组可控的演示事件，避免后端历史累计数据持续灌入队列。
  // ?live=1 会绕过该保护，保留完整实时通道用于联调与排障。
  if (state.presentationFallback) return

  if (msg.type === 'safety_event') {
    const raw = msg.data || {}
    state.events.unshift({
      event_id: msg.event_id,
      event_type: msg.event_type,
      priority: msg.priority,
      state: msg.state,
      confidence: msg.confidence,
      bed_id: msg.bed_id,
      node_id: msg.node_id,
      occurred_at: msg.occurred_at,
      model_name: raw.model?.model_name || raw.model_name || null,
      model_version: raw.model?.model_version || raw.model_version || null,
      inference_ms: raw.model?.inference_ms || raw.inference_ms || null,
      details: raw.details || {},
    })

    if (state.events.length > 50) state.events.pop()

    // P1 紧急事件自动唤起监护画面
    const isCritical = msg.priority === 'P1' ||
      ['fall_suspected', 'nurse_call', 'seizure', 'fall_prediction'].includes(msg.event_type)
    if (isCritical) {
      state.monitorBedId = msg.bed_id
      state.monitorEventType = msg.event_type
      state.monitorConfidence = msg.confidence || 0.9
      state.monitorVisible = true
    }

    loadWards()
    loadStats()
    bumpCharts()
  } else if (msg.type === 'event_ack') {
    const evt = state.events.find((e) => e.event_id === msg.event_id)
    if (evt) evt.state = ACK_STATE_MAP[msg.action] || evt.state
    loadWards()
    loadStats()
    bumpCharts()
  } else if (msg.type === 'event_update') {
    // 云端研判回写：更新事件列表中的 details.cloud_inference 与状态
    const evt = state.events.find((e) => e.event_id === msg.event_id)
    if (evt) {
      evt.state = msg.state || evt.state
      if (msg.cloud_inference) {
        evt.details = { ...(evt.details || {}), cloud_inference: msg.cloud_inference }
      }
    }
    loadWards()
    loadStats()
    bumpCharts()
  } else if (msg.type === 'node_health') {
    loadStats()
    loadWards()
    loadNodes()
    bumpCharts()
  } else if (msg.type === 'shift_summary') {
    loadShiftSummaries()
    bumpCharts()
  }
}

const onWsStatusChange = (status, info) => {
  state.wsStatus = {
    status,
    reconnectCount: info.reconnectCount,
    connectedAt: info.connectedAt,
    disconnectedAt: info.disconnectedAt,
    messageCount: info.messageCount,
  }
}

// ---- 生命周期 ----
let clockTimer = null
let statsTimer = null

const start = () => {
  if (state.started) return
  state.started = true

  loadWards()
  loadEvents()
  loadStats()
  loadShiftSummaries()
  loadNodes()

  ws.connect()
  ws.onMessage(onWsMessage)
  ws.onStatusChange(onWsStatusChange)

  clockTimer = setInterval(() => {
    state.currentTime = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  }, 1000)
  // 统计数据每 5 秒轮询一次；实时告警由 WebSocket 推送。
  statsTimer = setInterval(loadStats, 5000)
}

const stop = () => {
  if (clockTimer) clearInterval(clockTimer)
  if (statsTimer) clearInterval(statsTimer)
  ws.disconnect()
  state.started = false
}

export function useWardStore() {
  return {
    state,
    detailEvent,
    loadWards,
    loadEvents,
    loadNodes,
    loadStats,
    loadShiftSummaries,
    onAck,
    onGenerateSummary,
    onDeleteSummary,
    openMonitor,
    openMonitorFromEvent,
    openDetail,
    start,
    stop,
  }
}
