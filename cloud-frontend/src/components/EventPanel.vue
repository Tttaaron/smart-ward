<template>
  <div class="flex flex-col h-full min-h-0">
    <!-- 标题栏 -->
    <div class="mb-3 border-b border-slate-100 pb-2">
      <div class="flex items-center gap-2 mb-2">
        <h2 class="event-panel-title text-[15px] font-extrabold m-0 tracking-wide flex items-center gap-1.5">
          <el-icon :size="17" aria-hidden="true"><BellFilled /></el-icon>
          <span>护理告警与呼叫中心</span>
        </h2>
        <el-tag v-if="pendingCount > 0" type="danger" effect="dark" size="small" class="!text-[10px] !font-black !px-2 !py-0 !rounded-md">
          {{ pendingCount }} 待处置
        </el-tag>
        <el-tag v-if="timeoutCount > 0" type="warning" effect="light" size="small" class="!text-[10px] !font-black !px-2 !py-0 !rounded-md">
          {{ timeoutCount }} 超时/降级
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
        <el-icon class="empty-state-icon" :size="28" aria-hidden="true"><FirstAidKit /></el-icon>
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
          { 'card-timeout': fallbackOf(evt) }
        ]"
        @click="$emit('open-detail', evt.event_id)"
      >
        <!-- 首行：优先级 + 类型 + 状态 -->
        <div class="flex items-center gap-1.5">
          <span class="p-badge font-num text-[9px] font-black px-2 py-0.5 rounded-md" :class="evt.priority">{{ evt.priority }}</span>
          <span class="event-title text-[13px] font-extrabold text-slate-800">{{ eventTypeLabel(evt.event_type) }}</span>

          <!-- 推理链路 route -->
          <span
            class="route-chip font-num text-[9px] font-black px-1.5 py-0.5 rounded-md"
            :class="'route-' + routeOf(evt)"
            :title="routeDesc(routeOf(evt))"
          >
            <span class="route-mark" aria-hidden="true"></span>{{ routeLabel(routeOf(evt)) }}
          </span>

          <!-- 超时/降级状态 -->
          <span v-if="fallbackOf(evt)" class="fb-chip font-num text-[9px] font-black px-1.5 py-0.5 rounded-md animate-pulse">
            {{ stateLabel(fallbackOf(evt)) }}
          </span>

          <el-tag size="small" effect="plain" :type="stateTagType(evt.state)" class="ml-auto !text-[10px] !font-bold !rounded-md">
            {{ eventStateLabel(evt.state) }}
          </el-tag>
        </div>

        <!-- 第二行：床位 + 置信度 + 网络状态 + 监控按钮 -->
        <div class="flex justify-between items-center text-[11px]">
          <div class="flex gap-2 items-center">
            <span class="bed-id-chip">{{ evt.bed_id }}床</span>
            <span class="text-slate-500 font-semibold">AI置信度: <strong class="text-slate-700 font-num">{{ (evt.confidence * 100).toFixed(0) }}%</strong></span>

            <!-- 节点网络状态 -->
            <span v-if="networkOf(evt)" class="net-chip font-num text-[9px] font-black px-1.5 py-0.5 rounded-md" :class="'net-' + networkOf(evt)">
              {{ networkLabel(networkOf(evt)) }}
            </span>

            <!-- 实时监控画面开启通道 -->
            <button
              @click.stop="$emit('showMonitor', { id: evt.bed_id, eventType: evt.event_type, confidence: evt.confidence })"
              class="event-monitor-button"
            >
              <el-icon :size="13" aria-hidden="true"><VideoCameraFilled /></el-icon>
              监护画面
            </button>
          </div>

          <span
            v-if="['new', 'notified', 'acknowledged'].includes(evt.state)"
            class="timer-tag font-num text-[10px] font-black px-2 py-0.5 rounded-md border"
            :class="isTimeout(evt) ? 'timer-timeout animate-pulse' : 'timer-normal'"
          >
            <el-icon :size="12" aria-hidden="true"><Timer /></el-icon>
            {{ getWaitTimeText(evt) }}
          </span>
        </div>

        <!-- 第三行：模型 + 性能指标 -->
        <div class="flex flex-wrap gap-x-3 gap-y-1 text-[9.5px] text-slate-500 font-semibold items-center">
          <span class="flex items-center gap-1">
            <span class="text-slate-400">模型</span>
            <span class="text-slate-700 font-num">{{ evt.model_name || '—' }}<span v-if="evt.model_version" class="model-version">@{{ evt.model_version }}</span></span>
          </span>
          <span class="flex items-center gap-1">
            <span class="text-slate-400">边缘推理</span>
            <span class="text-slate-700 font-num">{{ fmtMs(perfOf(evt).inference_ms) }}</span>
          </span>
          <span v-if="perfOf(evt).ttft_ms != null" class="flex items-center gap-1">
            <span class="text-slate-400">TTFT</span>
            <span class="text-slate-700 font-num">{{ fmtMs(perfOf(evt).ttft_ms) }}</span>
          </span>
          <span v-if="perfOf(evt).cloud_latency_ms != null" class="flex items-center gap-1">
            <span class="text-slate-400">云端延迟</span>
            <span class="text-slate-700 font-num">{{ fmtMs(perfOf(evt).cloud_latency_ms) }}</span>
          </span>
          <span v-if="perfOf(evt).memory_mb != null" class="flex items-center gap-1">
            <span class="text-slate-400">内存</span>
            <span class="text-slate-700 font-num">{{ fmtBytesToMb(perfOf(evt).memory_mb) }}</span>
          </span>
        </div>

        <div class="flex items-center justify-between">
          <div class="text-[10px] text-slate-400 font-medium">发生时间：{{ formatFullTime(evt.occurred_at) }}</div>
          <div class="text-[9px] text-slate-300 font-num">trace: {{ shortTrace(evt) }}</div>
        </div>

        <!-- 临床处置：保留两个高频动作，其余收敛到更多菜单，降低连续告警的视觉噪音。 -->
        <div v-if="['new', 'notified', 'acknowledged'].includes(evt.state)" class="event-actions flex gap-1.5 mt-1 border-t border-slate-100/50 pt-2" @click.stop>
          <el-button
            v-if="evt.state !== 'acknowledged'"
            size="small" type="success" plain
            class="flex-1 !text-[12px] !font-bold !rounded-md"
            @click="$emit('ack', evt, 'acknowledge')"
          >立即到场</el-button>
          <el-button
            size="small" type="primary" plain
            class="flex-1 !text-[12px] !font-bold !rounded-md"
            @click="$emit('ack', evt, 'resolve')"
          >确认处置</el-button>
          <el-dropdown trigger="click" @command="(action) => $emit('ack', evt, action)">
            <el-button
              size="small"
              plain
              circle
              class="event-more-button"
              title="更多处置"
              aria-label="更多处置"
            >
              <el-icon :size="16" aria-hidden="true"><MoreFilled /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="false_positive">标记为误报</el-dropdown-item>
                <el-dropdown-item command="escalate" divided class="event-escalate-menu">科室升级</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  resolveRoute, routeLabel, routeDesc,
  stateLabel, resolveFallback, getPerf,
  networkMeta, fmtMs, fmtBytesToMb,
} from '../utils/eventMeta.js'

