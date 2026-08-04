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
    />

    <!-- Main Dashboard Body -->
    <main class="body flex-1 grid gap-3 p-3 min-h-0" style="grid-template-columns: 1.55fr 1.15fr 1.15fr; overflow: hidden;">
      <!-- Column 1: Ward Beds Grid + Node Latency ECharts Chart -->
      <section class="clinical-panel bg-med-surface border border-med-border rounded-lg p-3.5 overflow-hidden flex flex-col min-h-0 shadow-card">
        <!-- Beds list scrollable container -->
        <div class="flex-1 overflow-y-auto pr-1 min-h-0">
          <WardCard
            v-for="ward in wards"
            :key="ward.id"
            :ward="ward"
            :events="events"
            @show-monitor="openMonitor"
          />
        </div>

        <div class="panel-divider h-px bg-med-border my-2 flex-shrink-0"></div>

        <!-- Node Latency 看板 -->
        <NodeLatencyChart ref="nodeLatencyChartRef" class="flex-shrink-0" />

        <div class="panel-divider h-px bg-med-border my-2 flex-shrink-0"></div>

        <!-- 环境联动控制 -->
        <EnvControlPanel class="flex-shrink-0" />
      </section>

      <!-- Column 2: Event Workstation Panel -->
      <section class="clinical-panel bg-med-surface border border-med-border rounded-lg p-3.5 overflow-hidden flex flex-col min-h-0 shadow-card">
        <EventPanel
          :events="events"
          @ack="onAck"
          @show-monitor="openMonitorFromEvent"
          @open-detail="openDetail"
          class="flex-1 min-h-0"
        />
      </section>

      <!-- Column 3: Handover Shift Panel + 24h Event Trend ECharts Chart -->
      <section class="clinical-panel bg-med-surface border border-med-border rounded-lg p-3.5 overflow-hidden flex flex-col min-h-0 shadow-card">
        <ShiftPanel
          :shiftSummaries="shiftSummaries"
          :generating="generating"
          v-model:shiftDate="shiftDate"
          v-model:shiftPeriod="shiftPeriod"
          @generate="onGenerateSummary"
          @delete-summary="onDeleteSummary"
          class="flex-1 min-h-0"
        />

        <div class="panel-divider h-px bg-med-border my-2 flex-shrink-0"></div>

        <!-- Event Trend 折线图/饼图看板 -->
        <EventTrendChart ref="eventTrendChartRef" class="flex-shrink-0" />
      </section>
    </main>

    <!-- Footer -->
    <footer class="footer text-center py-2.5 text-[11px] text-med-text-3 border-t border-med-border bg-med-bg">
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
      @close="detailVisible = false"
    />

    <!-- Floating Debug Scene Injector Console -->
    <SceneInjector />

    <!-- Model Management Modal -->
    <ModelManage :visible="modelVisible" @close="modelVisible = false" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
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

// State variables
const wards = ref([])
const events = ref([])
const nodes = ref([])
const stats = ref({})
const currentTime = ref('')
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

// Network / cloud observability state
const wsStatus = ref({
  status: 'disconnected',
  reconnectCount: 0,
  connectedAt: null,
  disconnectedAt: null,
  messageCount: {},
})
const apiHealthy = ref(true)

// Component refs for chart trigger reloading
const eventTrendChartRef = ref(null)
const nodeLatencyChartRef = ref(null)

let timer = null

// Data loaders
const loadWards = async () => {
  try {
    const res = await api.getWards()
    wards.value = res.data.data || []
  } catch (e) {
    console.error('加载病区失败', e)
    apiHealthy.value = false
  }
}

const loadEvents = async () => {
  try {
    const res = await api.getEvents({ hours: 24, limit: 50 })
    events.value = res.data.data || []
  } catch (e) {
    console.error('加载事件失败', e)
    apiHealthy.value = false
  }
}

const loadNodes = async () => {
  try {
    const res = await api.getNodes('W-01')
    nodes.value = res.data.data || []
  } catch (e) {
    console.error('加载节点失败', e)
  }
}

const loadStats = async () => {
  try {
    const res = await api.getStats()
    stats.value = res.data.data || {}
    apiHealthy.value = true
  } catch (e) {
    console.error('加载统计失败', e)
    apiHealthy.value = false
  }
}

const loadShiftSummaries = async () => {
  try {
    const res = await api.getShiftSummaries({ ward_id: 'W-01', limit: 10 })
    shiftSummaries.value = res.data.data || []
  } catch (e) {
    console.error('加载摘要失败', e)
  }
}

// Actions
const onAck = async (evt, action) => {
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
    loadStats()
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  ws.disconnect()
})
</script>
