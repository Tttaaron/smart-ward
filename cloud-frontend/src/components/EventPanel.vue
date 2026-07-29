<template>
  <div class="flex flex-col h-full min-h-0">
    <!-- 标题栏 -->
    <div class="mb-3 border-b border-slate-100 pb-2">
      <div class="flex items-center gap-2 mb-2">
        <h2 class="text-[15px] font-extrabold text-blue-600 m-0 tracking-wide flex items-center gap-1.5">
          <span class="w-1.5 h-4 bg-blue-500 rounded-sm"></span>
          护理告警与呼叫中心
        </h2>
        <el-tag v-if="pendingCount > 0" type="danger" effect="dark" size="small" class="!text-[9px] !font-black !px-2 !py-0 !rounded-full animate-bounce">
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
    <ul v-else class="list-none flex flex-col gap-2.5 overflow-y-auto pr-1 flex-1">
      <li
        v-for="evt in filteredEvents"
        :key="evt.event_id"
        class="clinical-event-card bg-slate-50/60 border border-slate-200/80 rounded-lg p-3 flex flex-col gap-2 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md cursor-pointer"
        :class="[
          evt.priority,
          evt.state,
          { blink: evt.priority === 'P1' && ['new', 'notified'].includes(evt.state) }
        ]"
      >
        <div class="flex items-center gap-1.5">
          <span class="p-badge font-num text-[9px] font-black px-2 py-0.5 rounded-md" :class="evt.priority">{{ evt.priority }}</span>
          <span class="event-title text-[13px] font-extrabold text-slate-800">{{ eventTypeLabel(evt.event_type) }}</span>
          <el-tag size="small" effect="plain" :type="stateTagType(evt.state)" class="ml-auto !text-[10px] !font-bold !rounded-md">
            {{ eventStateLabel(evt.state) }}
          </el-tag>
        </div>

        <div class="flex justify-between items-center text-[11px]">
          <div class="flex gap-2 items-center">
            <span class="font-black text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-100">{{ evt.bed_id }}床</span>
            <span class="text-slate-500 font-semibold">AI置信度: <strong class="text-slate-700 font-num">{{ (evt.confidence * 100).toFixed(0) }}%</strong></span>
            
            <!-- 实时监控画面开启通道 -->
            <button 
              @click.stop="$emit('showMonitor', { id: evt.bed_id, eventType: evt.event_type, confidence: evt.confidence })"
              class="flex items-center gap-1 text-[9px] font-bold bg-slate-100 hover:bg-blue-100 text-slate-600 hover:text-blue-600 border border-slate-200 hover:border-blue-200 px-2 py-0.5 rounded-md transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-2.5 h-2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
              </svg>
              监护画面
            </button>
          </div>

          <span
            v-if="['new', 'notified', 'acknowledged'].includes(evt.state)"
            class="timer-tag font-num text-[10px] font-black px-2 py-0.5 rounded-md border"
            :class="isTimeout(evt) ? 'text-red-500 border-red-200 bg-red-50 animate-pulse' : 'text-blue-600 border-blue-100 bg-blue-50/30'"
          >
            ⏱️ {{ getWaitTimeText(evt) }}
          </span>
        </div>

        <div class="text-[10px] text-slate-400 font-medium">发生时间：{{ formatFullTime(evt.occurred_at) }}</div>

        <!-- 临床处置按钮组 -->
        <div v-if="['new', 'notified', 'acknowledged'].includes(evt.state)" class="flex gap-1.5 mt-1 border-t border-slate-100/50 pt-2">
          <el-button
            v-if="evt.state !== 'acknowledged'"
            size="small" type="success" plain
            class="flex-1 !text-[11px] !font-bold !rounded-md"
            @click="$emit('ack', evt, 'acknowledge')"
          >立即到场</el-button>
          <el-button
            size="small" type="primary" plain
            class="flex-1 !text-[11px] !font-bold !rounded-md"
            @click="$emit('ack', evt, 'resolve')"
          >确认处置</el-button>
          <el-button
            size="small" type="info" plain
            class="flex-1 !text-[11px] !font-bold !rounded-md"
            @click="$emit('ack', evt, 'false_positive')"
          >标记误报</el-button>
          <el-button
            size="small" type="danger" plain
            class="flex-1 !text-[11px] !font-bold !rounded-md"
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

defineEmits(['ack', 'showMonitor'])

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
  border-left-color: #2ea121;
}
.clinical-event-card.P1 {
  border-left-color: #f5222d;
}
.clinical-event-card.P1.blink {
  animation: p1-card-blink 1.2s infinite;
}
.clinical-event-card.P2 {
  border-left-color: #fa8c16;
}
.clinical-event-card.P3 {
  border-left-color: #1890ff;
}
.clinical-event-card.resolved,
.clinical-event-card.false_positive {
  opacity: 0.65;
  border-left-color: #8c8c8c;
}

/* 优先级徽章 */
.p-badge.P1 {
  background: rgba(245, 34, 45, 0.08);
  color: #f5222d;
  border: 1px solid rgba(245, 34, 45, 0.25);
}
.p-badge.P2 {
  background: rgba(250, 140, 22, 0.08);
  color: #fa8c16;
  border: 1px solid rgba(250, 140, 22, 0.25);
}
.p-badge.P3 {
  background: rgba(24, 144, 255, 0.08);
  color: #1890ff;
  border: 1px solid rgba(24, 144, 255, 0.25);
}

@keyframes p1-card-blink {
  0%, 100% { border-left-color: #f5222d; }
  50% { border-left-color: transparent; }
}
</style>