const props = defineProps({
  events: {
    type: Array,
    required: true,
    default: () => []
  }
})

defineEmits(['ack', 'showMonitor', 'open-detail'])

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
  { key: 'timeout', label: '超时/降级' },
  { key: 'resolved', label: '已归档' }
]

const pendingCount = computed(() => {
  return props.events.filter(e => ['new', 'notified'].includes(e.state)).length
})

const timeoutCount = computed(() => {
  return props.events.filter(e => fallbackOf(e)).length
})

const filteredEvents = computed(() => {
  if (currentFilter.value === 'p1') {
    return props.events.filter(e => e.priority === 'P1')
  }
  if (currentFilter.value === 'pending') {
    return props.events.filter(e => ['new', 'notified'].includes(e.state))
  }
  if (currentFilter.value === 'timeout') {
    return props.events.filter(e => fallbackOf(e))
  }
  if (currentFilter.value === 'resolved') {
    return props.events.filter(e => ['resolved', 'false_positive'].includes(e.state))
  }
  return props.events
})

// ---- 元信息辅助 ----
const routeOf = (evt) => resolveRoute(evt)
const fallbackOf = (evt) => resolveFallback(evt, nowTimestamp.value)
const perfOf = (evt) => getPerf(evt)
const networkOf = (evt) => getPerf(evt).network || evt._network
const networkLabel = (n) => networkMeta(n).label
const shortTrace = (evt) => {
  const t = evt.details?.trace_id || evt.trace_id
  if (!t) return evt.event_id?.slice(0, 12) || '—'
  return String(t).slice(0, 12) + '…'
}

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
  new: '待处置',
  notified: '已通知',
  acknowledged: '确认到场',
  resolved: '已归档',
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
  border-left-color: var(--color-success);
  background: #fffdfa;
}
.clinical-event-card.P1 {
  border-left-color: var(--color-danger);
}
.clinical-event-card.P1:not(.resolved):not(.false_positive) { box-shadow: inset 3px 0 0 var(--color-danger), 0 2px 8px rgba(200, 91, 80, 0.1); }
.clinical-event-card.P2 {
  border-left-color: var(--color-warning);
}
.clinical-event-card.P3 {
  border-left-color: var(--color-primary);
}
.clinical-event-card.resolved,
.clinical-event-card.false_positive {
  opacity: 0.65;
  border-left-color: #8c8c8c;
}

