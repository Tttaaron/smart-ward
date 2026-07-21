<template>
  <div class="nurse-station">
    <!-- 顶栏：病区概览 -->
    <header class="topbar">
      <div class="title">智慧病房 · 护士站工作台</div>
      <div class="metrics">
        <span class="metric">病区 {{ stats.total_wards || 0 }}</span>
        <span class="metric">床位 {{ stats.total_beds || 0 }}</span>
        <span class="metric" :class="{ alert: stats.online_nodes < stats.total_nodes }">
          节点 {{ stats.online_nodes || 0 }}/{{ stats.total_nodes || 0 }}
        </span>
        <span class="metric p1" v-if="stats.p1_pending > 0">
          P1 待处理 {{ stats.p1_pending }}
        </span>
        <span class="metric">{{ currentTime }}</span>
      </div>
    </header>

    <!-- 主体：左床位卡片 + 右告警工作台 -->
    <main class="body">
      <section class="wards-panel">
        <h2>病区床位</h2>
        <div v-if="wards.length === 0" class="empty">加载中...</div>
        <div v-else class="bed-grid">
          <div v-for="ward in wards" :key="ward.id" class="ward-card">
            <div class="ward-header">{{ ward.name }}（{{ ward.location }}）</div>
            <div class="beds">
              <div v-for="bed in bedOccupancy(bedId(ward, 0)) || ward.beds" :key="bed.bed_id || bed.id" class="bed-card" :class="bed.status">
                <div class="bed-name">{{ bed.name }}</div>
                <div class="bed-alias" v-if="bed.patient_alias">{{ bed.patient_alias }}</div>
                <div class="bed-status">{{ bed.status }}</div>
                <div class="bed-pending" v-if="bed.pending_events > 0">{{ bed.pending_events }} 待处理</div>
              </div>
            </div>
            <div class="ward-meta">
              <span>待处理告警 {{ ward.pending_alerts }}</span>
              <span>节点 {{ ward.nodes.length }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="events-panel">
        <h2>告警工作台 <span class="count">{{ events.length }}</span></h2>
        <div v-if="events.length === 0" class="empty">暂无事件</div>
        <ul class="event-list">
          <li v-for="evt in events" :key="evt.event_id" class="event-item" :class="[evt.priority, evt.state]">
            <div class="event-head">
              <span class="badge" :class="evt.priority">{{ evt.priority }}</span>
              <span class="event-type">{{ eventTypeLabel(evt.event_type) }}</span>
              <span class="state">{{ evt.state }}</span>
            </div>
            <div class="event-meta">
              {{ evt.bed_id }} · 置信度 {{ (evt.confidence * 100).toFixed(0) }}% · {{ formatTime(evt.occurred_at) }}
            </div>
            <div class="event-actions" v-if="['new', 'notified', 'acknowledged'].includes(evt.state)">
              <button @click="onAck(evt, 'acknowledge')">到场</button>
              <button @click="onAck(evt, 'resolve')">处置</button>
              <button @click="onAck(evt, 'false_positive')">误报</button>
              <button @click="onAck(evt, 'escalate')">升级</button>
            </div>
          </li>
        </ul>
      </section>

      <section class="shift-panel">
        <h2>交接班摘要</h2>
        <div class="shift-form">
          <input v-model="shiftDate" type="date" class="shift-input" />
          <select v-model="shiftPeriod" class="shift-input">
            <option value="day">白班</option>
            <option value="evening">晚班</option>
            <option value="night">夜班</option>
          </select>
          <button @click="onGenerateSummary" :disabled="generating">
            {{ generating ? '生成中...' : '生成摘要' }}
          </button>
        </div>
        <div v-if="shiftSummaries.length === 0" class="empty">暂无摘要</div>
        <ul class="summary-list">
          <li v-for="s in shiftSummaries" :key="s.id" class="summary-item">
            <div class="summary-head">
              <span class="summary-date">{{ s.shift_date }} {{ periodLabel(s.shift_period) }}</span>
              <span class="summary-counts">{{ s.event_count }} 事件</span>
            </div>
            <div class="summary-text">{{ s.summary_text }}</div>
            <div class="summary-meta">
              P1 {{ s.p1_count }} · P2 {{ s.p2_count }} · 已处置 {{ s.resolved_count }} · 误报 {{ s.false_positive_count }}
            </div>
          </li>
        </ul>
      </section>
    </main>

    <footer class="footer">
      智慧病房云边协同系统 · 框架骨架 v0.1 · 演示阶段数据均为模拟
    </footer>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import api from './api/index.js'
import ws from './api/websocket.js'

const wards = ref([])
const events = ref([])
const stats = ref({})
const currentTime = ref('')
const shiftSummaries = ref([])
const shiftDate = ref(new Date().toISOString().slice(0, 10))
const shiftPeriod = ref('day')
const generating = ref(false)

let timer = null

const periodLabel = (p) => ({ day: '白班', evening: '晚班', night: '夜班' }[p] || p)

// 占位：当前直接用 ward.beds 渲染（bedOccupancy/bedId 为兼容占位）
const bedId = (ward, idx) => ward.beds && ward.beds[idx] ? ward.beds[idx].id : null
const bedOccupancy = () => null

const eventTypeLabel = (t) => ({
  fall_suspected: '疑似跌倒',
  nurse_call: '护士呼叫',
  bed_leave: '离床',
  infusion_anomaly: '输液异常',
  door_departure: '门区异常',
  night_wandering: '夜间徘徊',
  environment_anomaly: '环境异常',
  node_offline: '节点失联',
  fall_prediction: '坠床预警',
  long_still: '长时间静止',
  abnormal_posture: '异常体态',
  seizure: '抽搐检测',
  bedsore_risk: '压疮风险',
  device_fault: '设备故障',
}[t] || t)

const formatTime = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('zh-CN')
}

