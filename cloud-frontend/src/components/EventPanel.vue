<template>
  <div class="events-panel-inner">
    <h2>告警工作台 <span class="count">{{ events.length }}</span></h2>
    <div v-if="events.length === 0" class="empty">暂无事件</div>
    <ul v-else class="event-list">
      <li v-for="evt in events" :key="evt.event_id" class="event-item" :class="[evt.priority, evt.state, { blink: evt.priority === 'P1' && ['new', 'notified'].includes(evt.state) }]">
        <div class="event-head">
          <span class="badge" :class="evt.priority">{{ evt.priority }}</span>
          <span class="event-type">{{ eventTypeLabel(evt.event_type) }}</span>
          <span class="state">{{ eventStateLabel(evt.state) }}</span>
        </div>
        <div class="event-meta">
          {{ evt.bed_id }} · 置信度 {{ (evt.confidence * 100).toFixed(0) }}% · {{ formatTime(evt.occurred_at) }}
        </div>
        <div class="event-actions" v-if="['new', 'notified', 'acknowledged'].includes(evt.state)">
          <!-- 确认后按钮应隐藏或禁用：“到场”在 acknowledged 状态时隐藏 -->
          <button v-if="evt.state !== 'acknowledged'" @click="$emit('ack', evt, 'acknowledge')" class="btn-ack">到场</button>
          <button @click="$emit('ack', evt, 'resolve')" class="btn-resolve">处置</button>
          <button @click="$emit('ack', evt, 'false_positive')" class="btn-false">误报</button>
          <button @click="$emit('ack', evt, 'escalate')" class="btn-escalate">升级</button>
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
  return new Date(iso).toLocaleTimeString('zh-CN')
}
</script>
