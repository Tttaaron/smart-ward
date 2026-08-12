<template>
  <div class="nurse-station h-screen flex flex-col bg-med-bg overflow-hidden">
    <!-- Topbar Component -->
    <TopBar :stats="stats" :currentTime="currentTime" @open-model="modelVisible = true" />

    <!-- 云端/网络/边缘状态栏 + 断网/恢复横幅 -->
    <SystemStatusBar
      :ws-status="wsStatus"
      :stats="stats"
      :nodes="nodes"
      :api-healthy="apiHealthy"
      :demo-mode="demoMode"
      :presentation-fallback="presentationFallback"
    />

    <!-- Main Dashboard Body -->
    <main class="body command-center flex-1 min-h-0">
      <div class="dashboard-grid">
      <!-- Column 1: Ward Beds Grid + Node Latency ECharts Chart -->
      <section class="workspace-panel ward-workspace">
        <div class="workspace-caption">
          <span class="caption-index">01</span>
          <span class="caption-title">床位态势</span>
          <span class="caption-meta">W-01 · 三楼东侧</span>
        </div>
        <!-- Beds list scrollable container -->
        <div class="ward-scroll">
          <WardCard
            v-for="ward in wards"
            :key="ward.id"
            :ward="ward"
            :events="events"
            @show-monitor="openMonitor"
          />
        </div>

        <div class="panel-divider"></div>

        <!-- Node Latency 看板 -->
        <NodeLatencyChart ref="nodeLatencyChartRef" :demo-mode="demoMode" class="node-chart" />

        <div class="panel-divider"></div>

        <!-- 环境联动控制 -->
        <EnvControlPanel class="env-panel" />
      </section>

      <!-- Column 2: Event Workstation Panel -->
      <section class="workspace-panel alert-workspace">
        <div class="workspace-caption">
          <span class="caption-index">02</span>
          <span class="caption-title">护理告警</span>
          <span class="caption-meta">优先级队列 · 实时处置</span>
        </div>
        <EventPanel
          :events="events"
          @ack="onAck"
          @show-monitor="openMonitorFromEvent"
          @open-detail="openDetail"
          class="workspace-content"
        />
      </section>

      <!-- Column 3: Handover Shift Panel + 24h Event Trend ECharts Chart -->
      <aside class="workspace-rail">
      <section class="workspace-panel handover-workspace">
        <div class="workspace-caption">
          <span class="caption-index">03</span>
          <span class="caption-title">交班摘要</span>
          <span class="caption-meta">本班次</span>
        </div>
        <ShiftPanel
          :shiftSummaries="shiftSummaries"
          :generating="generating"
          v-model:shiftDate="shiftDate"
          v-model:shiftPeriod="shiftPeriod"
          @generate="onGenerateSummary"
          @delete-summary="onDeleteSummary"
          class="workspace-content"
        />

        <div class="panel-divider"></div>

        <!-- Event Trend 折线图/饼图看板 -->
        <EventTrendChart ref="eventTrendChartRef" :demo-mode="demoMode" class="trend-chart" />
      </section>

      <!-- Column 4: 活动日志面板（对接 observation.activity） -->
      <section class="workspace-panel activity-workspace">
        <div class="workspace-caption">
          <span class="caption-index">04</span>
          <span class="caption-title">活动轨迹</span>
          <span class="caption-meta">摄像头观察</span>
        </div>
        <ActivityLogPanel class="workspace-content" />
      </section>
      </aside>
      </div>
    </main>

    <!-- Footer -->
    <footer class="footer text-center py-2 text-[11px] text-med-text-3 border-t border-med-border bg-med-bg">
      第一人民医院 · 呼吸与危重症医学科 (W-01病区) 智慧病房中央护理工作站 v0.4.0
    </footer>

    <!-- Live Monitor Float Screen Component -->
    <LiveMonitor
      :visible="monitorVisible"
      :bedId="monitorBedId"
      :eventType="monitorEventType"
      :confidence="monitorConfidence"
      @close="monitorVisible = false"
    />

    <!-- 事件详情与链路追踪抽屉 -->
    <EventDetailDrawer
      :visible="detailVisible"
      :event-id="detailEventId"
      :fallback-event="detailEvent"
      @close="detailVisible = false"
    />

    <!-- Floating Debug Scene Injector Console -->
    <SceneInjector />

    <!-- Model Management Modal -->
    <ModelManage :visible="modelVisible" :demo-mode="demoMode" @close="modelVisible = false" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from './api/index.js'
