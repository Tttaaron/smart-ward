<template>
  <div class="nurse-station">
    <!-- Topbar Component -->
    <TopBar :stats="stats" :currentTime="currentTime" />

    <!-- Main Dashboard Body -->
    <main class="body">
      <!-- Column 1: Ward Beds Grid + Node Latency ECharts Chart -->
      <section class="wards-panel glass-panel">
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
      <section class="events-panel glass-panel">
        <EventPanel :events="events" @ack="onAck" />
      </section>

      <!-- Column 3: Handover Shift Panel + 24h Event Trend ECharts Chart -->
      <section class="shift-panel glass-panel">
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
  font-family: 'Outfit', 'Inter', -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: radial-gradient(circle at 50% 50%, #162642 0%, #080d1a 100%);
  color: #e2e8f0;
  overflow-x: hidden;
  letter-spacing: 0.5px;
}

.nurse-station {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Custom Tech Scrollbars */
::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}
::-webkit-scrollbar-track {
  background: rgba(8, 15, 30, 0.3);
}
::-webkit-scrollbar-thumb {
  background: rgba(79, 195, 247, 0.2);
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(79, 195, 247, 0.5);
}

/* Glassmorphism Panel Base */
.glass-panel {
  background: rgba(16, 26, 48, 0.55);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.35);
  border-radius: 12px;
  padding: 18px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.glass-panel:hover {
  border-color: rgba(79, 195, 247, 0.15);
  box-shadow: 0 12px 40px rgba(79, 195, 247, 0.05);
}

/* Header TopBar */
.topbar {
  background: rgba(16, 26, 48, 0.7);
  backdrop-filter: blur(10px);
  padding: 14px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
  z-index: 10;
}
.title {
  font-size: 20px;
  font-weight: 700;
  color: #4fc3f7;
  letter-spacing: 1px;
  text-shadow: 0 0 12px rgba(79, 195, 247, 0.35);
}
.metrics {
  display: flex;
  gap: 12px;
  font-size: 12px;
}
.metric {
  padding: 5px 12px;
  background: rgba(36, 52, 73, 0.5);
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  color: #b0c4de;
  font-weight: 500;
}
.metric.alert {
  background: rgba(239, 68, 68, 0.2);
  color: #ff9e9e;
  border-color: rgba(239, 68, 68, 0.4);
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.2);
}
.metric.p1 {
  background: rgba(239, 68, 68, 0.35);
  color: #fff;
  border-color: #ef4444;
  font-weight: 600;
  animation: blink 1.2s infinite;
}

/* Keyframes for Blink animations */
@keyframes blink {
  50% { opacity: 0.5; }
}

@keyframes blink-bg {
  0%, 100% { 
    background: rgba(26, 38, 57, 0.4);
    border-color: rgba(239, 68, 68, 0.25);
    box-shadow: none; 
  }
  50% { 
    background: rgba(239, 68, 68, 0.2); 
    border-color: #ef4444;
    box-shadow: 0 0 15px rgba(239, 68, 68, 0.45); 
  }
}

@keyframes blink-border {
  50% { 
    border-left-color: transparent; 
    box-shadow: 0 0 15px rgba(239, 68, 68, 0.35); 
  }
}

/* Main Layout Grid */
.body {
  flex: 1;
  display: grid;
  grid-template-columns: 1.45fr 1.15fr 1.15fr;
  gap: 14px;
  padding: 14px;
  height: calc(100vh - 90px);
  overflow: hidden;
}

h2 {
  font-size: 16px;
  color: #4fc3f7;
  margin-bottom: 14px;
  font-weight: 700;
  display: flex;
  justify-content: space-between;
  align-items: center;
  letter-spacing: 0.8px;
}

.panel-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.08), transparent);
  margin: 18px 0 14px 0;
}

.count {
  color: #ff9e9e;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.25);
  padding: 2px 9px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}

