<template>
  <div class="clinical-event-station">
    <div class="station-header">
      <div class="header-left">
        <h2>护理告警与呼叫中心</h2>
        <span class="count-tag" v-if="pendingCount > 0">{{ pendingCount }} 待处置</span>
      </div>
      <div class="filter-tabs">
        <button 
          v-for="tab in filterTabs" 
          :key="tab.key" 
          :class="{ active: currentFilter === tab.key }"
          @click="currentFilter = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <div v-if="filteredEvents.length === 0" class="clinical-empty">
      <div class="empty-icon font-icon">🛡️</div>
      <div class="empty-text">当前病区暂无符合条件的告警与呼叫记录</div>
    </div>

    <ul v-else class="event-cards-stack">
      <li 
        v-for="evt in filteredEvents" 
        :key="evt.event_id" 
        class="clinical-event-card"
        :class="[evt.priority, evt.state, { blink: evt.priority === 'P1' && ['new', 'notified'].includes(evt.state) }]"
      >
        <div class="card-head">
          <span class="p-badge" :class="evt.priority">{{ evt.priority }}</span>
          <span class="event-title">{{ eventTypeLabel(evt.event_type) }}</span>
          <span class="state-pill" :class="evt.state">{{ eventStateLabel(evt.state) }}</span>
        </div>

        <div class="card-body-row">
          <div class="location-info">
            <span class="bed-tag">{{ evt.bed_id }}床</span>
            <span class="confidence-tag">AI置信度: {{ (evt.confidence * 100).toFixed(0) }}%</span>
          </div>

          <!-- Wait Timer -->
          <div class="timer-tag" :class="{ timeout: isTimeout(evt) }" v-if="['new', 'notified', 'acknowledged'].includes(evt.state)">
            ⏱️ {{ getWaitTimeText(evt) }}
          </div>
        </div>

        <div class="time-meta">
          发生时间：{{ formatFullTime(evt.occurred_at) }}
        </div>

        <!-- Clinical Workflow Action Buttons -->
        <div class="clinical-actions-row" v-if="['new', 'notified', 'acknowledged'].includes(evt.state)">
          <button v-if="evt.state !== 'acknowledged'" @click="$emit('ack', evt, 'acknowledge')" class="btn-clin ack">
            立即到场
          </button>
          <button @click="$emit('ack', evt, 'resolve')" class="btn-clin resolve">
            确认处置
          </button>
          <button @click="$emit('ack', evt, 'false_positive')" class="btn-clin false">
            标记误报
          </button>
          <button @click="$emit('ack', evt, 'escalate')" class="btn-clin escalate">
            科室升级
          </button>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  events: {
    type: Array,
    required: true,
    default: () => []
  }
})

defineEmits(['ack'])

const currentFilter = ref('all')
const nowTimestamp = ref(Date.now())
let timer = null

