<template>
  <div class="event-panel">
    <!-- 标题 + 计数 -->
    <div class="event-head">
      <div class="event-head-left">
        <span class="head-icon" aria-hidden="true"><el-icon :size="15"><BellFilled /></el-icon></span>
        <span class="head-title">告警队列</span>
        <span v-if="pendingCount > 0" class="chip chip-danger font-num">{{ pendingCount }} 待处置</span>
        <span v-if="timeoutCount > 0" class="chip chip-warning font-num">{{ timeoutCount }} 超时/降级</span>
      </div>

      <!-- 筛选分段控件 -->
      <div class="filter-tabs" role="tablist" aria-label="告警筛选">
        <button
          v-for="tab in filterTabs"
          :key="tab.key"
          type="button"
          role="tab"
          class="filter-tab"
          :class="{ active: currentFilter === tab.key }"
          :aria-selected="currentFilter === tab.key"
          @click="currentFilter = tab.key"
        >{{ tab.label }}</button>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="filteredEvents.length === 0" class="event-empty">
      <el-icon :size="30" aria-hidden="true"><FirstAidKit /></el-icon>
      <p>当前病区暂无符合条件的告警与呼叫记录</p>
    </div>

    <!-- 事件卡片列表 -->
    <ul v-else class="event-list">
      <li
        v-for="evt in visibleEvents"
        :key="evt.event_id"
        class="event-card"
        :class="[
          'pri-' + evt.priority,
          evt.state,
          { 'card-timeout': fallbackOf(evt) }
        ]"
        @click="$emit('open-detail', evt.event_id)"
      >
        <!-- 首行：优先级 + 类型 + 徽章 + 状态 -->
        <div class="event-line1">
          <span class="chip font-num" :class="'chip-' + evt.priority.toLowerCase()">{{ evt.priority }}</span>
          <span class="event-title">{{ eventTypeLabel(evt.event_type) }}</span>

          <span
            class="chip font-num"
            :class="'chip-' + routeOf(evt)"
            :title="routeDesc(routeOf(evt))"
          >
            <span class="route-mark" aria-hidden="true"></span>{{ routeLabel(routeOf(evt)) }}
          </span>

          <span
            v-if="cloudInferenceOf(evt)"
            class="chip font-num"
            :class="'chip-' + cloudToneOf(evt)"
            :title="cloudDescOf(evt)"
          >{{ cloudJudgeLabelOf(evt) }}</span>

          <span v-if="fallbackOf(evt)" class="chip chip-fallback font-num animate-text-pulse">
            {{ stateLabel(fallbackOf(evt)) }}
          </span>

          <span class="state-tag" :class="'state-' + evt.state">{{ eventStateLabel(evt.state) }}</span>
        </div>

        <!-- 第二行：床位 + 置信度 + 网络 + 监护 -->
        <div class="event-line2">
          <span class="chip chip-accent">{{ evt.bed_id }}床</span>
          <span class="conf-text">置信度 <strong class="font-num">{{ (evt.confidence * 100).toFixed(0) }}%</strong></span>

          <span v-if="networkOf(evt)" class="chip font-num" :class="'chip-net-' + networkOf(evt)">
            {{ networkLabel(networkOf(evt)) }}
          </span>

          <button
            @click.stop="$emit('showMonitor', { id: evt.bed_id, eventType: evt.event_type, confidence: evt.confidence })"
            class="monitor-link"
          >
            <el-icon :size="13" aria-hidden="true"><VideoCameraFilled /></el-icon>
            监护画面
          </button>

          <span
            v-if="['new', 'notified', 'acknowledged'].includes(evt.state)"
            class="wait-timer font-num"
            :class="isTimeout(evt) ? 'is-timeout' : ''"
          >
            <el-icon :size="12" aria-hidden="true"><Timer /></el-icon>
            {{ getWaitTimeText(evt) }}
          </span>
        </div>

        <!-- 第四行：时间 + trace + 处置 -->
        <div class="event-line4" @click.stop>
          <span class="occur-time font-num">{{ formatFullTime(evt.occurred_at) }}</span>
          <span class="trace-id font-num">trace: {{ shortTrace(evt) }}</span>

          <div v-if="['new', 'notified', 'acknowledged'].includes(evt.state)" class="event-actions">
            <button
              v-if="evt.state !== 'acknowledged'"
              class="action-btn is-primary"
              @click="$emit('ack', evt, 'acknowledge')"
            >立即到场</button>
            <button
              class="action-btn is-ghost"
              @click="$emit('ack', evt, 'resolve')"
            >确认处置</button>
            <el-dropdown trigger="click" @command="(action) => $emit('ack', evt, action)">
              <button class="action-btn is-more" title="更多处置" aria-label="更多处置">
                <el-icon :size="15" aria-hidden="true"><MoreFilled /></el-icon>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="false_positive">标记为误报</el-dropdown-item>
                  <el-dropdown-item command="escalate" divided class="event-escalate-menu">科室升级</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </li>
    </ul>

    <!-- 超出 limit 时引导至告警中心 -->
    <router-link v-if="limit > 0 && filteredEvents.length > limit" to="/alerts" class="view-all">
      查看全部 {{ filteredEvents.length }} 条告警
      <el-icon :size="13" aria-hidden="true"><ArrowRight /></el-icon>
    </router-link>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  resolveRoute, routeLabel, routeDesc,
  stateLabel, resolveFallback, getPerf,
  networkMeta,
  getCloudInference, cloudJudgmentMeta,
} from '../utils/eventMeta.js'