import ws from './api/websocket.js'

// Import all sub-components
import TopBar from './components/TopBar.vue'
import WardCard from './components/WardCard.vue'
import EventPanel from './components/EventPanel.vue'
import ShiftPanel from './components/ShiftPanel.vue'
import EventTrendChart from './components/EventTrendChart.vue'
import NodeLatencyChart from './components/NodeLatencyChart.vue'
import SceneInjector from './components/SceneInjector.vue'
import LiveMonitor from './components/LiveMonitor.vue'
import EnvControlPanel from './components/EnvControlPanel.vue'
import ModelManage from './components/ModelManage.vue'
import SystemStatusBar from './components/SystemStatusBar.vue'
import EventDetailDrawer from './components/EventDetailDrawer.vue'
import ActivityLogPanel from './components/ActivityLogPanel.vue'

// State variables
const wards = ref([])
const events = ref([])
const nodes = ref([])
const stats = ref({})
const currentTime = ref(new Date().toLocaleTimeString('zh-CN'))
const shiftSummaries = ref([])
const shiftDate = ref(new Date().toISOString().slice(0, 10))
const shiftPeriod = ref('day')
const generating = ref(false)

// Live Monitor OSD Panel states
const monitorVisible = ref(false)
const monitorBedId = ref('B01')
const monitorEventType = ref('fall_suspected')
const monitorConfidence = ref(0.9)

// Model management modal
const modelVisible = ref(false)

// Event detail drawer
const detailVisible = ref(false)
const detailEventId = ref('')
const detailEvent = computed(() => events.value.find((event) => event.event_id === detailEventId.value) || null)

// Network / cloud observability state
const wsStatus = ref({
  status: 'disconnected',
  reconnectCount: 0,
  connectedAt: null,
  disconnectedAt: null,
  messageCount: {},
})
const apiHealthy = ref(true)
const demoMode = ref(false)
const presentationFallback = ref(false)
const liveSources = new Set()
const preferLiveData = new URLSearchParams(window.location.search).get('live') === '1'

// Component refs for chart trigger reloading
const eventTrendChartRef = ref(null)
const nodeLatencyChartRef = ref(null)

let timer = null
let statsTimer = null

const demoTimestamp = (secondsAgo = 0) => new Date(Date.now() - secondsAgo * 1000).toISOString()

