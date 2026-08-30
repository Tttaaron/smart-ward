<template>
  <div class="overview-view">
    <!-- 病区运行指标带 -->
    <MetricStrip :items="metrics" />

    <!-- 主体两列：床位态势 + 护理告警 -->
    <div class="overview-body">
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
      </section>

      <!-- 右列：护理告警（全量队列在「告警中心」） -->
      <section class="panel acc-danger overview-center">
        <div class="panel-caption">
          <span class="caption-index">02</span>
          <span class="caption-title">护理告警</span>
          <span class="caption-meta">优先级队列 · 实时处置</span>
        </div>
        <EventPanel
          :events="state.events"
          :limit="8"
          @ack="store.onAck"
          @show-monitor="store.openMonitorFromEvent"
          @open-detail="store.openDetail"
        />
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import MetricStrip from '../components/MetricStrip.vue'
import WardCard from '../components/WardCard.vue'
import EventPanel from '../components/EventPanel.vue'
import {
  Monitor, WarningFilled, DataLine, Connection, Timer,
} from '@element-plus/icons-vue'
import { useWardStore } from '../stores/ward.js'

const store = useWardStore()
const { state } = store

const wardSummary = computed(() => {
  const ward = state.wards[0]
  return ward ? `${ward.id} · ${ward.location}` : 'W-01'
})

const dash = (v) => (v == null ? '—' : v)

const metrics = computed(() => {
  const s = state.stats || {}
  const online = Number(s.online_nodes) || 0
  const total = Number(s.total_nodes) || 0
  const nodesDegraded = total > 0 && online < total

  return [
    {
      key: 'beds',
      label: '在床 / 总床位',
      value: `${dash(s.occupied_beds)} / ${dash(s.total_beds)}`,
      hint: '床垫传感',
      icon: Monitor,
      tone: 'primary',
    },
    {
      key: 'p1',
      label: 'P1 待处置',
      value: dash(s.p1_pending),
      hint: '需立即到场',
      icon: WarningFilled,
      tone: Number(s.p1_pending) > 0 ? 'danger' : 'success',
    },
    {
      key: 'leave',
      label: '离床告警',
      value: dash(s.leave_beds),
      hint: '近 24 小时',
      icon: Timer,
      tone: Number(s.leave_beds) > 0 ? 'warning' : 'neutral',
    },
    {
      key: 'today',
      label: '今日事件',
      value: dash(s.events_today),
      hint: '全病区累计',
      icon: DataLine,
      tone: 'accent',
    },
    {
      key: 'nodes',
      label: '在线节点',
      value: total > 0 ? `${online} / ${total}` : '—',
      hint: '边缘代理',
      icon: Connection,
      tone: nodesDegraded ? 'warning' : 'success',
    },
  ]
})
</script>

<style scoped>
.overview-view {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  min-height: 0;
}

.overview-body {
  display: grid;
  grid-template-columns: minmax(340px, 1fr) minmax(420px, 1.5fr);
  gap: 14px;
  flex: 1;
  min-height: 0;
}

.overview-left, .overview-center { overflow: hidden; }

.ward-scroll {
  flex: 1 1 auto;
  min-height: 0;
  padding-right: 3px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.view-empty {
  padding: 30px 0;
  text-align: center;
  color: var(--text-3);
  font-size: var(--fs-body);
}

@media (max-width: 820px) {
  .overview-view {
    height: auto;
    min-height: 100%;
    overflow-y: auto;
  }
  .overview-body {
    display: flex;
    flex-direction: column;
  }
  .overview-center { order: 1; min-height: 480px; }
  .overview-left { order: 2; min-height: 620px; }
}
</style>
