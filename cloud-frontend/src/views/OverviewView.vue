<template>
  <div class="overview-view">
    <!-- 左列：床位态势 + 节点延迟 + 环境联动 -->
    <section class="panel acc-neutral overview-left">
      <div class="panel-caption">
        <span class="caption-index">01</span>
        <span class="caption-title">床位态势</span>
        <span class="caption-meta">{{ wardSummary }}</span>
      </div>

      <div class="ward-scroll">
        <WardCard
          v-for="ward in state.wards"
          :key="ward.id"
          :ward="ward"
          :events="state.events"
          @show-monitor="store.openMonitor"
        />
        <div v-if="state.wards.length === 0" class="view-empty">等待病区数据…</div>
      </div>

      <div class="panel-divider" aria-hidden="true"></div>
      <NodeLatencyChart :demo-mode="state.demoMode" :refresh-tick="state.refreshTick" />
      <div class="panel-divider" aria-hidden="true"></div>
      <EnvControlPanel />
    </section>

    <!-- 中列：护理告警 -->
    <section class="panel acc-danger overview-center">
      <div class="panel-caption">
        <span class="caption-index">02</span>
        <span class="caption-title">护理告警</span>
        <span class="caption-meta">优先级队列 · 实时处置</span>
      </div>
      <EventPanel
        :events="state.events"
        :limit="6"
        @ack="store.onAck"
        @show-monitor="store.openMonitorFromEvent"
        @open-detail="store.openDetail"
      />
    </section>

    <!-- 右列：交班摘要 + 24h 趋势 + 活动轨迹 -->
    <aside class="overview-rail">
      <section class="panel acc-neutral shift-brief">
        <div class="panel-caption">
          <span class="caption-index">03</span>
          <span class="caption-title">交班摘要</span>
          <router-link to="/shifts" class="caption-link">查看全部 →</router-link>
        </div>
        <template v-if="latestSummary">
          <p class="brief-text">{{ latestSummary.summary_text }}</p>
          <div class="brief-pills">
            <span class="pill"><i>P1特急</i><b class="font-num t-danger">{{ latestSummary.p1_count }}</b></span>
            <span class="pill"><i>已处置</i><b class="font-num t-success">{{ latestSummary.resolved_count }}</b></span>
            <span class="pill"><i>事件</i><b class="font-num">{{ latestSummary.event_count }}</b></span>
          </div>
        </template>
        <div v-else class="brief-empty">暂无交接记录，可在「交班记录」页生成</div>
      </section>

      <section class="panel acc-accent trend-panel">
        <div class="panel-caption">
          <span class="caption-index">04</span>
          <span class="caption-title">事件趋势</span>
          <span class="caption-meta">24h</span>
        </div>
        <EventTrendChart :demo-mode="state.demoMode" :refresh-tick="state.refreshTick" />
      </section>

      <section class="panel acc-neutral activity-panel">
        <div class="panel-caption">
          <span class="caption-index">05</span>
          <span class="caption-title">活动轨迹</span>
          <span class="caption-meta">摄像头观察</span>
        </div>
        <ActivityLogPanel />
      </section>
    </aside>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import WardCard from '../components/WardCard.vue'
import EventPanel from '../components/EventPanel.vue'
import NodeLatencyChart from '../components/NodeLatencyChart.vue'
import EnvControlPanel from '../components/EnvControlPanel.vue'
import EventTrendChart from '../components/EventTrendChart.vue'
import ActivityLogPanel from '../components/ActivityLogPanel.vue'
import { useWardStore } from '../stores/ward.js'

const store = useWardStore()
const { state } = store

const wardSummary = computed(() => {
  const ward = state.wards[0]
  return ward ? `${ward.id} · ${ward.location}` : 'W-01'
})

const latestSummary = computed(() => state.shiftSummaries[0] || null)
</script>

<style scoped>
.overview-view {
  display: grid;
  grid-template-columns: minmax(310px, 1.02fr) minmax(410px, 1.38fr) minmax(300px, 0.92fr);
  gap: 14px;
  height: 100%;
  min-height: 0;
}

.overview-left { overflow: hidden; }
.ward-scroll {
  flex: 1 1 auto;
  min-height: 0;
  padding-right: 3px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.overview-center { overflow: hidden; }

.overview-rail {
  display: grid;
  grid-template-rows: auto minmax(210px, auto) minmax(0, 1fr);
  gap: 14px;
  min-width: 0;
  min-height: 0;
}

.shift-brief, .trend-panel, .activity-panel { overflow: hidden; }
.activity-panel { min-height: 0; }

.caption-link {
  margin-left: auto;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  text-decoration: none;
  white-space: nowrap;
  transition: opacity 0.15s ease;
}
.caption-link:hover { opacity: 0.8; }

.brief-text {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  color: var(--text-2);
  font-size: 12px;
  line-height: 1.6;
}
.brief-pills { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  background: rgba(24, 48, 76, 0.04);
  border: 1px solid var(--line);
  border-radius: 6px;
  font-size: 10.5px;
}
.pill i { color: var(--text-3); font-style: normal; font-weight: 600; }
.pill b { color: var(--text-2); font-weight: 800; }
.t-danger { color: var(--danger); }
.t-success { color: var(--success); }
.brief-empty { color: var(--text-3); font-size: 12px; padding: 10px 0; }

.view-empty {
  padding: 30px 0;
  text-align: center;
  color: var(--text-3);
  font-size: 12px;
}

/* 窄屏：两列，右栏横排 */
@media (max-width: 1280px) {
  .overview-view {
    grid-template-columns: minmax(300px, 1fr) minmax(390px, 1.25fr);
    grid-template-rows: minmax(0, 1fr) auto;
    overflow-y: auto;
  }
  .overview-rail {
    grid-column: 1 / -1;
    grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
    grid-template-rows: auto minmax(0, 1fr);
  }
  .shift-brief { grid-column: 1 / -1; }
}
@media (max-width: 820px) {
  .overview-view {
    display: flex;
    flex-direction: column;
    height: auto;
    min-height: 100%;
    overflow: visible;
  }
  .overview-center { order: 1; min-height: 480px; }
  .overview-left { order: 2; min-height: 620px; }
  .overview-rail { order: 3; display: flex; flex-direction: column; }
  .trend-panel, .activity-panel { min-height: 300px; }
}
</style>
