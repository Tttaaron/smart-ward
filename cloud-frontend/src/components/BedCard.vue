<template>
  <div class="bed-headboard" :class="[bed.status, { alert: bed.pending_events > 0 }]">
    <!-- Top Row: Bed ID + Nursing Care Level -->
    <div class="card-top-row">
      <div class="bed-no">{{ bed.name }}</div>
      <div class="care-level-badge" :class="careLevelClass">
        {{ careLevelText }}
      </div>
    </div>

    <!-- Patient Main Info -->
    <div class="patient-main-info">
      <div class="patient-name-age" v-if="bed.patient_alias">
        <span class="p-name">{{ bed.patient_alias }}</span>
        <span class="p-meta">({{ genderAgeText }})</span>
      </div>
      <div class="patient-name-age empty" v-else>
        空床 (无加床登记)
      </div>
    </div>

    <!-- Medical Staff Info -->
    <div class="staff-info">
      <span>责护: {{ nurseName }}</span>
      <span>主管: {{ doctorName }}</span>
    </div>

    <!-- Patient Risk Badges -->
    <div class="risk-tags-container">
      <span v-for="tag in riskTags" :key="tag.text" class="risk-tag" :class="tag.type">
        {{ tag.text }}
      </span>
    </div>

    <!-- Bottom Status Indicator -->
    <div class="card-bottom-bar">
      <span class="status-dot" :class="bed.status"></span>
      <span class="status-label">{{ bedStatusLabel(bed.status) }}</span>
      <span class="pending-alarm-count" v-if="bed.pending_events > 0">
        ⚠️ {{ bed.pending_events }}起待处理
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  bed: {
    type: Object,
    required: true
  }
})

// Nursing care level mapping based on bed ID for clinical demo
const careLevelText = computed(() => {
  if (props.bed.id === 'B01') return '特级护理'
  if (props.bed.id === 'B02') return 'Ⅰ级护理'
  return 'Ⅱ级护理'
})

const careLevelClass = computed(() => {
  if (props.bed.id === 'B01') return 'level-special'
  if (props.bed.id === 'B02') return 'level-1'
  return 'level-2'
})

const genderAgeText = computed(() => {
  if (props.bed.id === 'B01') return '男, 68岁'
  if (props.bed.id === 'B02') return '女, 74岁'
  return '男, 59岁'
})

const nurseName = computed(() => {
  if (props.bed.id === 'B01') return '张莉'
  if (props.bed.id === 'B02') return '李秀'
  return '王婷'
})

const doctorName = computed(() => {
  if (props.bed.id === 'B01') return '王主任'
  if (props.bed.id === 'B02') return '陈医师'
  return '刘医师'
})

const riskTags = computed(() => {
  if (props.bed.id === 'B01') return [
    { text: '防跌倒', type: 'danger' },
    { text: '防压疮', type: 'warning' },
    { text: '禁食', type: 'info' }
  ]
  if (props.bed.id === 'B02') return [
    { text: '防跌倒', type: 'danger' },
    { text: '高龄', type: 'info' }
  ]
  return [
    { text: '防坠床', type: 'warning' }
  ]
})

const bedStatusLabel = (status) => {
  const map = {
    idle: '空闲',
    occupied: '在床',
    alert: '告警/呼叫中',
    maintenance: '设备维护'
  }
  return map[status] || status
}
</script>

<style scoped>
.bed-headboard {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: relative;
  transition: all 0.2s ease;
}

.bed-headboard:hover {
  border-color: #38bdf8;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.bed-headboard.alert {
  border-color: #ef4444 !important;
  background: rgba(220, 38, 38, 0.15) !important;
  animation: clinical-alert-pulse 1.2s infinite;
}

.card-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #334155;
  padding-bottom: 6px;
}

.bed-no {
  font-family: 'Outfit', sans-serif;
  font-size: 15px;
  font-weight: 800;
  color: #f8fafc;
}

.care-level-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}

.care-level-badge.level-special {
  background: rgba(220, 38, 38, 0.2);
  color: #fca5a5;
  border: 1px solid rgba(220, 38, 38, 0.4);
}

.care-level-badge.level-1 {
  background: rgba(217, 119, 6, 0.2);
  color: #fde047;
  border: 1px solid rgba(217, 119, 6, 0.4);
}

.care-level-badge.level-2 {
  background: rgba(2, 132, 199, 0.2);
  color: #7dd3fc;
  border: 1px solid rgba(2, 132, 199, 0.4);
}

.patient-main-info {
  margin-top: 2px;
}

.patient-name-age {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.p-name {
  font-size: 13px;
  font-weight: 700;
  color: #f1f5f9;
}

.p-meta {
  font-size: 11px;
  color: #94a3b8;
}

.patient-name-age.empty {
  font-size: 11px;
  color: #64748b;
  font-style: italic;
}

.staff-info {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #94a3b8;
  background: #0f172a;
  padding: 3px 6px;
  border-radius: 4px;
}

.risk-tags-container {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  min-height: 20px;
}

.risk-tag {
  font-size: 9px;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 3px;
}

.risk-tag.danger {
  background: rgba(220, 38, 38, 0.15);
  color: #fca5a5;
  border: 1px solid rgba(220, 38, 38, 0.3);
}

.risk-tag.warning {
  background: rgba(217, 119, 6, 0.15);
  color: #fde047;
  border: 1px solid rgba(217, 119, 6, 0.3);
}

.risk-tag.info {
  background: rgba(2, 132, 199, 0.15);
  color: #7dd3fc;
  border: 1px solid rgba(2, 132, 199, 0.3);
}

.card-bottom-bar {
  display: flex;
  align-items: center;
  font-size: 11px;
  margin-top: 2px;
  padding-top: 4px;
  border-top: 1px dashed #334155;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 6px;
}

.status-dot.occupied { background: #10b981; box-shadow: 0 0 6px #10b981; }
.status-dot.idle { background: #64748b; }
.status-dot.maintenance { background: #f59e0b; }
.status-dot.alert { background: #ef4444; box-shadow: 0 0 8px #ef4444; }

.status-label {
  font-weight: 600;
  color: #cbd5e1;
}

.pending-alarm-count {
  margin-left: auto;
  font-size: 10px;
  color: #ef4444;
  font-weight: 700;
}

@keyframes clinical-alert-pulse {
  0%, 100% { box-shadow: 0 0 0 rgba(239, 68, 68, 0); }
  50% { box-shadow: 0 0 12px rgba(239, 68, 68, 0.4); }
}
</style>
