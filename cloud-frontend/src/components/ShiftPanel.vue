<template>
  <div class="shift-panel-inner">
    <h2>交接班摘要</h2>
    
    <div class="shift-form-card">
      <div class="input-group">
        <input 
          :value="shiftDate" 
          @input="$emit('update:shiftDate', $event.target.value)" 
          type="date" 
          class="shift-input date-input" 
        />
        <select 
          :value="shiftPeriod" 
          @change="$emit('update:shiftPeriod', $event.target.value)" 
          class="shift-input select-input"
        >
          <option value="day">白班 (08-16点)</option>
          <option value="evening">晚班 (16-24点)</option>
          <option value="night">夜班 (00-08点)</option>
        </select>
      </div>
      <button 
        @click="$emit('generate')" 
        :disabled="generating" 
        class="btn-generate"
      >
        <span class="sparkle" v-if="!generating">✨</span>
        <span>{{ generating ? '生成中...' : '生成班次摘要' }}</span>
      </button>
    </div>
    
    <div v-if="shiftSummaries.length === 0" class="empty-state">
      <div class="empty-icon">📝</div>
      <div class="empty-text">当前日期无班次摘要记录</div>
    </div>
    
    <ul v-else class="summary-list">
      <li v-for="s in shiftSummaries" :key="s.id" class="summary-item">
        <div class="summary-head">
          <span class="summary-date">{{ s.shift_date }} · {{ periodLabel(s.shift_period) }}</span>
          <span class="summary-counts">{{ s.event_count }} 起事件</span>
        </div>
        <div class="summary-text">{{ s.summary_text }}</div>
        <div class="summary-meta">
          <span class="meta-dot p1">P1: {{ s.p1_count }}</span>
          <span class="meta-dot p2">P2: {{ s.p2_count }}</span>
          <span class="meta-dot ok">已处置: {{ s.resolved_count }}</span>
          <span class="meta-dot false">误报: {{ s.false_positive_count }}</span>
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

<style scoped>
.shift-panel-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.shift-form-card {
  background: rgba(30, 41, 59, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.input-group {
  display: flex;
  gap: 6px;
}

.shift-input {
  flex: 1;
  background: rgba(15, 23, 42, 0.5);
  color: #f1f5f9;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 4px;
  padding: 6px 8px;
  font-size: 11px;
  outline: none;
  font-family: inherit;
  transition: all 0.2s ease;
}

.shift-input:focus {
  border-color: rgba(79, 195, 247, 0.4);
  box-shadow: 0 0 6px rgba(79, 195, 247, 0.15);
}

.select-input option {
  background: #1a2942;
  color: #f1f5f9;
}

.btn-generate {
  width: 100%;
  padding: 6px 14px;
  background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.25s ease;
  box-shadow: 0 4px 8px rgba(30, 64, 175, 0.25);
}

.btn-generate:hover:not(:disabled) {
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.45);
  transform: translateY(-0.5px);
}

.btn-generate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sparkle {
  animation: sparkle-rotate 2s infinite linear;
}

@keyframes sparkle-rotate {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #475569;
  padding: 30px 10px;
}

.empty-icon {
  font-size: 24px;
  margin-bottom: 8px;
}

.empty-text {
  font-size: 12px;
  font-weight: 500;
}

.summary-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-item {
  background: rgba(30, 41, 59, 0.2);
  border-radius: 6px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.03);
  border-left: 3.5px solid #38bdf8;
}

.summary-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.summary-date {
  font-size: 11px;
  font-weight: 700;
  color: #38bdf8;
}

.summary-counts {
  font-size: 9px;
  color: #94a3b8;
  background: rgba(15, 23, 42, 0.4);
  padding: 1px 6px;
  border-radius: 8px;
  font-family: 'Outfit', sans-serif;
  font-weight: 600;
}

.summary-text {
  font-size: 11.5px;
  line-height: 1.5;
  color: #cbd5e1;
  margin-bottom: 8px;
  word-break: break-all;
}

.summary-meta {
  font-size: 10px;
  color: #64748b;
  border-top: 1px dashed rgba(255, 255, 255, 0.05);
  padding-top: 6px;
  margin-top: 4px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-dot {
  position: relative;
  padding-left: 10px;
}

.meta-dot::before {
  content: '';
  position: absolute;
  left: 0;
  top: 3.5px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #cbd5e1;
}

.meta-dot.p1::before { background: #ef4444; }
.meta-dot.p2::before { background: #f59e0b; }
.meta-dot.ok::before { background: #10b981; }
.meta-dot.false::before { background: #64748b; }
</style>
