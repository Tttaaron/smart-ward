<template>
  <header class="hospital-topbar">
    <div class="brand-section">
      <div class="hospital-logo">🏥</div>
      <div class="brand-text">
        <h1 class="hospital-name">第一人民医院 · 智慧病房</h1>
        <div class="sub-dept">呼吸与危重症医学科 (W-01病区)</div>
      </div>
    </div>

    <div class="duty-section">
      <div class="duty-item">
        <span class="duty-label">值班护士：</span>
        <span class="duty-value">张莉 (主管护师)</span>
      </div>
      <div class="duty-divider">|</div>
      <div class="duty-item">
        <span class="duty-label">责任医生：</span>
        <span class="duty-value">王主任</span>
      </div>
    </div>

    <div class="metrics-section">
      <div class="metric-box">
        <span class="m-label">总床位</span>
        <span class="m-value font-num">{{ stats.total_beds || 3 }}</span>
      </div>
      <div class="metric-box success">
        <span class="m-label">在床</span>
        <span class="m-value font-num">{{ stats.occupied_beds || 2 }}</span>
      </div>
      <div class="metric-box warning">
        <span class="m-label">离床</span>
        <span class="m-value font-num">{{ stats.leave_beds || 1 }}</span>
      </div>
      <div class="metric-box info" :class="{ alert: stats.online_nodes < stats.total_nodes }">
        <span class="m-label">监测节点</span>
        <span class="m-value font-num">{{ stats.online_nodes || 0 }}/{{ stats.total_nodes || 0 }}</span>
      </div>
      <div class="metric-box urgent" v-if="stats.p1_pending > 0">
        <span class="m-label">P1特急</span>
        <span class="m-value font-num">{{ stats.p1_pending }}</span>
      </div>
    </div>

    <div class="clock-section">
      <div class="clock-date">{{ currentDateStr }}</div>
      <div class="clock-time font-num">{{ currentTime }}</div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'

defineProps({
  stats: {
    type: Object,
    required: true,
    default: () => ({})
  },
  currentTime: {
    type: String,
    required: true,
    default: ''
  }
})

const currentDateStr = computed(() => {
  const d = new Date()
  const weekDays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day} ${weekDays[d.getDay()]}`
})
</script>

<style scoped>
.hospital-topbar {
  background: #0f172a;
  border-bottom: 2px solid #1e293b;
  padding: 10px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  color: #f8fafc;
  z-index: 100;
}

.brand-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hospital-logo {
  font-size: 26px;
  background: #1e293b;
  width: 44px;
  height: 44px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #334155;
}

.brand-text {
  display: flex;
  flex-direction: column;
}

.hospital-name {
  font-size: 17px;
  font-weight: 700;
  color: #38bdf8;
  letter-spacing: 0.5px;
}

.sub-dept {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
  margin-top: 2px;
}

.duty-section {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #1e293b;
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid #334155;
  font-size: 12px;
}

.duty-label {
  color: #94a3b8;
}

.duty-value {
  color: #e2e8f0;
  font-weight: 600;
}

.duty-divider {
  color: #475569;
}

.metrics-section {
  display: flex;
  align-items: center;
  gap: 8px;
}

.metric-box {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 4px 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 65px;
}

.m-label {
  font-size: 10px;
  color: #94a3b8;
}

.m-value {
  font-size: 14px;
  font-weight: 700;
  color: #f8fafc;
}

.metric-box.success .m-value {
  color: #10b981;
}

.metric-box.warning .m-value {
  color: #f59e0b;
}

.metric-box.info .m-value {
  color: #38bdf8;
}

.metric-box.urgent {
  background: rgba(220, 38, 38, 0.15);
  border-color: rgba(220, 38, 38, 0.4);
}

.metric-box.urgent .m-label {
  color: #fca5a5;
}

.metric-box.urgent .m-value {
  color: #ef4444;
  animation: pulse-text 1.2s infinite;
}

.clock-section {
  text-align: right;
  background: #1e293b;
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid #334155;
}

.clock-date {
  font-size: 10px;
  color: #94a3b8;
}

.clock-time {
  font-size: 15px;
  font-weight: 700;
  color: #38bdf8;
}

.font-num {
  font-family: 'Outfit', sans-serif;
}

@keyframes pulse-text {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