const demoWards = () => [{
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

const demoEvents = () => [
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

const demoShiftSummaries = () => [{
  id: 'demo-shift-01', shift_date: new Date().toISOString().slice(0, 10), shift_period: 'day',
  event_count: 3, p1_count: 2, p2_count: 1, resolved_count: 1, false_positive_count: 0,
  summary_text: 'B01床存在坠床风险，已提高巡视频次；B02床呼叫已到场处置。边缘节点运行稳定，未发现设备离线。',
}]

const useDemoFallback = ({ replace = false } = {}) => {
  demoMode.value = true
  if (replace || !wards.value.length) wards.value = demoWards()
  if (replace || !events.value.length) events.value = demoEvents()
  if (replace || !nodes.value.length) nodes.value = wards.value[0]?.nodes || []
  if (replace || !shiftSummaries.value.length) shiftSummaries.value = demoShiftSummaries()
  if (replace || !Object.keys(stats.value).length) {
    stats.value = {
      total_beds: 3, occupied_beds: 3, leave_beds: 1,
      online_nodes: 3, total_nodes: 3, p1_pending: 1,
      pending_events: 3, events_today: 12,
    }
  }
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

const activatePresentationFallback = () => {
  if (presentationFallback.value) return
  presentationFallback.value = true
  useDemoFallback({ replace: true })
}

const markLiveSource = (source) => {
  if (presentationFallback.value) return
  liveSources.add(source)
  if (['wards', 'events', 'nodes', 'stats', 'shifts'].every((key) => liveSources.has(key))) {
    demoMode.value = false
  }
}

// Data loaders
const loadWards = async () => {
  try {
    const res = await api.getWards()
    const nextWards = res.data.data || []
    if (hasPresentationOutliers({}, nextWards)) {
      activatePresentationFallback()
      return
    }
    if (presentationFallback.value) return
    wards.value = nextWards
    markLiveSource('wards')
  } catch (e) {
    console.error('加载病区失败', e)
    apiHealthy.value = false
    useDemoFallback()
  }
}

const loadEvents = async () => {
  try {
    const res = await api.getEvents({ hours: 24, limit: 50 })
    if (presentationFallback.value) return
    events.value = res.data.data || []
    markLiveSource('events')
  } catch (e) {
    console.error('加载事件失败', e)
    apiHealthy.value = false
    useDemoFallback()
  }
}

const loadNodes = async () => {
  try {
    const res = await api.getNodes('W-01')
    if (presentationFallback.value) return
    nodes.value = res.data.data || []
    markLiveSource('nodes')
  } catch (e) {
    console.error('加载节点失败', e)
    useDemoFallback()
  }
}

const loadStats = async () => {
  try {
    const res = await api.getStats()
    apiHealthy.value = true
    const nextStats = res.data.data || {}
    if (hasPresentationOutliers(nextStats)) {
      activatePresentationFallback()
      return
    }
    if (presentationFallback.value) return
    stats.value = nextStats
    markLiveSource('stats')
  } catch (e) {
    console.error('加载统计失败', e)
    apiHealthy.value = false
    useDemoFallback()
  }
}

const loadShiftSummaries = async () => {
  try {
    const res = await api.getShiftSummaries({ ward_id: 'W-01', limit: 10 })
    if (presentationFallback.value) return
    shiftSummaries.value = res.data.data || []
    markLiveSource('shifts')
  } catch (e) {
    console.error('加载摘要失败', e)
    useDemoFallback()
  }
}

// Actions
const onAck = async (evt, action) => {
  if (demoMode.value) {
    const demoStateMap = {
      acknowledge: 'acknowledged',
      resolve: 'resolved',
      false_positive: 'false_positive',
      escalate: 'escalated',
    }
    evt.state = demoStateMap[action] || evt.state
    return
  }
  try {
    await api.ackEvent(evt.event_id, {
      action,
      operator_id: 'nurse-demo',
      operator_name: '演示护士',
      operator_role: 'nurse',
    })

    // Optimistic local update
    const stateMap = {
      acknowledge: 'acknowledged',
      resolve: 'resolved',
      false_positive: 'false_positive',
      escalate: 'escalated',
    }
    evt.state = stateMap[action]

    // Refresh wards & stats & charts to reflect acknowledged state immediately
    loadWards()
    loadStats()
    eventTrendChartRef.value?.fetchData()
    nodeLatencyChartRef.value?.fetchData()
  } catch (e) {
    console.error('确认失败', e)
    alert('确认失败，请查看后端日志')
  }
}

const onGenerateSummary = async () => {
  generating.value = true
  try {
    if (demoMode.value) {
      shiftSummaries.value = demoShiftSummaries()
      return
    }
    await api.generateShiftSummary({
      ward_id: 'W-01',
      shift_date: shiftDate.value,
      shift_period: shiftPeriod.value,
      operator_id: 'nurse-demo',
    })
    await loadShiftSummaries()
    // Refresh trend chart in case it changed
    eventTrendChartRef.value?.fetchData()
  } catch (e) {
    console.error('生成摘要失败', e)
    alert('生成失败，请查看后端日志')
  } finally {
    generating.value = false
  }
}

const onDeleteSummary = async (summaryId) => {
  if (!confirm('确定删除该交接班摘要？')) return
  if (demoMode.value) {
    shiftSummaries.value = shiftSummaries.value.filter((summary) => summary.id !== summaryId)
    return
  }
  try {
    await api.deleteShiftSummary(summaryId)
    await loadShiftSummaries()
  } catch (e) {
    console.error('删除摘要失败', e)
    alert('删除失败')
  }
}

// Live Monitor handlers
const openMonitor = (bed) => {
  monitorBedId.value = bed.id || bed.bed_id || 'B01'
  // Find active alarm for this bed
  const activeEvent = events.value.find(
    e => e.bed_id === monitorBedId.value && ['new', 'notified', 'acknowledged'].includes(e.state)
  )
  if (activeEvent) {
    monitorEventType.value = activeEvent.event_type
    monitorConfidence.value = activeEvent.confidence || 0.90
  } else {
    // Default if clicked manually for normal bed
    monitorEventType.value = bed.status === 'alert' ? 'fall_suspected' : 'nurse_call'
    monitorConfidence.value = 0.95
  }
  monitorVisible.value = true
}

const openMonitorFromEvent = (evtData) => {
  monitorBedId.value = evtData.id || 'B01'
  monitorEventType.value = evtData.eventType || 'fall_suspected'
  monitorConfidence.value = evtData.confidence || 0.90
  monitorVisible.value = true
}

// 打开事件详情与链路追踪抽屉
const openDetail = (eventId) => {
  detailEventId.value = eventId
  detailVisible.value = true
}

// WebSocket message handler with immediate reload trigger
const onWsMessage = (msg) => {
  // 展示保护模式使用一组可控的演示事件，避免后端历史累计数据持续灌入队列。
  // ?live=1 会绕过该保护，保留完整实时通道用于联调与排障。
  if (presentationFallback.value) return

  if (msg.type === 'safety_event') {
    // Add new event to top of events workstation list（尽量保留完整字段）
    const raw = msg.data || {}
    events.value.unshift({
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

    // Enforce 50 items limit
    if (events.value.length > 50) {
      events.value.pop()
    }

    // 判定是否为 P1 紧急事件自动唤起监护画面
    const isCritical = msg.priority === 'P1' || ['fall_suspected', 'nurse_call', 'seizure', 'fall_prediction'].includes(msg.event_type)
    if (isCritical) {
      // 自动打开 live monitor 展示 camera feed
      monitorBedId.value = msg.bed_id
      monitorEventType.value = msg.event_type
      monitorConfidence.value = msg.confidence || 0.90
      monitorVisible.value = true
    }

    // Trigger reloading of statistics, beds, and graphs immediately
    loadWards()
    loadStats()
    eventTrendChartRef.value?.fetchData()
    nodeLatencyChartRef.value?.fetchData()
  } else if (msg.type === 'event_ack') {
    const evt = events.value.find(e => e.event_id === msg.event_id)
    if (evt) {
      const stateMap = {
        acknowledge: 'acknowledged',
        resolve: 'resolved',
        false_positive: 'false_positive',
        escalate: 'escalated'
      }
      evt.state = stateMap[msg.action] || evt.state
    }
    loadWards()
    loadStats()
    eventTrendChartRef.value?.fetchData()
  } else if (msg.type === 'event_update') {
    // 云端研判回写：更新事件列表中的 details.cloud_inference 与状态
    const evt = events.value.find(e => e.event_id === msg.event_id)
    if (evt) {
      evt.state = msg.state || evt.state
      if (msg.cloud_inference) {
        evt.details = {
          ...(evt.details || {}),
          cloud_inference: msg.cloud_inference,
        }
      }
    }
    loadWards()
    loadStats()
    eventTrendChartRef.value?.fetchData()
  } else if (msg.type === 'node_health') {
    loadStats()
    loadWards()
    loadNodes()
    nodeLatencyChartRef.value?.fetchData()
  } else if (msg.type === 'shift_summary') {
    loadShiftSummaries()
    eventTrendChartRef.value?.fetchData()
  }
}

// WebSocket 状态变化（用于状态栏断网/重连/恢复展示）
const onWsStatusChange = (status, info) => {
  wsStatus.value = {
    status,
    reconnectCount: info.reconnectCount,
    connectedAt: info.connectedAt,
    disconnectedAt: info.disconnectedAt,
    messageCount: info.messageCount,
  }
}

// Lifecycle Hooks
onMounted(() => {
  loadWards()
  loadEvents()
  loadStats()
  loadShiftSummaries()
  loadNodes()

  ws.connect()
  ws.onMessage(onWsMessage)
  ws.onStatusChange(onWsStatusChange)

  timer = setInterval(() => {
    currentTime.value = new Date().toLocaleTimeString('zh-CN')
  }, 1000)
  // 统计数据不需要每秒刷新，实时告警仍由 WebSocket 推送。
  statsTimer = setInterval(loadStats, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (statsTimer) clearInterval(statsTimer)
  ws.disconnect()
})
</script>
