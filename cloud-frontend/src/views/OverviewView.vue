<template>
  <div class="overview-view">
    <!-- 左列：床位态势 -->
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
</template>

<script setup>
import { computed } from 'vue'
import WardCard from '../components/WardCard.vue'
import EventPanel from '../components/EventPanel.vue'
import { useWardStore } from '../stores/ward.js'

const store = useWardStore()
const { state } = store

const wardSummary = computed(() => {
  const ward = state.wards[0]
  return ward ? `${ward.id} · ${ward.location}` : 'W-01'
})
</script>

<style scoped>
.overview-view {
  display: grid;
  grid-template-columns: minmax(340px, 1fr) minmax(420px, 1.5fr);
  gap: 14px;
  height: 100%;
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
  font-size: 12px;
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
}
</style>
