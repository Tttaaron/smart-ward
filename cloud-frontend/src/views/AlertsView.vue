<template>
  <div class="alerts-view">
    <!-- 顶部统计卡 -->
    <div class="stats-row">
      <div class="stat-card acc-danger">
        <span class="stat-icon" aria-hidden="true"><el-icon :size="16"><WarningFilled /></el-icon></span>
        <div class="stat-copy">
          <span class="stat-label">待处置</span>
          <strong class="stat-value font-num">{{ pendingCount }}</strong>
        </div>
        <span class="stat-hint">new / notified</span>
      </div>
      <div class="stat-card acc-warning">
        <span class="stat-icon" aria-hidden="true"><el-icon :size="16"><Timer /></el-icon></span>
        <div class="stat-copy">
          <span class="stat-label">超时 / 降级</span>
          <strong class="stat-value font-num">{{ timeoutCount }}</strong>
        </div>
        <span class="stat-hint">> 3min 或云端回退</span>
      </div>
      <div class="stat-card acc-accent">
        <span class="stat-icon" aria-hidden="true"><el-icon :size="16"><DataLine /></el-icon></span>
        <div class="stat-copy">
          <span class="stat-label">今日事件</span>
          <strong class="stat-value font-num">{{ state.stats.events_today ?? '—' }}</strong>
        </div>
        <span class="stat-hint">全病区累计</span>
      </div>
      <div class="stat-card acc-neutral">
        <span class="stat-icon" aria-hidden="true"><el-icon :size="16"><CircleCheckFilled /></el-icon></span>
        <div class="stat-copy">
          <span class="stat-label">已归档</span>
          <strong class="stat-value font-num">{{ archivedCount }}</strong>
        </div>
        <span class="stat-hint">resolved / 误报</span>
      </div>
      <div class="stat-card acc-neutral">
        <span class="stat-icon" aria-hidden="true"><el-icon :size="16"><Cloudy /></el-icon></span>
        <div class="stat-copy">
          <span class="stat-label">云端研判</span>
          <strong class="stat-value font-num">{{ cloudJudgeCount }}</strong>
        </div>
        <span class="stat-hint">含二次研判结果</span>
      </div>
    </div>

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
import EventPanel from '../components/EventPanel.vue'
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
</script>

<style scoped>
.alerts-view {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  min-height: 0;
}

/* 统计卡 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  flex: 0 0 auto;
}
.stat-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 12px 13px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 11px;
  box-shadow: var(--shadow-panel), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(14px);
  overflow: hidden;
}
.stat-card::before {
  content: '';
  position: absolute;
  top: -1px;
  left: 14px;
  right: 14px;
  height: 2px;
  border-radius: 0 0 3px 3px;
  background: var(--stat-accent, var(--primary));
  opacity: 0.6;
}
.stat-card.acc-danger { --stat-accent: var(--danger); }
.stat-card.acc-warning { --stat-accent: var(--warning); }
.stat-card.acc-accent { --stat-accent: var(--accent); }
.stat-card.acc-neutral { --stat-accent: var(--info); }

.stat-icon {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border-radius: 9px;
  color: var(--stat-accent, var(--primary));
  background: color-mix(in srgb, var(--stat-accent, var(--primary)) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--stat-accent, var(--primary)) 30%, transparent);
}
.stat-copy { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.stat-label { color: var(--text-3); font-size: 10.5px; font-weight: 700; white-space: nowrap; }
.stat-value {
  color: var(--stat-accent, var(--text));
  font-size: 22px;
  font-weight: 800;
  line-height: 1.1;
  text-shadow: 0 0 12px color-mix(in srgb, var(--stat-accent, var(--text)) 22%, transparent);
}
.stat-hint {
  margin-left: auto;
  color: var(--text-3);
  font-size: 9.5px;
  font-weight: 600;
  white-space: nowrap;
  align-self: flex-end;
}

.alerts-queue {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 1280px) {
  .stats-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .stats-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .stat-hint { display: none; }
}
</style>