/* 超时/降级卡片右侧提示条 */
.clinical-event-card.card-timeout {
  border-right-width: 3px;
  border-right-color: var(--color-warning);
  background: #fffaf1;
}

/* 优先级徽章 */
.p-badge.P1 {
  background: rgba(200, 91, 80, 0.1);
  color: var(--color-danger);
  border: 1px solid rgba(200, 91, 80, 0.28);
}
.p-badge.P2 {
  background: rgba(189, 118, 43, 0.1);
  color: var(--color-warning);
  border: 1px solid rgba(189, 118, 43, 0.28);
}
.p-badge.P3 {
  background: rgba(20, 121, 118, 0.08);
  color: var(--color-primary);
  border: 1px solid rgba(20, 121, 118, 0.25);
}

/* 推理链路 route 徽章 */
.route-chip.route-edge {
  background: rgba(24, 131, 94, 0.08);
  color: var(--color-success);
  border: 1px solid rgba(24, 131, 94, 0.28);
}
.route-chip.route-cloud {
  background: rgba(20, 121, 118, 0.08);
  color: var(--color-primary);
  border: 1px solid rgba(20, 121, 118, 0.3);
}
.route-chip.route-hybrid {
  background: rgba(189, 118, 43, 0.08);
  color: var(--color-warning);
  border: 1px solid rgba(189, 118, 43, 0.3);
}
.route-mark {
  display: inline-block;
  width: 5px;
  height: 5px;
  margin-right: 4px;
  border-radius: 50%;
  background: currentColor;
  vertical-align: middle;
}

/* 超时/降级徽章 */
.fb-chip {
  background: rgba(189, 118, 43, 0.1);
  color: var(--color-warning);
  border: 1px dashed rgba(189, 118, 43, 0.45);
}

/* 网络状态徽章 */
.net-chip.net-online {
  background: rgba(24, 131, 94, 0.08);
  color: var(--color-success);
  border: 1px solid rgba(24, 131, 94, 0.25);
}
.net-chip.net-degraded {
  background: rgba(189, 118, 43, 0.08);
  color: var(--color-warning);
  border: 1px solid rgba(189, 118, 43, 0.3);
}
.net-chip.net-offline {
  background: rgba(200, 91, 80, 0.08);
  color: var(--color-danger);
  border: 1px solid rgba(200, 91, 80, 0.3);
}

.event-panel-title { color: var(--color-primary); }
.event-panel-title :deep(.el-icon) { color: var(--color-primary); }
.empty-state-icon { color: var(--color-primary); opacity: 0.7; }
.bed-id-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 5px;
  border: 1px solid rgba(20, 121, 118, 0.22);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 800;
}
.event-monitor-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-surface-3);
  color: var(--color-text-2);
  font-size: 9px;
  font-weight: 700;
  transition: all 0.2s ease;
}
.event-monitor-button:hover {
  border-color: rgba(20, 121, 118, 0.42);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}
.timer-tag { display: inline-flex; align-items: center; gap: 4px; }
.timer-normal {
  color: var(--color-primary);
  border: 1px solid rgba(20, 121, 118, 0.22);
  background: rgba(20, 121, 118, 0.06);
}
.timer-timeout {
  color: var(--color-danger);
  border: 1px solid rgba(200, 91, 80, 0.28);
  background: rgba(200, 91, 80, 0.08);
}
.model-version { color: var(--color-primary); }
.event-actions { align-items: stretch; }
.event-actions :deep(.el-button:not(.event-more-button)) { min-width: 0; }
.event-actions :deep(.el-dropdown) { display: flex; }
.event-more-button {
  width: 30px;
  min-width: 30px;
  padding-inline: 0 !important;
  flex: 0 0 30px !important;
}
.event-escalate-menu { color: var(--color-danger); }
@media (max-width: 720px) {
  .clinical-event-card { padding: 10px; }
  .clinical-event-card > .flex:last-child { flex-wrap: wrap; }
}
</style>
