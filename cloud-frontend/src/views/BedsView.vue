<template>
  <div class="beds-view">
    <!-- 左：床位态势（大卡） -->
    <section class="panel acc-neutral beds-main">
      <div class="panel-caption">
        <span class="caption-index">01</span>
        <span class="caption-title">床位态势</span>
        <span class="caption-meta">{{ wardSummary }} · 共 {{ totalBeds }} 床</span>
      </div>
      <div class="beds-scroll">
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

    <!-- 右：节点心跳 + 节点列表 + 环境联动 -->
    <aside class="beds-side">
      <section class="panel acc-accent">
        <div class="panel-caption">
          <span class="caption-index">02</span>
          <span class="caption-title">节点心跳</span>
          <span class="caption-meta">10s 自动刷新</span>
        </div>
        <NodeLatencyChart :demo-mode="state.demoMode" :refresh-tick="state.refreshTick" />
      </section>

      <section class="panel acc-neutral node-list-panel">
        <div class="panel-caption">
          <span class="caption-index">03</span>
          <span class="caption-title">边缘节点</span>
          <span class="caption-meta">{{ state.nodes.length }} 台设备</span>
        </div>
        <ul v-if="state.nodes.length" class="node-list">
          <li v-for="node in state.nodes" :key="node.id" class="node-row">
            <span class="dot" :class="node.status" aria-hidden="true"></span>
            <span class="node-id mono">{{ node.id }}</span>
            <span class="chip chip-accent font-num">{{ node.bed_id }}床</span>
            <span class="node-model font-num">{{ node.model_version || '—' }}</span>
            <span v-if="node.buffered_events > 0" class="chip chip-warning font-num">缓存 {{ node.buffered_events }}</span>
            <span class="node-hb font-num">{{ heartbeatText(node) }}</span>
          </li>
        </ul>
        <div v-else class="view-empty">暂无节点数据</div>
      </section>

      <section class="panel acc-neutral activity-panel">
        <div class="panel-caption">
          <span class="caption-index">04</span>
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
import NodeLatencyChart from '../components/NodeLatencyChart.vue'
import ActivityLogPanel from '../components/ActivityLogPanel.vue'
import { useWardStore } from '../stores/ward.js'

const store = useWardStore()
const { state } = store

const wardSummary = computed(() => {
  const ward = state.wards[0]
  return ward ? `${ward.id} · ${ward.location}` : 'W-01'
})

const totalBeds = computed(() =>
  state.wards.reduce((acc, w) => acc + (w.beds?.length || 0), 0)
)

const heartbeatText = (node) => {
  if (!node.last_heartbeat) return '—'
  const sec = Math.max(0, Math.floor((Date.now() - new Date(node.last_heartbeat).getTime()) / 1000))
  return sec < 60 ? `${sec}s 前` : `${Math.floor(sec / 60)}min 前`
}
</script>

<style scoped>
.beds-view {
  display: grid;
  grid-template-columns: minmax(420px, 1.5fr) minmax(320px, 0.85fr);
  gap: 14px;
  height: 100%;
  min-height: 0;
}

.beds-main { overflow: hidden; }
.beds-scroll {
  flex: 1;
  min-height: 0;
  padding-right: 3px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.beds-side {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
}
.beds-side .panel { flex: 0 0 auto; }

.node-list-panel { overflow: hidden; }

.activity-panel { overflow: hidden; min-height: 300px; }
.node-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.node-row {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 10px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 9px;
}
.node-id { color: var(--text-2); font-size: 10.5px; font-weight: 700; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-model { color: var(--text-3); font-size: 10px; }
.node-hb { color: var(--text-3); font-size: 10px; font-weight: 700; margin-left: auto; }

.view-empty {
  padding: 26px 0;
  text-align: center;
  color: var(--text-3);
  font-size: 12px;
}

@media (max-width: 1020px) {
  .beds-view {
    display: flex;
    flex-direction: column;
    height: auto;
    min-height: 100%;
    overflow-y: auto;
  }
  .beds-main { min-height: 560px; }
}
</style>
