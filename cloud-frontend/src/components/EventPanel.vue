<template>
  <div class="h-full flex flex-col">
    <!-- 标题栏 -->
    <div class="mb-3 border-b border-med-border pb-2">
      <div class="flex items-center gap-2 mb-2">
        <h2 class="text-[15px] font-bold text-med-primary m-0">护理告警与呼叫中心</h2>
        <el-tag v-if="pendingCount > 0" type="danger" effect="light" size="small" class="!text-[10px] !font-bold !rounded-full">
          {{ pendingCount }} 待处置
        </el-tag>
      </div>
      <el-radio-group v-model="currentFilter" size="small">
        <el-radio-button
          v-for="tab in filterTabs"
          :key="tab.key"
          :value="tab.key"
        >{{ tab.label }}</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 空状态 -->
    <el-empty v-if="filteredEvents.length === 0" description="当前病区暂无符合条件的告警与呼叫记录" :image-size="64">
      <template #image>
        <span class="text-3xl">🛡️</span>
      </template>
    </el-empty>

    <!-- 事件卡片列表 -->
    <ul v-else class="list-none flex flex-col gap-2 overflow-y-auto">
      <li
        v-for="evt in filteredEvents"
        :key="evt.event_id"
        class="clinical-event-card bg-med-surface-2 border rounded-md p-2.5 flex flex-col gap-1.5"
        :class="[
          evt.priority,
          evt.state,
          { blink: evt.priority === 'P1' && ['new', 'notified'].includes(evt.state) }
        ]"
      >
        <div class="flex items-center gap-1.5">
          <span class="p-badge font-num text-[10px] font-extrabold px-1.5 py-0.5 rounded" :class="evt.priority">{{ evt.priority }}</span>
          <span class="event-title text-[13px] font-bold text-med-text">{{ eventTypeLabel(evt.event_type) }}</span>
          <el-tag size="small" effect="plain" :type="stateTagType(evt.state)" class="ml-auto !text-[10px]">
            {{ eventStateLabel(evt.state) }}
          </el-tag>
        </div>

        <div class="flex justify-between items-center text-[11px]">
          <div class="flex gap-1.5 items-center">
            <span class="font-bold text-med-primary bg-med-surface px-1.5 py-0.5 rounded">{{ evt.bed_id }}床</span>
            <span class="text-med-text-2">AI置信度: {{ (evt.confidence * 100).toFixed(0) }}%</span>
          </div>

          <span
            v-if="['new', 'notified', 'acknowledged'].includes(evt.state)"
            class="timer-tag font-num text-[11px] font-bold px-2 py-0.5 rounded border"
            :class="isTimeout(evt) ? 'text-med-danger border-med-danger/40 bg-med-danger/5' : 'text-med-primary border-med-border bg-med-surface'"
          >
            ⏱️ {{ getWaitTimeText(evt) }}
          </span>
        </div>

        <div class="text-[10px] text-med-text-3">发生时间：{{ formatFullTime(evt.occurred_at) }}</div>

        <!-- 临床处置按钮组 -->
        <div v-if="['new', 'notified', 'acknowledged'].includes(evt.state)" class="flex gap-1.5 mt-1">
          <el-button
            v-if="evt.state !== 'acknowledged'"
            size="small" type="success" plain
            class="flex-1 !text-[11px] !font-bold"
            @click="$emit('ack', evt, 'acknowledge')"
          >立即到场</el-button>
          <el-button
            size="small" type="primary" plain
            class="flex-1 !text-[11px] !font-bold"
            @click="$emit('ack', evt, 'resolve')"
          >确认处置</el-button>
          <el-button
            size="small" type="info" plain
            class="flex-1 !text-[11px] !font-bold"
            @click="$emit('ack', evt, 'false_positive')"
          >标记误报</el-button>
          <el-button
            size="small" type="danger" plain
            class="flex-1 !text-[11px] !font-bold"
            @click="$emit('ack', evt, 'escalate')"
          >科室升级</el-button>
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

// 状态映射为 Element Plus tag type
const stateTagType = (s) => ({
  new: 'danger',
  notified: 'danger',
  acknowledged: 'warning',
  resolved: 'success',
  false_positive: 'info',
  escalated: 'danger',
}[s] || 'info')

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
  return diffSec > 180 // 超时高亮：> 3 分钟
}
</script>

<style scoped>
/* 优先级左边框 */
.clinical-event-card {
  border-left-width: 4px;
  border-left-color: #00b42a;
}
.clinical-event-card.P1 {
  border-left-color: #f53f3f;
}
.clinical-event-card.P1.blink {
  animation: p1-card-blink 1.2s infinite;
}
.clinical-event-card.P2 {
  border-left-color: #ff7d00;
}
.clinical-event-card.P3 {
  border-left-color: #1677ff;
}
.clinical-event-card.resolved,
.clinical-event-card.false_positive {
  opacity: 0.65;
  border-left-color: #86909c;
}

/* 优先级徽章 */
.p-badge.P1 {
  background: rgba(245, 63, 63, 0.1);
  color: #f53f3f;
  border: 1px solid rgba(245, 63, 63, 0.3);
}
.p-badge.P2 {
  background: rgba(255, 125, 0, 0.1);
  color: #ff7d00;
  border: 1px solid rgba(255, 125, 0, 0.3);
}
.p-badge.P3 {
  background: rgba(22, 119, 255, 0.1);
  color: #1677ff;
  border: 1px solid rgba(22, 119, 255, 0.3);
}

@keyframes p1-card-blink {
  0%, 100% { border-left-color: #f53f3f; }
  50% { border-left-color: transparent; }
}
</style>
