<template>
  <div class="nurse-station">
    <!-- Topbar Component -->
    <TopBar :stats="stats" :currentTime="currentTime" />

    <!-- Main Dashboard Body -->
    <main class="body">
      <!-- Column 1: Ward Beds Grid + Node Latency ECharts Chart -->
      <section class="wards-panel clinical-panel">
        <WardCard v-for="ward in wards" :key="ward.id" :ward="ward" />

        <div class="panel-divider"></div>

        <!-- Node Latency 看板 -->
        <NodeLatencyChart ref="nodeLatencyChartRef" />
      </section>

      <!-- Column 2: Event Workstation Panel -->
      <section class="events-panel clinical-panel">
        <EventPanel :events="events" @ack="onAck" />
      </section>

      <!-- Column 3: Handover Shift Panel + 24h Event Trend ECharts Chart -->
      <section class="shift-panel clinical-panel">
        <ShiftPanel
          :shiftSummaries="shiftSummaries"
          :generating="generating"
          v-model:shiftDate="shiftDate"
          v-model:shiftPeriod="shiftPeriod"
          @generate="onGenerateSummary"
        />

        <div class="panel-divider"></div>

        <!-- Event Trend 折线图/饼图看板 -->
        <EventTrendChart ref="eventTrendChartRef" />
      </section>
    </main>

    <!-- Footer -->
    <footer class="footer">
      第一人民医院 · 呼吸与危重症医学科 (W-01病区) 智慧病房中央护理工作站 v0.3.0
    </footer>

    <!-- Floating Debug Scene Injector Console -->
    <SceneInjector />
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

// State variables
const wards = ref([])
const events = ref([])
const stats = ref({})
const currentTime = ref('')
const shiftSummaries = ref([])
const shiftDate = ref(new Date().toISOString().slice(0, 10))
const shiftPeriod = ref('day')
const generating = ref(false)

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
    if (msg.priority === 'P1' || ['fall_suspected', 'nurse_call', 'seizure', 'fall_prediction'].includes(msg.event_type)) {
      playBeep()
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

<style>
/* Clinical Reset and Styles */
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #0b172a;
  color: #e2e8f0;
  overflow-x: hidden;
}

.nurse-station {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Scrollbars */
::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}
::-webkit-scrollbar-track {
  background: #0b172a;
}
::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #475569;
}

/* Main Layout Grid */
.body {
  flex: 1;
  display: grid;
  grid-template-columns: 1.55fr 1.15fr 1.15fr;
  gap: 12px;
  padding: 12px;
  height: calc(100vh - 84px);
  overflow: hidden;
}

.clinical-panel {
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 8px;
  padding: 14px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.panel-divider {
  height: 1px;
  background: #1e293b;
  margin: 14px 0;
}

/* Footer styling */
.footer {
  text-align: center;
  padding: 10px;
  font-size: 11px;
  color: #64748b;
  border-top: 1px solid #1e293b;
  background: #0b172a;
}
</style>