.empty {
  color: #5a6e85;
  text-align: center;
  padding: 40px 10px;
  font-size: 13px;
}

/* Skeleton Screens */
.skeleton-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.skeleton-card {
  background: rgba(36, 52, 73, 0.3);
  border-radius: 8px;
  padding: 14px;
  border: 1px solid rgba(255, 255, 255, 0.03);
}
.skeleton-bar {
  background: linear-gradient(90deg, rgba(255,255,255,0.03) 25%, rgba(255,255,255,0.08) 37%, rgba(255,255,255,0.03) 63%);
  background-size: 400% 100%;
  animation: skeleton-loading 1.4s ease infinite;
  border-radius: 4px;
}
.skeleton-bar.title {
  width: 35%;
  height: 14px;
  margin-bottom: 14px;
}
.skeleton-bar.footer-meta {
  width: 80%;
  height: 10px;
  margin-top: 12px;
}
.skeleton-beds {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.skeleton-bed {
  height: 52px;
  background: linear-gradient(90deg, rgba(255,255,255,0.02) 25%, rgba(255,255,255,0.06) 37%, rgba(255,255,255,0.02) 63%);
  background-size: 400% 100%;
  animation: skeleton-loading 1.4s ease infinite;
  border-radius: 6px;
}

@keyframes skeleton-loading {
  0% { background-position: 100% 0; }
  100% { background-position: 0% 0; }
}

/* Beds Grid layouts */
.bed-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.ward-card {
  background: rgba(30, 41, 59, 0.35);
  border-radius: 8px;
  padding: 14px;
  border: 1px solid rgba(255, 255, 255, 0.04);
}
.ward-header {
  font-weight: 600;
  margin-bottom: 12px;
  font-size: 13px;
  color: #94a3b8;
  border-left: 3px solid #4fc3f7;
  padding-left: 8px;
}
.beds {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(95px, 1fr));
  gap: 8px;
}

/* Individual Bed Card Premium Styling */
.bed-card {
  background: rgba(26, 38, 57, 0.4);
  border-radius: 6px;
  padding: 9px 4px;
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.05);
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  cursor: pointer;
}
.bed-card:hover {
  transform: translateY(-3px) scale(1.02);
  border-color: rgba(79, 195, 247, 0.35);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3);
  background: rgba(36, 52, 73, 0.5);
}
.bed-card.occupied {
  border-left: 3.5px solid #10b981;
}
.bed-card.maintenance {
  border-left: 3.5px solid #f59e0b;
  opacity: 0.8;
}
.bed-card.idle {
  border-left: 3.5px solid #64748b;
  opacity: 0.65;
}
/* Trigger alarm blinking red background if alert */
.bed-card.alert {
  animation: blink-bg 1.5s infinite;
  border-left: 3.5px solid #ef4444 !important;
  color: #fff;
  opacity: 1;
}

.bed-name {
  font-size: 13px;
  font-weight: 700;
  color: #f8fafc;
}
.bed-alias {
  font-size: 10px;
  color: #94a3b8;
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}
.bed-status {
  font-size: 10px;
  color: #64748b;
  margin-top: 2px;
}
.bed-card.occupied .bed-status {
  color: #10b981;
}
.bed-card.maintenance .bed-status {
  color: #f59e0b;
}
.bed-card.alert .bed-status {
  color: #ff8a80;
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
  color: #64748b;
  margin-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  padding-top: 10px;
}