const props = defineProps({
  events: { type: Array, required: true, default: () => [] },
  // 列表条数上限（0 = 不限制）。启用后展示"查看全部"入口。
  limit: { type: Number, default: 0 },
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
  { key: 'resolved', label: '已归档' },
]

const pendingCount = computed(() =>
  props.events.filter((e) => ['new', 'notified'].includes(e.state)).length
)

const timeoutCount = computed(() => props.events.filter((e) => fallbackOf(e)).length)

const filteredEvents = computed(() => {
  if (currentFilter.value === 'p1') return props.events.filter((e) => e.priority === 'P1')
  if (currentFilter.value === 'pending') return props.events.filter((e) => ['new', 'notified'].includes(e.state))
  if (currentFilter.value === 'timeout') return props.events.filter((e) => fallbackOf(e))
  if (currentFilter.value === 'resolved') return props.events.filter((e) => ['resolved', 'false_positive'].includes(e.state))
  return props.events
})

const visibleEvents = computed(() =>
  props.limit > 0 ? filteredEvents.value.slice(0, props.limit) : filteredEvents.value
)

// ---- 元信息辅助 ----
const routeOf = (evt) => resolveRoute(evt)
const fallbackOf = (evt) => resolveFallback(evt, nowTimestamp.value)
const networkOf = (evt) => getPerf(evt).network || evt._network
const networkLabel = (n) => networkMeta(n).label
const cloudInferenceOf = (evt) => getCloudInference(evt)
const cloudJudgeLabelOf = (evt) => cloudJudgmentMeta(getCloudInference(evt)?.judgment).label
const cloudToneOf = (evt) => cloudJudgmentMeta(getCloudInference(evt)?.judgment).tone
const cloudDescOf = (evt) => {
  const ci = getCloudInference(evt)
  const meta = cloudJudgmentMeta(ci?.judgment)
  return `${meta.desc}${ci?.advice ? `｜${ci.advice}` : ''}`
}

const shortTrace = (evt) => {
  const t = evt.details?.trace_id || evt.trace_id
  if (!t) return evt.event_id?.slice(0, 12) || '—'
  return String(t).slice(0, 12) + '…'
}

const eventTypeLabel = (t) => ({
  fall_suspected: '疑似跌倒',
  nurse_call: '护士呼叫',
  bed_leave: '患者离床',
  door_departure: '门区异常',
  night_wandering: '夜间徘徊',
  environment_anomaly: '环境异常',
  node_offline: '节点失联',
  fall_prediction: '坠床预警',
  long_still: '长时间静止',
  abnormal_posture: '异常体态',
  seizure: '抽搐检测',
  bedsore_risk: '压疮预防',
  device_fault: '设备故障',
}[t] || t)

const eventStateLabel = (s) => ({
  new: '待处置',
  notified: '已通知',
  acknowledged: '确认到场',
  resolved: '已归档',
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
  return diffSec > 180 // 超时高亮：> 3 分钟
}
</script>

<style scoped>
.event-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

/* 头部 */
.event-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  flex: 0 0 auto;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line);
}
.event-head-left { display: flex; align-items: center; gap: 8px; }
.head-icon {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  color: var(--danger);
  background: var(--danger-soft);
  border: 1px solid rgba(220, 38, 38, 0.3);
  border-radius: 7px;
}
.head-title { color: var(--text); font-size: 14px; font-weight: 800; }

/* 筛选分段控件 */
.filter-tabs {
  display: flex;
  padding: 2px;
  background: var(--bg-deep);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.filter-tab {
  height: 24px;
  padding: 0 10px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text-3);
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.18s ease;
}
.filter-tab:hover { color: var(--text-2); }
.filter-tab.active {
  color: var(--primary);
  background: var(--primary-soft);
  box-shadow: 0 0 10px rgba(42, 125, 225, 0.12);
}

/* 空状态 */
.event-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 44px 0;
  color: var(--text-3);
  font-size: 12px;
}
.event-empty :deep(.el-icon) { color: var(--primary); opacity: 0.6; }

/* 列表 */
.event-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
  list-style: none;
  flex: 1;
  min-height: 0;
  padding-right: 3px;
  overflow-y: auto;
}

