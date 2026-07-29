<template>
  <div class="shift-panel-inner">
    <h2>交接班摘要</h2>
    <div class="shift-form">
      <input :value="shiftDate" @input="$emit('update:shiftDate', $event.target.value)" type="date" class="shift-input" />
      <select :value="shiftPeriod" @change="$emit('update:shiftPeriod', $event.target.value)" class="shift-input">
        <option value="day">白班 (08:00 - 16:00)</option>
        <option value="evening">晚班 (16:00 - 24:00)</option>
        <option value="night">夜班 (00:00 - 08:00)</option>
      </select>
      <button @click="$emit('generate')" :disabled="generating">
        {{ generating ? '生成中...' : '生成摘要' }}
      </button>
    </div>
    <div v-if="shiftSummaries.length === 0" class="empty">暂无摘要</div>
    <ul v-else class="summary-list">
      <li v-for="s in shiftSummaries" :key="s.id" class="summary-item">
        <div class="summary-head">
          <span class="summary-date">{{ s.shift_date }} {{ periodLabel(s.shift_period) }}</span>
          <span class="summary-counts">{{ s.event_count }} 事件</span>
        </div>
        <div class="summary-text">{{ s.summary_text }}</div>
        <div class="summary-meta">
          P1 {{ s.p1_count }} · P2 {{ s.p2_count }} · 已处置 {{ s.resolved_count }} · 误报 {{ s.false_positive_count }}
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
defineProps({
  shiftSummaries: {
    type: Array,
    required: true,
    default: () => []
  },
  generating: {
    type: Boolean,
    required: true,
    default: false
  },
  shiftDate: {
    type: String,
    required: true
  },
  shiftPeriod: {
    type: String,
    required: true
  }
})

defineEmits(['update:shiftDate', 'update:shiftPeriod', 'generate'])

const periodLabel = (p) => ({ day: '白班', evening: '晚班', night: '夜班' }[p] || p)
</script>
