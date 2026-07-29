<template>
  <div class="nurse-station">
    <!-- Topbar Component -->
    <TopBar :stats="stats" :currentTime="currentTime" />

    <!-- Main Dashboard Body -->
    <main class="body">
      <!-- Column 1: Ward Beds Grid + Node Latency ECharts Chart -->
      <section class="wards-panel">
        <h2>病区床位</h2>
        
        <!-- Skeleton Loader / Empty State -->
        <div v-if="wards.length === 0" class="skeleton-grid">
          <div v-for="i in 3" :key="i" class="skeleton-card">
            <div class="skeleton-bar title"></div>
            <div class="skeleton-beds">
              <div v-for="j in 4" :key="j" class="skeleton-bed"></div>
            </div>
            <div class="skeleton-bar footer-meta"></div>
          </div>
        </div>
        
        <div v-else class="bed-grid">
          <WardCard v-for="ward in wards" :key="ward.id" :ward="ward" />
        </div>

        <div class="panel-divider"></div>

        <!-- Node Latency 看板 -->
        <NodeLatencyChart ref="nodeLatencyChartRef" />
      </section>

      <!-- Column 2: Event Workstation Panel -->
      <section class="events-panel">
        <EventPanel :events="events" @ack="onAck" />
      </section>

      <!-- Column 3: Handover Shift Panel + 24h Event Trend ECharts Chart -->
      <section class="shift-panel">
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
      智慧病房云边协同系统 · 框架骨架 v0.1 · 演示阶段数据均为模拟
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
  }, 5000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  ws.disconnect()
})
</script>

<style>
/* Global Reset and Styles */
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #0f1b2d;
  color: #e0e6ed;
  overflow-x: hidden;
}

.nurse-station {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Scrollbars */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: #152238;
}
::-webkit-scrollbar-thumb {
  background: #2a3f5f;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #3e5c8a;
}

/* Header TopBar */
.topbar {
  background: #1a2942;
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #2a3f5f;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
}
.title {
  font-size: 18px;
  font-weight: 600;
  color: #4fc3f7;
  text-shadow: 0 0 10px rgba(79, 195, 247, 0.2);
}
.metrics {
  display: flex;
  gap: 12px;
  font-size: 13px;
}
.metric {
  padding: 4px 10px;
  background: #243449;
  border-radius: 4px;
  border: 1px solid #2a3f5f;
}
.metric.alert {
  background: #5a2a2a;
  color: #ff9a9a;
  border-color: #f44336;
}
.metric.p1 {
  background: #6b1f1f;
  color: #ffb3b3;
  border-color: #f44336;
  animation: blink 1s infinite;
}

/* Keyframes for Blink animation */
@keyframes blink {
  50% { opacity: 0.4; }
}

