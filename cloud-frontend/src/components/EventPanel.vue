<template>
  <div class="events-panel-inner">
    <div class="panel-header-row">
      <h2>告警工作台</h2>
      <span class="count-badge">{{ events.length }}</span>
    </div>
    
    <div v-if="events.length === 0" class="empty-state">
      <div class="empty-icon">✓</div>
      <div class="empty-text">当前无待处理的安全事件</div>
    </div>
    
    <ul v-else class="event-list">
      <li 
        v-for="evt in events" 
        :key="evt.event_id" 
        class="event-card-item" 
        :class="[evt.priority, evt.state, { blink: evt.priority === 'P1' && ['new', 'notified'].includes(evt.state) }]"
      >
        <div class="event-header">
          <span class="priority-badge" :class="evt.priority">{{ evt.priority }}</span>
          <span class="event-title-text">{{ eventTypeLabel(evt.event_type) }}</span>
          <span class="state-label" :class="evt.state">{{ eventStateLabel(evt.state) }}</span>
        </div>
        
        <div class="event-meta-info">
          <span class="meta-field bed-id">{{ evt.bed_id }}</span>
          <span class="meta-divider">|</span>
          <span class="meta-field confidence">置信度: <strong class="num-font">{{ (evt.confidence * 100).toFixed(0) }}%</strong></span>
          <span class="meta-divider">|</span>
          <span class="meta-field time">{{ formatTime(evt.occurred_at) }}</span>
        </div>
        
        <div class="action-buttons-group" v-if="['new', 'notified', 'acknowledged'].includes(evt.state)">
          <!-- “到场”在处置中 (acknowledged) 状态时隐藏 -->
          <button v-if="evt.state !== 'acknowledged'" @click="$emit('ack', evt, 'acknowledge')" class="btn-pill btn-ack">
            到场
          </button>
          <button @click="$emit('ack', evt, 'resolve')" class="btn-pill btn-resolve">
            处置
          </button>
          <button @click="$emit('ack', evt, 'false_positive')" class="btn-pill btn-false">
            误报
          </button>
          <button @click="$emit('ack', evt, 'escalate')" class="btn-pill btn-escalate">
            升级
          </button>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
defineProps({
  events: {
    type: Array,
    required: true,
    default: () => []
  }
})

defineEmits(['ack'])

const eventTypeLabel = (t) => ({
  fall_suspected: '疑似跌倒',
  nurse_call: '护士呼叫',
  bed_leave: '离床',
  door_departure: '门区异常',
  night_wandering: '夜间徘徊',
  environment_anomaly: '环境异常',
  node_offline: '节点失联',
  fall_prediction: '坠床预警',
  long_still: '长时间静止',
  abnormal_posture: '异常体态',
  seizure: '抽搐检测',
  bedsore_risk: '压疮风险',
  device_fault: '设备故障',
}[t] || t)

const eventStateLabel = (s) => ({
  new: '未处理',
  notified: '已通知',
  acknowledged: '处置中',
  resolved: '已处置',
  false_positive: '误报',
  escalated: '已升级',
}[s] || s)

const formatTime = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
</script>

<style scoped>
.events-panel-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.count-badge {
  font-family: 'Outfit', sans-serif;
  color: #ff9e9e;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.25);
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 700;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #475569;
  padding: 40px 10px;
}

.empty-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 2px solid #334155;
  color: #334155;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  margin-bottom: 12px;
  background: rgba(15, 23, 42, 0.2);
}

.empty-text {
  font-size: 12px;
  font-weight: 500;
}

.event-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.event-card-item {
  background: rgba(30, 41, 59, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  padding: 12px 14px;
  border-left: 4px solid #10b981;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.event-card-item:hover {
  transform: translateY(-2px);
  border-color: rgba(255, 255, 255, 0.08);
  background: rgba(30, 41, 59, 0.4);
}

.event-card-item.P1 {
  border-left-color: #ef4444;
}

.event-card-item.P1.blink {
  animation: blink-border 1.2s infinite;
}

.event-card-item.P2 {
  border-left-color: #f59e0b;
}

.event-card-item.P3 {
  border-left-color: #3b82f6;
}

.event-card-item.resolved, .event-card-item.false_positive {
  opacity: 0.5;
  border-left-color: #64748b;
}

.event-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.priority-badge {
  font-family: 'Outfit', sans-serif;
  padding: 1px 7px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.priority-badge.P1 { background: rgba(239, 68, 68, 0.15); color: #ff8a80; border: 1px solid rgba(239, 68, 68, 0.25); }
.priority-badge.P2 { background: rgba(245, 158, 11, 0.12); color: #ffd180; border: 1px solid rgba(245, 158, 11, 0.2); }
.priority-badge.P3 { background: rgba(59, 130, 246, 0.12); color: #80d8ff; border: 1px solid rgba(59, 130, 246, 0.2); }

.event-title-text {
  font-weight: 700;
  font-size: 13px;
  color: #f1f5f9;
}

.state-label {
  margin-left: auto;
  font-size: 10px;
  color: #94a3b8;
  background: rgba(15, 23, 42, 0.45);
  padding: 1px 8px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.02);
  font-weight: 500;
}
.state-label.acknowledged {
  color: #ffd180;
  border-color: rgba(245, 158, 11, 0.15);
}
.state-label.resolved {
  color: #a7f3d0;
  border-color: rgba(16, 185, 129, 0.15);
}

.event-meta-info {
  font-size: 11px;
  color: #64748b;
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
}

.meta-divider {
  color: #334155;
}

.num-font {
  font-family: 'Outfit', sans-serif;
  color: #cbd5e1;
}

.action-buttons-group {
  margin-top: 10px;
  display: flex;
  gap: 6px;
}

.btn-pill {
  flex: 1;
  padding: 5px;
  background: rgba(30, 41, 59, 0.6);
  color: #94a3b8;
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 6px;
  cursor: pointer;
  font-size: 11px;
  font-weight: 700;
  transition: all 0.2s ease;
  outline: none;
}

.btn-pill:hover {
  background: rgba(79, 195, 247, 0.08);
  border-color: rgba(79, 195, 247, 0.3);
  color: #4fc3f7;
  transform: translateY(-0.5px);
}

.btn-pill.btn-ack {
  background: rgba(16, 185, 129, 0.08);
  border-color: rgba(16, 185, 129, 0.2);
  color: #34d399;
}
.btn-pill.btn-ack:hover {
  background: #10b981;
  color: #fff;
  border-color: #10b981;
  box-shadow: 0 4px 10px rgba(16, 185, 129, 0.25);
}

.btn-pill.btn-resolve:hover {
  background: #3b82f6;
  color: #fff;
  border-color: #3b82f6;
  box-shadow: 0 4px 10px rgba(59, 130, 246, 0.25);
}

@keyframes blink-border {
  50% { 
    border-left-color: transparent; 
    box-shadow: 0 0 12px rgba(239, 68, 68, 0.4); 
  }
}
</style>
