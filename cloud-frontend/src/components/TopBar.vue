<template>
  <header class="topbar-container">
    <div class="title-section">
      <span class="neon-dot"></span>
      <h1 class="main-title">智慧病房 · 护士站工作台</h1>
    </div>
    <div class="metrics-section">
      <div class="metric-tag">
        <span class="label">病区</span>
        <span class="value">{{ stats.total_wards || 0 }}</span>
      </div>
      <div class="metric-tag">
        <span class="label">床位</span>
        <span class="value">{{ stats.total_beds || 0 }}</span>
      </div>
      <div class="metric-tag" :class="{ alert: stats.online_nodes < stats.total_nodes }">
        <span class="label">节点</span>
        <span class="value">{{ stats.online_nodes || 0 }}/{{ stats.total_nodes || 0 }}</span>
      </div>
      <div class="metric-tag p1-urgent" v-if="stats.p1_pending > 0">
        <span class="pulse-ring"></span>
        <span class="label">P1 待处理</span>
        <span class="value">{{ stats.p1_pending }}</span>
      </div>
      <div class="time-tag">
        {{ currentTime }}
      </div>
    </div>
  </header>
</template>

<script setup>
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
</script>

<style scoped>
.topbar-container {
  background: rgba(15, 23, 42, 0.65);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
  z-index: 100;
  position: relative;
}

.topbar-container::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(79, 195, 247, 0.35), transparent);
}

.title-section {
  display: flex;
  align-items: center;
  gap: 10px;
}

.neon-dot {
  width: 8px;
  height: 8px;
  background: #00e5ff;
  border-radius: 50%;
  box-shadow: 0 0 10px #00e5ff, 0 0 20px rgba(0, 229, 255, 0.5);
  animation: heartbeat 2s infinite ease-in-out;
}

.main-title {
  font-size: 18px;
  font-weight: 700;
  color: #f8fafc;
  background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: 0.5px;
}

.metrics-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.metric-tag {
  display: flex;
  align-items: center;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  gap: 8px;
  box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.05);
}

.metric-tag .label {
  color: #64748b;
  font-weight: 500;
}

.metric-tag .value {
  color: #e2e8f0;
  font-weight: 700;
  font-family: 'Outfit', sans-serif;
}

.metric-tag.alert {
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.08);
}
.metric-tag.alert .label {
  color: #fca5a5;
}
.metric-tag.alert .value {
  color: #ef4444;
  text-shadow: 0 0 8px rgba(239, 68, 68, 0.3);
}

.p1-urgent {
  display: flex;
  align-items: center;
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.5);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  gap: 8px;
  position: relative;
  overflow: hidden;
}

.p1-urgent .label {
  color: #fca5a5;
  font-weight: 600;
}

.p1-urgent .value {
  color: #ffffff;
  font-weight: 800;
  font-family: 'Outfit', sans-serif;
  text-shadow: 0 0 8px rgba(255, 255, 255, 0.5);
}

.pulse-ring {
  width: 6px;
  height: 6px;
  background: #ef4444;
  border-radius: 50%;
  box-shadow: 0 0 8px #ef4444;
  animation: pulse-animation 1.5s infinite;
}

.time-tag {
  font-family: 'Outfit', sans-serif;
  font-size: 13px;
  color: #4fc3f7;
  font-weight: 600;
  background: rgba(79, 195, 247, 0.08);
  border: 1px solid rgba(79, 195, 247, 0.2);
  border-radius: 6px;
  padding: 4px 12px;
  text-shadow: 0 0 6px rgba(79, 195, 247, 0.2);
}

@keyframes heartbeat {
  0%, 100% { transform: scale(1); opacity: 0.9; }
  50% { transform: scale(1.25); opacity: 1; }
}

@keyframes pulse-animation {
  0% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7);
  }
  70% {
    transform: scale(1);
    box-shadow: 0 0 0 6px rgba(239, 68, 68, 0);
  }
  100% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
  }
}
</style>