.event-card {
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 11px 12px 10px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-left: 3px solid var(--info);
  border-radius: 10px;
  cursor: pointer;
  box-shadow: var(--shadow-card);
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}
.event-card:hover {
  transform: translateY(-2px);
  border-color: var(--line-strong);
  border-left-color: var(--line-glow);
  box-shadow: var(--shadow-card-hover);
}
.event-card.pri-P1 { border-left-color: var(--danger); }
.event-card.pri-P1:not(.resolved):not(.false_positive) {
  box-shadow: inset 3px 0 0 var(--danger), 0 0 18px rgba(220, 38, 38, 0.14);
  animation: med-pulse-danger 2.2s ease-in-out infinite;
}
.event-card.pri-P2 { border-left-color: var(--warning); }
.event-card.pri-P3 { border-left-color: var(--primary); }
.event-card.resolved, .event-card.false_positive { opacity: 0.58; border-left-color: var(--info); }

/* 超时/降级卡片右侧提示条 */
.event-card.card-timeout {
  border-right: 3px solid var(--warning);
  background:
    linear-gradient(90deg, transparent 60%, rgba(217, 119, 6, 0.05)),
    var(--surface-2);
}

.event-line1 {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.event-title { color: var(--text); font-size: 13.5px; font-weight: 800; }
.route-mark {
  display: inline-block;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}
.state-tag {
  margin-left: auto;
  padding: 3px 8px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 700;
  border: 1px solid transparent;
}
.state-new, .state-notified { color: var(--danger); background: var(--danger-soft); border-color: rgba(220, 38, 38, 0.3); }
.state-acknowledged { color: var(--warning); background: var(--warning-soft); border-color: rgba(251, 191, 36, 0.3); }
.state-resolved { color: var(--success); background: var(--success-soft); border-color: rgba(52, 211, 153, 0.3); }
.state-false_positive, .state-escalated { color: var(--info); background: var(--info-soft); border-color: rgba(140, 163, 181, 0.3); }

.event-line2 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}
.conf-text { color: var(--text-3); font-weight: 600; }
.conf-text strong { color: var(--text-2); font-weight: 800; }

.monitor-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 8px;
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  background: transparent;
  color: var(--text-2);
  font-size: 10.5px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.18s ease;
}
.monitor-link:hover {
  color: var(--primary);
  border-color: rgba(42, 125, 225, 0.45);
  background: var(--primary-soft);
}

.wait-timer {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 10.5px;
  font-weight: 800;
  color: var(--primary);
  background: var(--primary-soft);
  border: 1px solid rgba(42, 125, 225, 0.25);
}
.wait-timer.is-timeout {
  color: #fff;
  background: var(--danger);
  border: 1px solid var(--danger);
  box-shadow: 0 0 10px rgba(220, 38, 38, 0.4);
  animation: med-text-pulse 1.2s ease-in-out infinite;
}

.event-line4 {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px dashed var(--line);
}
.occur-time { color: var(--text-3); font-size: 10.5px; font-weight: 600; }
.trace-id { color: var(--text-3); font-size: 10px; opacity: 0.8; }

.event-actions {
  display: flex;
  gap: 6px;
  margin-left: auto;
}
.action-btn {
  height: 26px;
  padding: 0 11px;
  border-radius: 7px;
  font-size: 11.5px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.18s ease;
}
.action-btn.is-primary {
  color: #FFFFFF;
  background: linear-gradient(135deg, #6BA6EC, var(--primary));
  border: 1px solid rgba(42, 125, 225, 0.6);
  box-shadow: 0 3px 10px rgba(42, 125, 225, 0.25);
}
.action-btn.is-primary:hover { box-shadow: 0 4px 14px rgba(42, 125, 225, 0.35); }
.action-btn.is-ghost {
  color: var(--primary);
  background: transparent;
  border: 1px solid rgba(42, 125, 225, 0.45);
}
.action-btn.is-ghost:hover { background: var(--primary-soft); }
.action-btn.is-more {
  display: grid;
  place-items: center;
  width: 26px;
  padding: 0;
  color: var(--text-3);
  background: transparent;
  border: 1px solid var(--line-strong);
}
.action-btn.is-more:hover { color: var(--text); border-color: var(--line-glow); }

.event-escalate-menu { color: var(--danger); }

/* 查看全部 */
.view-all {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex: 0 0 auto;
  height: 34px;
  margin-top: 10px;
  border: 1px dashed rgba(42, 125, 225, 0.4);
  border-radius: 8px;
  color: var(--primary);
  font-size: 12px;
  font-weight: 700;
  text-decoration: none;
  transition: all 0.18s ease;
}
.view-all:hover {
  background: var(--primary-soft);
  border-color: var(--primary);
  box-shadow: 0 0 12px rgba(42, 125, 225, 0.14);
}

@media (max-width: 720px) {
  .event-card { padding: 10px; }
  .event-head { flex-direction: column; align-items: stretch; }
  .filter-tabs { overflow-x: auto; }
}
</style>