const loadWards = async () => {
  try {
    const res = await api.getWards()
    wards.value = res.data.data || []
  } catch (e) { console.error('加载病区失败', e) }
}

const loadEvents = async () => {
  try {
    const res = await api.getEvents({ hours: 24, limit: 50 })
    events.value = res.data.data || []
  } catch (e) { console.error('加载事件失败', e) }
}

const loadStats = async () => {
  try {
    const res = await api.getStats()
    stats.value = res.data.data || {}
  } catch (e) { console.error('加载统计失败', e) }
}

const onAck = async (evt, action) => {
  try {
    await api.ackEvent(evt.event_id, {
      action,
      operator_id: 'nurse-demo',
      operator_name: '演示护士',
      operator_role: 'nurse',
    })
    // 乐观更新本地状态
    const stateMap = {
      acknowledge: 'acknowledged',
      resolve: 'resolved',
      false_positive: 'false_positive',
      escalate: 'escalated',
    }
    evt.state = stateMap[action]
  } catch (e) {
    console.error('确认失败', e)
    alert('确认失败，请查看后端日志')
  }
}

const onWsMessage = (msg) => {
  if (msg.type === 'safety_event') {
    events.value.unshift({
      event_id: msg.event_id,
      event_type: msg.event_type,
      priority: msg.priority,
      state: msg.state,
      confidence: msg.confidence,
      bed_id: msg.bed_id,
      occurred_at: msg.occurred_at,
    })
    if (events.value.length > 50) events.value.pop()
  } else if (msg.type === 'event_ack') {
    const evt = events.value.find(e => e.event_id === msg.event_id)
    if (evt) {
      const stateMap = { acknowledge: 'acknowledged', resolve: 'resolved', false_positive: 'false_positive', escalate: 'escalated' }
      evt.state = stateMap[msg.action] || evt.state
    }
  } else if (msg.type === 'node_health') {
    loadStats()
  } else if (msg.type === 'shift_summary') {
    loadShiftSummaries()
  }
}