@keyframes blink-bg {
  0%, 100% { background: #2d4055; box-shadow: none; }
  50% { background: #6b1f1f; box-shadow: 0 0 12px rgba(244, 67, 54, 0.6); }
}

@keyframes blink-border {
  50% { border-left-color: transparent; box-shadow: 0 0 10px rgba(244, 67, 54, 0.4); }
}

/* Main Layout Grid */
.body {
  flex: 1;
  display: grid;
  grid-template-columns: 1.5fr 1.1fr 1.1fr;
  gap: 12px;
  padding: 12px;
  height: calc(100vh - 84px);
  overflow: hidden;
}
.wards-panel, .events-panel, .shift-panel {
  background: #1a2942;
  border-radius: 8px;
  padding: 16px;
  overflow-y: auto;
  border: 1px solid #2a3f5f;
  display: flex;
  flex-direction: column;
}
h2 {
  font-size: 15px;
  color: #4fc3f7;
  margin-bottom: 12px;
  font-weight: 600;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-divider {
  height: 1px;
  background: #2a3f5f;
  margin: 16px 0 12px 0;
}

.count {
  color: #ff9a9a;
  background: #3e2723;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
}

.empty {
  color: #6a7a8a;
  text-align: center;
  padding: 30px 10px;
  font-size: 13px;
}

/* Skeleton Screens */
.skeleton-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.skeleton-card {
  background: #243449;
  border-radius: 6px;
  padding: 12px;
  border: 1px solid #2a3f5f;
}
.skeleton-bar {
  background: linear-gradient(90deg, #2a3f5f 25%, #3e5c8a 37%, #2a3f5f 63%);
  background-size: 400% 100%;
  animation: skeleton-loading 1.4s ease infinite;
  border-radius: 3px;
}
.skeleton-bar.title {
  width: 40%;
  height: 14px;
  margin-bottom: 12px;
}
.skeleton-bar.footer-meta {
  width: 90%;
  height: 11px;
  margin-top: 10px;
}
.skeleton-beds {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.skeleton-bed {
  height: 50px;
  background: linear-gradient(90deg, #2d4055 25%, #3a4f64 37%, #2d4055 63%);
  background-size: 400% 100%;
  animation: skeleton-loading 1.4s ease infinite;
  border-radius: 4px;
}

@keyframes skeleton-loading {
  0% { background-position: 100% 0; }
  100% { background-position: 0% 0; }
}

/* Beds Panel styling */
.bed-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ward-card {
  background: #243449;
  border-radius: 6px;
  padding: 12px;
  border: 1px solid #2a3f5f;
}
.ward-header {
  font-weight: 600;
  margin-bottom: 10px;
  font-size: 13px;
  color: #e0e6ed;
}
.beds {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
  gap: 8px;
}

/* Individual Bed Card */
.bed-card {
  background: #2d4055;
  border-radius: 4px;
  padding: 8px 4px;
  text-align: center;
  border: 1px solid #3a4f64;
  transition: all 0.25s ease;
  position: relative;
  overflow: hidden;
}
.bed-card:hover {
  transform: translateY(-2px);
  border-color: #4fc3f7;
}
.bed-card.occupied {
  border-left: 3px solid #4caf50;
}
.bed-card.maintenance {
  border-left: 3px solid #ff9800;
  opacity: 0.8;
}
.bed-card.idle {
  border-left: 3px solid #8a9aaa;
  opacity: 0.65;
}
/* Trigger alarm blinking red background if alert */
.bed-card.alert {
  animation: blink-bg 1.5s infinite;
  border-left: 3px solid #f44336 !important;
  color: #fff;
  opacity: 1;
}

.bed-name {
  font-size: 13px;
  font-weight: bold;
}
.bed-alias {
  font-size: 10px;
  color: #b0c4de;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bed-status {
  font-size: 10px;
  color: #8a9aaa;
  margin-top: 2px;
}
.bed-card.alert .bed-status {
  color: #ffa4a4;
}
.bed-pending {
  font-size: 9px;
  color: #ff8a80;
  margin-top: 3px;
  font-weight: 600;
}
.ward-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #8a9aaa;
  margin-top: 10px;
  border-top: 1px solid #2a3f5f;
  padding-top: 8px;
}

/* Event List Styling */
.event-list {
  list-style: none;
}
.event-item {
  background: #243449;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 8px;
  border-left: 3.5px solid #4caf50;
  border: 1px solid #2a3f5f;
  border-left-width: 3.5px;
  transition: all 0.25s ease;
}
.event-item.P1 {
  border-left-color: #f44336;
}
.event-item.P1.blink {
  animation: blink-border 1.2s infinite;
}
.event-item.P2 {
  border-left-color: #ff9800;
}
.event-item.P3 {
  border-left-color: #2196f3;
}
.event-item.resolved, .event-item.false_positive {
  opacity: 0.5;
  border-left-color: #78909c;
}
.event-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.badge {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: bold;
}
.badge.P1 { background: #d32f2f; color: #fff; }
.badge.P2 { background: #f57c00; color: #fff; }
.badge.P3 { background: #1976d2; color: #fff; }

.event-type {
  font-weight: 600;
  font-size: 12px;
  color: #e0e6ed;
}
.state {
  margin-left: auto;
  font-size: 10px;
  color: #8a9aaa;
  background: #152238;
  padding: 1px 6px;
  border-radius: 3px;
}
.event-meta {
  font-size: 11px;
  color: #8a9aaa;
}
.event-actions {
  margin-top: 8px;
  display: flex;
  gap: 4px;
}
.event-actions button {
  flex: 1;
  padding: 5px;
  background: #2d4055;
  color: #e0e6ed;
  border: 1px solid #3a4f64;
  border-radius: 3px;
  cursor: pointer;
  font-size: 11px;
  transition: all 0.2s ease;
}
.event-actions button:hover {
  background: #3a4f64;
  border-color: #8a9aaa;
}
.event-actions button.btn-ack {
  background: #1b3d2b;
  border-color: #2e7d32;
  color: #81c784;
}
.event-actions button.btn-ack:hover {
  background: #2e7d32;
  color: #fff;
}
.event-actions button.btn-resolve {
  background: #2d4055;
}
.event-actions button.btn-resolve:hover {
  background: #1976d2;
  border-color: #1976d2;
  color: #fff;
}

/* Shift Handovers Panel styling */
.shift-form {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
}
.shift-input {
  background: #243449;
  color: #e0e6ed;
  border: 1px solid #3a4f64;
  border-radius: 3px;
  padding: 5px 6px;
  font-size: 11px;
  outline: none;
}
.shift-form button {
  padding: 5px 12px;
  background: #2e75b6;
  color: #fff;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
}
.shift-form button:hover {
  background: #245d91;
}
.shift-form button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.summary-list {
  list-style: none;
}
.summary-item {
  background: #243449;
  border-radius: 4px;
  padding: 10px;
  margin-bottom: 8px;
  border-left: 3.5px solid #4fc3f7;
  border: 1px solid #2a3f5f;
  border-left-width: 3.5px;
}
.summary-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}
.summary-date {
  font-size: 11px;
  font-weight: bold;
  color: #4fc3f7;
}
.summary-counts {
  font-size: 10px;
  color: #8a9aaa;
  background: #1a2942;
  padding: 1px 6px;
  border-radius: 8px;
}
.summary-text {
  font-size: 11.5px;
  line-height: 1.5;
  color: #d0d6dd;
  margin-bottom: 6px;
  word-break: break-all;
}
.summary-meta {
  font-size: 10px;
  color: #8a9aaa;
  border-top: 1px dashed #3a4f64;
  padding-top: 6px;
  margin-top: 4px;
}

/* Footer styling */
.footer {
  text-align: center;
  padding: 12px;
  font-size: 12px;
  color: #6a7a8a;
  border-top: 1px solid #2a3f5f;
  background: #101a2c;
}
</style>
