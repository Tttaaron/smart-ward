<template>
  <div class="ward-card-container">
    <div class="header-section">
      <div class="header-title">
        <span class="pulse-marker"></span>
        <span class="ward-name">{{ ward.name }}</span>
        <span class="location-tag">{{ ward.location }}</span>
      </div>
      <span class="status-indicator" :class="ward.status"></span>
    </div>
    
    <div class="beds-grid">
      <BedCard v-for="bed in ward.beds" :key="bed.id" :bed="bed" />
    </div>
    
    <div class="meta-section">
      <span class="meta-item warning" v-if="ward.pending_alerts > 0">
        待处理: <strong>{{ ward.pending_alerts }}</strong>
      </span>
      <span class="meta-item normal" v-else>
        无待处理告警
      </span>
      <span class="meta-item">
        监测节点: <strong>{{ ward.nodes ? ward.nodes.length : 0 }}</strong>
      </span>
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
.ward-card-container {
  background: rgba(30, 41, 59, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 10px;
  padding: 14px;
  transition: all 0.3s ease;
}

.ward-card-container:hover {
  border-color: rgba(79, 195, 247, 0.15);
  box-shadow: inset 0 0 10px rgba(79, 195, 247, 0.05);
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 6px;
}

.pulse-marker {
  width: 4px;
  height: 12px;
  background: #4fc3f7;
  border-radius: 2px;
  box-shadow: 0 0 6px #4fc3f7;
}

.ward-name {
  font-size: 13px;
  font-weight: 700;
  color: #f1f5f9;
}

.location-tag {
  font-size: 10px;
  color: #64748b;
  background: rgba(15, 23, 42, 0.3);
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.02);
}

.status-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #64748b;
}
.status-indicator.online {
  background: #10b981;
  box-shadow: 0 0 6px #10b981;
}

.beds-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
  gap: 8px;
}

.meta-section {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #64748b;
  margin-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.03);
  padding-top: 8px;
}

.meta-item strong {
  font-family: 'Outfit', sans-serif;
  color: #e2e8f0;
  font-weight: 600;
}

.meta-item.warning {
  color: #ff8a80;
}
.meta-item.warning strong {
  color: #ef4444;
  text-shadow: 0 0 6px rgba(239, 68, 68, 0.2);
}

.meta-item.normal {
  color: #475569;
}
</style>
