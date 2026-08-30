<template>
  <div class="alerts-view">
    <!-- 顶部统计卡（与总览大屏共用 MetricStrip，保证跨页视觉一致） -->
    <MetricStrip :items="metrics" />

    <!-- 全量告警队列 -->
    <section class="panel acc-danger alerts-queue">
      <div class="panel-caption">
        <span class="caption-index">02</span>
        <span class="caption-title">告警中心</span>
        <span class="caption-meta">共 {{ state.events.length }} 条 · 实时推送</span>
      </div>
      <EventPanel
        :events="state.events"
        @ack="store.onAck"
        @show-monitor="store.openMonitorFromEvent"
        @open-detail="store.openDetail"
      />
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import MetricStrip from '../components/MetricStrip.vue'
import EventPanel from '../components/EventPanel.vue'
import {
  WarningFilled, Timer, DataLine, CircleCheckFilled, Cloudy,
} from '@element-plus/icons-vue'
import { useWardStore } from '../stores/ward.js'
import { resolveFallback, getCloudInference } from '../utils/eventMeta.js'

const store = useWardStore()
const { state } = store

const pendingCount = computed(
  () => state.events.filter((e) => ['new', 'notified'].includes(e.state)).length
)
const timeoutCount = computed(() => state.events.filter((e) => resolveFallback(e)).length)
const archivedCount = computed(
  () => state.events.filter((e) => ['resolved', 'false_positive'].includes(e.state)).length
)
const cloudJudgeCount = computed(() => state.events.filter((e) => getCloudInference(e)).length)

const metrics = computed(() => [
  {
    key: 'pending',
    label: '待处置',
    value: pendingCount.value,
    hint: 'new / notified',
    icon: WarningFilled,
    tone: pendingCount.value > 0 ? 'danger' : 'success',
  },
  {
    key: 'timeout',
    label: '超时 / 降级',
    value: timeoutCount.value,
    hint: '> 3min 或云端回退',
    icon: Timer,
    tone: timeoutCount.value > 0 ? 'warning' : 'neutral',
  },
  {
    key: 'today',
    label: '今日事件',
    value: state.stats.events_today ?? '—',
    hint: '全病区累计',
    icon: DataLine,
    tone: 'accent',
  },
  {
    key: 'archived',
    label: '已归档',
    value: archivedCount.value,
    hint: 'resolved / 误报',
    icon: CircleCheckFilled,
    tone: 'success',
  },
  {
    key: 'cloud',
    label: '云端研判',
    value: cloudJudgeCount.value,
    hint: '含二次研判结果',
    icon: Cloudy,
    tone: 'primary',
  },
])
</script>

<style scoped>
.alerts-view {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  min-height: 0;
}

/* 统计卡样式已抽到 components/MetricStrip.vue，告警中心与总览大屏共用 */

.alerts-queue {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
</style>