const loadShiftSummaries = async () => {
  try {
    const res = await api.getShiftSummaries({ ward_id: 'W-01', limit: 10 })
    shiftSummaries.value = res.data.data || []
  } catch (e) { console.error('加载摘要失败', e) }
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
  } catch (e) {
    console.error('生成摘要失败', e)
    alert('生成失败，请查看后端日志')
  } finally {
    generating.value = false
  }
}

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
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; background: #0f1b2d; color: #e0e6ed; }
.nurse-station { min-height: 100vh; display: flex; flex-direction: column; }
.topbar { background: #1a2942; padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #2a3f5f; }
.title { font-size: 18px; font-weight: 600; color: #4fc3f7; }
.metrics { display: flex; gap: 16px; font-size: 13px; }
.metric { padding: 4px 10px; background: #243449; border-radius: 4px; }
.metric.alert { background: #5a2a2a; color: #ff9a9a; }
.metric.p1 { background: #6b1f1f; color: #ffb3b3; animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0.5; } }
.body { flex: 1; display: grid; grid-template-columns: 1.5fr 1fr 1fr; gap: 12px; padding: 12px; }
.wards-panel, .events-panel { background: #1a2942; border-radius: 8px; padding: 16px; overflow-y: auto; }
h2 { font-size: 15px; color: #4fc3f7; margin-bottom: 12px; }
.count { color: #ff9a9a; font-weight: normal; }
.empty { color: #6a7a8a; text-align: center; padding: 20px; }
.bed-grid { display: flex; flex-direction: column; gap: 12px; }
.ward-card { background: #243449; border-radius: 6px; padding: 12px; }
.ward-header { font-weight: 600; margin-bottom: 8px; }
.beds { display: grid; grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); gap: 8px; }
.bed-card { background: #2d4055; border-radius: 4px; padding: 8px; text-align: center; }
.bed-card.occupied { border-left: 3px solid #4caf50; }
.bed-card.alert { border-left: 3px solid #f44336; }
.bed-card.maintenance { border-left: 3px solid #ff9800; }
.bed-alias { font-size: 11px; color: #b0c4de; margin-top: 2px; }
.bed-pending { font-size: 10px; color: #ff9a9a; margin-top: 2px; }
.bed-name { font-size: 13px; }
.bed-status { font-size: 11px; color: #8a9aaa; }
.ward-meta { display: flex; justify-content: space-between; font-size: 12px; color: #8a9aaa; margin-top: 8px; }
.event-list { list-style: none; }
.event-item { background: #243449; border-radius: 6px; padding: 10px; margin-bottom: 8px; border-left: 3px solid #4caf50; }
.event-item.P1 { border-left-color: #f44336; }
.event-item.P2 { border-left-color: #ff9800; }
.event-item.P3 { border-left-color: #2196f3; }
.event-item.resolved, .event-item.false_positive { opacity: 0.5; }
.event-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.badge { padding: 2px 6px; border-radius: 3px; font-size: 11px; font-weight: 600; }
.badge.P1 { background: #6b1f1f; color: #fff; }
.badge.P2 { background: #6b4a1f; color: #fff; }
.badge.P3 { background: #1f3a6b; color: #fff; }
.event-type { font-weight: 600; }
.state { margin-left: auto; font-size: 11px; color: #8a9aaa; }
.event-meta { font-size: 12px; color: #8a9aaa; }
.event-actions { margin-top: 8px; display: flex; gap: 4px; }
.event-actions button { flex: 1; padding: 4px; background: #2d4055; color: #e0e6ed; border: 1px solid #3a4f64; border-radius: 3px; cursor: pointer; font-size: 12px; }
.event-actions button:hover { background: #3a4f64; }
.footer { text-align: center; padding: 8px; font-size: 12px; color: #6a7a8a; border-top: 1px solid #2a3f5f; }

/* 交接班面板 */
.shift-panel { background: #1a2942; border-radius: 8px; padding: 12px; overflow-y: auto; }
.shift-form { display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
.shift-input { background: #243449; color: #e0e6ed; border: 1px solid #3a4f64; border-radius: 3px; padding: 4px 6px; font-size: 12px; }
.shift-form button { padding: 4px 10px; background: #2e75b6; color: #fff; border: none; border-radius: 3px; cursor: pointer; font-size: 12px; }
.shift-form button:disabled { opacity: 0.5; cursor: not-allowed; }
.summary-list { list-style: none; }
.summary-item { background: #243449; border-radius: 4px; padding: 8px; margin-bottom: 8px; border-left: 3px solid #4fc3f7; }
.summary-head { display: flex; justify-content: space-between; margin-bottom: 4px; }
.summary-date { font-size: 12px; font-weight: 600; color: #4fc3f7; }
.summary-counts { font-size: 11px; color: #8a9aaa; }
.summary-text { font-size: 12px; line-height: 1.5; color: #d0d6dd; margin-bottom: 4px; }
.summary-meta { font-size: 11px; color: #8a9aaa; }
</style>