onMounted(() => {
  timer = setInterval(() => {
    nowTimestamp.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const filterTabs = [
  { key: 'all', label: '全部' },
  { key: 'p1', label: 'P1特急' },
  { key: 'pending', label: '待到场' },
  { key: 'resolved', label: '已归档' }
]

const pendingCount = computed(() => {
  return props.events.filter(e => ['new', 'notified'].includes(e.state)).length
})

const filteredEvents = computed(() => {
  if (currentFilter.value === 'p1') {
    return props.events.filter(e => e.priority === 'P1')
  }
  if (currentFilter.value === 'pending') {
    return props.events.filter(e => ['new', 'notified'].includes(e.state))
  }
  if (currentFilter.value === 'resolved') {
    return props.events.filter(e => ['resolved', 'false_positive'].includes(e.state))
  }
  return props.events
})

const eventTypeLabel = (t) => ({
  fall_suspected: '疑似跌倒 (突发危险)',
  nurse_call: '护士呼叫 (患者求助)',
  bed_leave: '患者离床 (离床预警)',
  door_departure: '门区异常 (离走风险)',
  night_wandering: '夜间徘徊 (离床夜游)',
  environment_anomaly: '环境异常 (病房监测)',
  node_offline: '节点失联 (设备断连)',
  fall_prediction: '坠床预警 (体态危险)',
  long_still: '长时间静止 (体征监护)',
  abnormal_posture: '异常体态 (姿势异常)',
  seizure: '抽搐检测 (身体抽动)',
  bedsore_risk: '压疮预防 (翻身提醒)',
  device_fault: '设备故障 (网络异常)',
}[t] || t)

const eventStateLabel = (s) => ({
  new: '未到场',
  notified: '未到场',
  acknowledged: '护士到场中',
  resolved: '已归档完成',
  false_positive: '判定误报',
  escalated: '升级上报',
}[s] || s)

const formatFullTime = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const getWaitTimeText = (evt) => {
  if (!evt.occurred_at) return '已等待 00:00'
  const diffSec = Math.max(0, Math.floor((nowTimestamp.value - new Date(evt.occurred_at).getTime()) / 1000))
  const m = String(Math.floor(diffSec / 60)).padStart(2, '0')
  const s = String(diffSec % 60).padStart(2, '0')
  return `已等待 ${m}:${s}`
}

const isTimeout = (evt) => {
  if (!evt.occurred_at) return false
  const diffSec = Math.floor((nowTimestamp.value - new Date(evt.occurred_at).getTime()) / 1000)
  return diffSec > 180 // Timeout highlight if > 3 mins
}
</script>

<style scoped>
.clinical-event-station {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.station-header {
  margin-bottom: 12px;
  border-bottom: 1px solid #1e293b;
  padding-bottom: 8px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.header-left h2 {
  font-size: 15px;
  font-weight: 700;
  color: #38bdf8;
  margin: 0;
}

.count-tag {
  background: rgba(220, 38, 38, 0.2);
  color: #fca5a5;
  border: 1px solid rgba(220, 38, 38, 0.4);
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 10px;
}

.filter-tabs {
  display: flex;
  gap: 4px;
}

.filter-tabs button {
  background: #1e293b;
  border: 1px solid #334155;
  color: #94a3b8;
  padding: 3px 10px;
  font-size: 11px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
}

.filter-tabs button.active {
  background: #0284c7;
  color: #fff;
  border-color: #38bdf8;
}

.clinical-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #64748b;
  padding: 40px 10px;
}

.empty-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.empty-text {
  font-size: 12px;
}

.event-cards-stack {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}

.clinical-event-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-left: 4px solid #10b981;
  border-radius: 6px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.clinical-event-card.P1 {
  border-left-color: #ef4444;
}

.clinical-event-card.P1.blink {
  animation: p1-card-blink 1.2s infinite;
}

.clinical-event-card.P2 {
  border-left-color: #f59e0b;
}

.clinical-event-card.P3 {
  border-left-color: #0284c7;
}

.clinical-event-card.resolved, .clinical-event-card.false_positive {
  opacity: 0.65;
  border-left-color: #64748b;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.p-badge {
  font-family: 'Outfit', sans-serif;
  font-size: 10px;
  font-weight: 800;
  padding: 1px 6px;
  border-radius: 3px;
}

.p-badge.P1 { background: rgba(220, 38, 38, 0.2); color: #fca5a5; border: 1px solid rgba(220, 38, 38, 0.4); }
.p-badge.P2 { background: rgba(217, 119, 6, 0.2); color: #fde047; border: 1px solid rgba(217, 119, 6, 0.4); }
.p-badge.P3 { background: rgba(2, 132, 199, 0.2); color: #7dd3fc; border: 1px solid rgba(2, 132, 199, 0.4); }

.event-title {
  font-size: 13px;
  font-weight: 700;
  color: #f1f5f9;
}

.state-pill {
  margin-left: auto;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  background: #0f172a;
  color: #94a3b8;
  border: 1px solid #334155;
}

.state-pill.acknowledged {
  color: #fde047;
  border-color: rgba(217, 119, 6, 0.4);
}

.card-body-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
}

.location-info {
  display: flex;
  gap: 6px;
  align-items: center;
}

.bed-tag {
  font-weight: 700;
  color: #38bdf8;
  background: #0f172a;
  padding: 1px 6px;
  border-radius: 3px;
}

.confidence-tag {
  color: #94a3b8;
}

.timer-tag {
  font-family: 'Outfit', sans-serif;
  font-size: 11px;
  font-weight: 700;
  color: #38bdf8;
  background: #0f172a;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #334155;
}

.timer-tag.timeout {
  color: #ef4444;
  border-color: rgba(220, 38, 38, 0.4);
  background: rgba(220, 38, 38, 0.1);
}

.time-meta {
  font-size: 10px;
  color: #64748b;
}

.clinical-actions-row {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}

.btn-clin {
  flex: 1;
  padding: 5px;
  font-size: 11px;
  font-weight: 700;
  border-radius: 4px;
  border: 1px solid #334155;
  background: #0f172a;
  color: #cbd5e1;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-clin.ack {
  background: rgba(16, 185, 129, 0.15);
  border-color: rgba(16, 185, 129, 0.4);
  color: #34d399;
}
.btn-clin.ack:hover {
  background: #10b981;
  color: #fff;
}

.btn-clin.resolve:hover {
  background: #0284c7;
  color: #fff;
  border-color: #0284c7;
}

@keyframes p1-card-blink {
  0%, 100% { border-left-color: #ef4444; }
  50% { border-left-color: transparent; }
}
</style>
