<template>
  <div class="nurse-station h-screen flex flex-col bg-med-bg overflow-hidden">
    <!-- Topbar Component -->
    <TopBar :stats="stats" :currentTime="currentTime" @open-model="modelVisible = true" />

    <!-- Main Dashboard Body -->
    <main class="body flex-1 grid gap-3 p-3 min-h-0" style="grid-template-columns: 1.55fr 1.15fr 1.15fr; overflow: hidden;">
      <!-- Column 1: Ward Beds Grid + Node Latency ECharts Chart -->
      <section class="clinical-panel bg-med-surface border border-med-border rounded-lg p-3.5 overflow-hidden flex flex-col min-h-0 shadow-card">
        <!-- Beds list scrollable container -->
        <div class="flex-1 overflow-y-auto pr-1 min-h-0">
          <WardCard v-for="ward in wards" :key="ward.id" :ward="ward" @show-monitor="openMonitor" />
        </div>

        <div class="panel-divider h-px bg-med-border my-2 flex-shrink-0"></div>

        <!-- Node Latency 看板 -->
        <NodeLatencyChart ref="nodeLatencyChartRef" class="flex-shrink-0" />
      </section>

      <!-- Column 2: Event Workstation Panel -->
      <section class="clinical-panel bg-med-surface border border-med-border rounded-lg p-3.5 overflow-hidden flex flex-col min-h-0 shadow-card">
        <EventPanel :events="events" @ack="onAck" @show-monitor="openMonitorFromEvent" class="flex-1 min-h-0" />
      </section>

      <!-- Column 3: Handover Shift Panel + 24h Event Trend ECharts Chart -->
      <section class="clinical-panel bg-med-surface border border-med-border rounded-lg p-3.5 overflow-hidden flex flex-col min-h-0 shadow-card">
        <ShiftPanel
          :shiftSummaries="shiftSummaries"
          :generating="generating"
          v-model:shiftDate="shiftDate"
          v-model:shiftPeriod="shiftPeriod"
          @generate="onGenerateSummary"
          class="flex-1 min-h-0"
        />

        <div class="panel-divider h-px bg-med-border my-2 flex-shrink-0"></div>

        <!-- Event Trend 折线图/饼图看板 -->
        <EventTrendChart ref="eventTrendChartRef" class="flex-shrink-0" />
      </section>
    </main>

    <!-- Footer -->
    <footer class="footer text-center py-2.5 text-[11px] text-med-text-3 border-t border-med-border bg-med-bg">
      第一人民医院 · 呼吸与危重症医学科 (W-01病区) 智慧病房中央护理工作站 v0.3.0
    </footer>

    <!-- Live Monitor Float Screen Component -->
    <LiveMonitor 
      :visible="monitorVisible" 
      :bedId="monitorBedId" 
      :eventType="monitorEventType"
      :confidence="monitorConfidence"
      @close="monitorVisible = false" 
    />

    <!-- Floating Debug Scene Injector Console -->
    <SceneInjector />

    <!-- Model Management Modal -->
    <ModelManage :visible="modelVisible" @close="modelVisible = false" />

    <!-- Environment Control Panel (bottom-right floating) -->
    <div class="fixed bottom-16 right-4 z-30 w-[220px] shadow-lg rounded-lg bg-white/90 backdrop-blur border border-med-border">
      <EnvControlPanel />
    </div>
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

// State variables
const wards = ref([])
const events = ref([])
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

// Component refs for chart trigger reloading
const eventTrendChartRef = ref(null)
const nodeLatencyChartRef = ref(null)

let timer = null

// Double insurance alert audio player (mp3 + Web Audio synthesizer fallback)
const playBeep = () => {
  try {
    const audio = new Audio('/alert.mp3')
    audio.play().catch(() => {
      // Fallback: Web Audio API synthesis if file is not found or blocked by browser policies
      const AudioCtx = window.AudioContext || window.webkitAudioContext
      if (!AudioCtx) return
      const ctx = new AudioCtx()
      
      // Dual-tone siren beep
      const playTone = (freq, duration, startOffset) => {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.connect(gain)
        gain.connect(ctx.destination)
        
        osc.type = 'sine'
        osc.frequency.setValueAtTime(freq, ctx.currentTime + startOffset)
        
        gain.gain.setValueAtTime(0.3, ctx.currentTime + startOffset)
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + startOffset + duration - 0.05)
        
        osc.start(ctx.currentTime + startOffset)
        osc.stop(ctx.currentTime + startOffset + duration)
      }
      
      playTone(880, 0.2, 0.0)    // High tone
      playTone(660, 0.25, 0.25)  // Low tone
    })
  } catch (err) {
    console.error('Failed to trigger alert sound', err)
  }
}

// Data loaders
const loadWards = async () => {
  try {
    const res = await api.getWards()
    wards.value = res.data.data || []
  } catch (e) {
    console.error('加载病区失败', e)
  }
}

const loadEvents = async () => {
  try {
    const res = await api.getEvents({ hours: 24, limit: 50 })
    events.value = res.data.data || []
  } catch (e) {
    console.error('加载事件失败', e)
  }
}

const loadStats = async () => {
  try {
    const res = await api.getStats()
    stats.value = res.data.data || {}
  } catch (e) {
    console.error('加载统计失败', e)
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

// WebSocket message handler with immediate reload trigger
const onWsMessage = (msg) => {
  if (msg.type === 'safety_event') {
    // Add new event to top of events workstation list
    events.value.unshift({
      event_id: msg.event_id,
      event_type: msg.event_type,
      priority: msg.priority,
      state: msg.state,
      confidence: msg.confidence,
      bed_id: msg.bed_id,
      occurred_at: msg.occurred_at,
    })
    
    // Enforce 50 items limit
    if (events.value.length > 50) {
      events.value.pop()
    }
    
    // Audio alert warning for incoming P1 events
    const isCritical = msg.priority === 'P1' || ['fall_suspected', 'nurse_call', 'seizure', 'fall_prediction'].includes(msg.event_type)
    if (isCritical) {
      playBeep()
      
      // Auto-open live monitor for this P1 emergency event to show camera feed
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
    nodeLatencyChartRef.value?.fetchData()
  } else if (msg.type === 'shift_summary') {
    loadShiftSummaries()
    eventTrendChartRef.value?.fetchData()
  }
}

// Lifecycle Hooks
onMounted(() => {
  loadWards()
  loadEvents()
  loadStats()
  loadShiftSummaries()
  
  ws.connect()
  ws.onMessage(onWsMessage)
  
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

