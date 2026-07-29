<template>
  <div class="card-item" :class="[bed.status, { alert: bed.pending_events > 0 }]">
    <!-- Neon Corner Tag -->
    <div class="card-indicator"></div>
    
    <div class="bed-title">{{ bed.name }}</div>
    <div class="patient-name" v-if="bed.patient_alias">{{ bed.patient_alias }}</div>
    <div class="patient-name none" v-else>无登记患者</div>
    
    <div class="status-badge" :class="bed.status">
      {{ bedStatusLabel(bed.status) }}
    </div>
    
    <!-- Urgent Alert Banner -->
    <div class="alarm-tag" v-if="bed.pending_events > 0">
      <span class="warning-icon">⚠️</span>
      <span>{{ bed.pending_events }} 起告警</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  bed: {
    type: Object,
    required: true
  }
})

const bedStatusLabel = (status) => {
  const map = {
    idle: '空闲',
    occupied: '在床',
    alert: '告警中',
    maintenance: '维护中'
  }
  return map[status] || status
}
</script>

<style scoped>
.card-item {
  background: rgba(26, 38, 57, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  padding: 10px 6px;
  text-align: center;
  position: relative;
  overflow: hidden;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.card-item:hover {
  transform: translateY(-3px) scale(1.02);
  border-color: rgba(79, 195, 247, 0.3);
  box-shadow: 0 10px 22px rgba(0, 0, 0, 0.4);
  background: rgba(30, 41, 59, 0.6);
}

/* Corner indicator defaults */
.card-indicator {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  background: #64748b; /* idle default */
  transition: all 0.3s ease;
}

/* Colors by state */
.card-item.occupied {
  border-bottom: 2px solid rgba(16, 185, 129, 0.2);
}
.card-item.occupied .card-indicator {
  background: #10b981;
}

.card-item.maintenance {
  border-bottom: 2px solid rgba(245, 158, 11, 0.15);
  opacity: 0.85;
}
.card-item.maintenance .card-indicator {
  background: #f59e0b;
}

.card-item.idle {
  opacity: 0.6;
}
.card-item.idle .card-indicator {
  background: #64748b;
}

/* P1 Alarm breathing neon state */
.card-item.alert {
  animation: blink-card 1.5s infinite;
  border: 1px solid #ef4444 !important;
  opacity: 1;
}

.card-item.alert .card-indicator {
  background: #ef4444;
  box-shadow: 0 1px 6px #ef4444;
}

.bed-title {
  font-family: 'Outfit', sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: #f8fafc;
}

.patient-name {
  font-size: 10px;
  font-weight: 600;
  color: #cbd5e1;
  max-width: 90%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.patient-name.none {
  color: #475569;
  font-weight: 400;
}

.status-badge {
  font-size: 9px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.4);
  color: #94a3b8;
}

.status-badge.occupied {
  color: #34d399;
  background: rgba(16, 185, 129, 0.1);
}
.status-badge.maintenance {
  color: #fbbf24;
  background: rgba(245, 158, 11, 0.08);
}
.status-badge.alert {
  color: #ff8a80;
  background: rgba(239, 68, 68, 0.12);
}

.alarm-tag {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 9px;
  color: #ff8a80;
  font-weight: 700;
  margin-top: 2px;
}

.warning-icon {
  animation: warning-shake 0.8s infinite alternate;
}

@keyframes warning-shake {
  0% { transform: rotate(-10deg); }
  100% { transform: rotate(10deg); }
}

@keyframes blink-card {
  0%, 100% {
    background: rgba(26, 38, 57, 0.45);
    box-shadow: none;
  }
  50% {
    background: rgba(239, 68, 68, 0.18);
    box-shadow: 0 0 15px rgba(239, 68, 68, 0.4);
  }
}
</style>
