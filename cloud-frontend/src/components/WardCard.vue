<template>
  <div class="ward-card">
    <!-- 病区标题栏 -->
    <div class="ward-header">
      <div class="ward-title">
        <el-icon :size="15" class="ward-icon" aria-hidden="true"><OfficeBuilding /></el-icon>
        <span class="ward-name">{{ ward.name }}</span>
        <span class="ward-loc chip chip-ghost">{{ ward.location }}</span>
      </div>
      <div class="ward-stats">
        <span class="ward-stat">待处理
          <strong class="font-num" :class="ward.pending_alerts > 0 ? 't-danger' : ''">{{ ward.pending_alerts }}</strong>
        </span>
        <span class="stat-divider" aria-hidden="true"></span>
        <span class="ward-stat">监测节点
          <strong class="font-num">{{ ward.nodes ? ward.nodes.length : 0 }}</strong>
        </span>
      </div>
    </div>

    <!-- 床位网格 -->
    <div class="ward-bed-grid">
      <BedCard
        v-for="bed in ward.beds"
        :key="bed.id"
        :bed="bed"
        :latest-event="latestEventOf(bed.id)"
        :node-status="nodeStatusOf(bed.id)"
        :model-version="modelVersionOf(bed.id)"
        @show-monitor="(b) => $emit('showMonitor', b)"
      />
    </div>
  </div>
</template>

<script setup>
import BedCard from './BedCard.vue'

const props = defineProps({
  ward: { type: Object, required: true },
  // 病区事件列表（用于每个床位展示最新事件推理链路）
  events: { type: Array, default: () => [] },
})

defineEmits(['showMonitor'])

const latestEventOf = (bedId) => {
  const list = props.events.filter((e) => e.bed_id === bedId)
  return list.length ? list[0] : null
}

const nodeStatusOf = (bedId) => (props.ward.nodes || []).find((n) => n.bed_id === bedId)?.status || ''

const modelVersionOf = (bedId) =>
  (props.ward.nodes || []).find((n) => n.bed_id === bedId)?.model_version || ''
</script>

<style scoped>
.ward-card {
  padding: 12px;
  background: rgba(42, 125, 225, 0.03);
  border: 1px solid var(--line);
  border-radius: 12px;
}

.ward-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 11px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line);
}
.ward-title { display: flex; align-items: center; gap: 8px; min-width: 0; }
.ward-icon { color: var(--primary); flex: 0 0 auto; }
.ward-name { color: var(--text); font-size: 13.5px; font-weight: 800; white-space: nowrap; }

.ward-stats { display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.ward-stat { color: var(--text-3); font-size: 11.5px; font-weight: 600; }
.ward-stat strong { color: var(--text-2); font-weight: 800; }
.ward-stat strong.t-danger { color: var(--danger); }
.stat-divider { width: 1px; height: 11px; background: var(--line-strong); }

.ward-bed-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
  gap: 10px;
}

@media (max-width: 720px) {
  .ward-header { align-items: flex-start; flex-wrap: wrap; }
  .ward-stats { width: 100%; justify-content: flex-start; }
  .ward-bed-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