/* Event List Styling */
.event-list {
  list-style: none;
}
.event-item {
  background: rgba(30, 41, 59, 0.25);
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 10px;
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-left: 3.5px solid #10b981;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.event-item:hover {
  transform: translateY(-2px);
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(30, 41, 59, 0.4);
}
.event-item.P1 {
  border-left-color: #ef4444;
}
.event-item.P1.blink {
  animation: blink-border 1.2s infinite;
}
.event-item.P2 {
  border-left-color: #f59e0b;
}
.event-item.P3 {
  border-left-color: #3b82f6;
}
.event-item.resolved, .event-item.false_positive {
  opacity: 0.5;
  border-left-color: #64748b;
}
.event-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.badge {
  padding: 1px 7px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.badge.P1 { background: rgba(239, 68, 68, 0.2); color: #ff8a80; border: 1px solid rgba(239, 68, 68, 0.3); }
.badge.P2 { background: rgba(245, 158, 11, 0.15); color: #ffd180; border: 1px solid rgba(245, 158, 11, 0.25); }
.badge.P3 { background: rgba(59, 130, 246, 0.15); color: #80d8ff; border: 1px solid rgba(59, 130, 246, 0.25); }

.event-type {
  font-weight: 600;
  font-size: 13px;
  color: #f1f5f9;
}
.state {
  margin-left: auto;
  font-size: 10px;
  color: #94a3b8;
  background: rgba(15, 23, 42, 0.4);
  padding: 2px 8px;
  border-radius: 10px;
  border: 1px solid rgba(255,255,255,0.03);
}
.event-meta {
  font-size: 11px;
  color: #64748b;
  font-weight: 500;
}
.event-actions {
  margin-top: 10px;
  display: flex;
  gap: 6px;
}
.event-actions button {
  flex: 1;
  padding: 6px;
  background: rgba(30, 41, 59, 0.6);
  color: #cbd5e1;
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  transition: all 0.2s ease;
}
.event-actions button:hover {
  background: rgba(79, 195, 247, 0.1);
  border-color: rgba(79, 195, 247, 0.35);
  color: #4fc3f7;
}
.event-actions button.btn-ack {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.25);
  color: #34d399;
}
.event-actions button.btn-ack:hover {
  background: #10b981;
  color: #fff;
  border-color: #10b981;
  box-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
}
.event-actions button.btn-resolve:hover {
  background: #3b82f6;
  border-color: #3b82f6;
  color: #fff;
  box-shadow: 0 0 10px rgba(59, 130, 246, 0.3);
}

/* Shift Handovers Panel styling */
.shift-form {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.shift-input {
  background: rgba(15, 23, 42, 0.45);
  color: #f1f5f9;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 4px;
  padding: 6px 10px;
  font-size: 12px;
  outline: none;
  font-family: inherit;
  transition: all 0.2s ease;
}
.shift-input:focus {
  border-color: rgba(79, 195, 247, 0.4);
  box-shadow: 0 0 8px rgba(79, 195, 247, 0.15);
}
.shift-form button {
  padding: 6px 14px;
  background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.25s ease;
  box-shadow: 0 4px 10px rgba(30, 64, 175, 0.2);
}
.shift-form button:hover:not(:disabled) {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
  transform: translateY(-1px);
}
.shift-form button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.summary-list {
  list-style: none;
}
.summary-item {
  background: rgba(30, 41, 59, 0.2);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 8px;
  border: 1px solid rgba(255, 255, 255, 0.03);
  border-left: 3.5px solid #38bdf8;
}
.summary-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}
.summary-date {
  font-size: 12px;
  font-weight: 700;
  color: #38bdf8;
}
.summary-counts {
  font-size: 10px;
  color: #94a3b8;
  background: rgba(15, 23, 42, 0.4);
  padding: 2px 8px;
  border-radius: 10px;
}
.summary-text {
  font-size: 12px;
  line-height: 1.6;
  color: #cbd5e1;
  margin-bottom: 8px;
  word-break: break-all;
}
.summary-meta {
  font-size: 10.5px;
  color: #64748b;
  border-top: 1px dashed rgba(255, 255, 255, 0.06);
  padding-top: 8px;
  margin-top: 6px;
}

/* Footer styling */
.footer {
  text-align: center;
  padding: 14px;
  font-size: 11px;
  color: #5a6e85;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(8, 13, 26, 0.8);
  backdrop-filter: blur(10px);
}
</style>
