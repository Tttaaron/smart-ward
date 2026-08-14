<template>
  <div class="shifts-view">
    <!-- 主：交接班摘要 -->
    <section class="panel acc-neutral shifts-main">
      <div class="panel-caption">
        <span class="caption-index">01</span>
        <span class="caption-title">临床护理交接班</span>
        <span class="caption-meta">交接责任护士：{{ STAFF.onDuty.name }} ({{ STAFF.onDuty.role }})</span>
      </div>
      <ShiftPanel
        :shift-summaries="state.shiftSummaries"
        :generating="state.generating"
        v-model:shift-date="state.shiftDate"
        v-model:shift-period="state.shiftPeriod"
        @generate="store.onGenerateSummary"
        @delete-summary="store.onDeleteSummary"
      />
    </section>

    <!-- 侧：24h 事件趋势 -->
    <aside class="panel acc-accent shifts-side">
      <div class="panel-caption">
        <span class="caption-index">02</span>
        <span class="caption-title">事件趋势</span>
        <span class="caption-meta">24h · 类别占比</span>
      </div>
      <EventTrendChart :demo-mode="state.demoMode" :refresh-tick="state.refreshTick" />
      <div class="panel-divider" aria-hidden="true"></div>
      <div class="shift-stats">
        <div class="shift-stat-row">
          <span class="ss-label">本班次事件</span>
          <strong class="ss-value font-num">{{ state.stats.events_today ?? '—' }}</strong>
        </div>
        <div class="shift-stat-row">
          <span class="ss-label">P1 待处置</span>
          <strong class="ss-value font-num t-danger">{{ state.stats.p1_pending ?? '—' }}</strong>
        </div>
        <div class="shift-stat-row">
          <span class="ss-label">离床告警</span>
          <strong class="ss-value font-num t-warning">{{ state.stats.leave_beds ?? '—' }}</strong>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup>
import ShiftPanel from '../components/ShiftPanel.vue'
import EventTrendChart from '../components/EventTrendChart.vue'
import { useWardStore } from '../stores/ward.js'
import { STAFF } from '../mock/wardProfile.js'

const store = useWardStore()
const { state } = store
</script>

<style scoped>
.shifts-view {
  display: grid;
  grid-template-columns: minmax(440px, 1.4fr) minmax(320px, 0.8fr);
  gap: 14px;
  height: 100%;
  min-height: 0;
}

.shifts-main { overflow: hidden; }

.shifts-side { overflow: hidden; }

.shift-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.shift-stat-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 11px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 9px;
}
.ss-label { color: var(--text-3); font-size: 11.5px; font-weight: 600; }
.ss-value { color: var(--text); font-size: 15px; font-weight: 800; }
.t-danger { color: var(--danger); }
.t-warning { color: var(--warning); }

@media (max-width: 1020px) {
  .shifts-view {
    display: flex;
    flex-direction: column;
    height: auto;
    min-height: 100%;
    overflow-y: auto;
  }
  .shifts-main { min-height: 460px; }
}
</style>
