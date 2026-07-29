<template>
  <div class="ward-clinical-section">
    <div class="ward-title-bar">
      <div class="title-left">
        <span class="ward-icon">🏥</span>
        <span class="ward-name-text">{{ ward.name }}</span>
        <span class="location-badge">{{ ward.location }}</span>
      </div>
      <div class="ward-stats-summary">
        <span>待处理: <strong :class="{ warn: ward.pending_alerts > 0 }">{{ ward.pending_alerts }}</strong></span>
        <span class="divider">|</span>
        <span>摄像头/传感器: <strong>{{ ward.nodes ? ward.nodes.length : 0 }}</strong></span>
      </div>
    </div>

    <div class="beds-clinical-grid">
      <BedCard v-for="bed in ward.beds" :key="bed.id" :bed="bed" />
    </div>
  </div>
</template>

<script setup>
import BedCard from './BedCard.vue'

defineProps({
  ward: {
    type: Object,
    required: true
  }
})
</script>

<style scoped>
.ward-clinical-section {
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.ward-title-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #1e293b;
}

.title-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ward-icon {
  font-size: 14px;
}

.ward-name-text {
  font-size: 14px;
  font-weight: 700;
  color: #38bdf8;
}

.location-badge {
  font-size: 10px;
  color: #94a3b8;
  background: #1e293b;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid #334155;
}

.ward-stats-summary {
  font-size: 11px;
  color: #94a3b8;
  display: flex;
  gap: 8px;
  align-items: center;
}

.ward-stats-summary strong {
  color: #f8fafc;
  font-family: 'Outfit', sans-serif;
}

.ward-stats-summary strong.warn {
  color: #ef4444;
}

.ward-stats-summary .divider {
  color: #334155;
}

.beds-clinical-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
}
</style>
