<template>
  <div class="clinical-shift-panel">
    <div class="shift-header">
      <h2>病区护理交接班记录</h2>
      <div class="nurse-sign-tag">
        交接责任护士：<strong>张莉 (主管护师)</strong>
      </div>
    </div>

    <div class="shift-form-box">
      <div class="form-row">
        <input 
          :value="shiftDate" 
          @input="$emit('update:shiftDate', $event.target.value)" 
          type="date" 
          class="clin-input date" 
        />
        <select 
          :value="shiftPeriod" 
          @change="$emit('update:shiftPeriod', $event.target.value)" 
          class="clin-input select"
        >
          <option value="day">白班 (08:00 - 16:00)</option>
          <option value="evening">晚班 (16:00 - 24:00)</option>
          <option value="night">夜班 (00:00 - 08:00)</option>
        </select>
      </div>
      <button 
        @click="$emit('generate')" 
        :disabled="generating" 
        class="btn-generate-clinical"
      >
        <span>{{ generating ? '正在归纳班次数据...' : '📋 生成临床护理交接摘要' }}</span>
      </button>
    </div>

    <div v-if="shiftSummaries.length === 0" class="shift-empty">
      暂无选定日期的护理交接记录
    </div>

    <ul v-else class="shift-reports-list">
      <li v-for="s in shiftSummaries" :key="s.id" class="report-card">
        <div class="report-head">
          <span class="report-title">{{ s.shift_date }} · {{ periodLabel(s.shift_period) }}交接</span>
          <span class="event-total-badge">{{ s.event_count }} 起护理事件</span>
        </div>
        
        <div class="report-text">{{ s.summary_text }}</div>

        <div class="report-metrics-row">
          <span class="m-pill p1">P1特急: {{ s.p1_count }}</span>
          <span class="m-pill p2">P2高级: {{ s.p2_count }}</span>
          <span class="m-pill ok">已处置: {{ s.resolved_count }}</span>
          <span class="m-pill false">误报: {{ s.false_positive_count }}</span>
        </div>

        <div class="report-sign-footer">
          <span>交班人: 张莉 (签名确认)</span>
          <span>接班人: 李秀 (签名确认)</span>
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
.clinical-shift-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.shift-header {
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #1e293b;
}

.shift-header h2 {
  font-size: 15px;
  font-weight: 700;
  color: #38bdf8;
  margin: 0 0 4px 0;
}

.nurse-sign-tag {
  font-size: 11px;
  color: #94a3b8;
}

.nurse-sign-tag strong {
  color: #f1f5f9;
}

.shift-form-box {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-row {
  display: flex;
  gap: 6px;
}

.clin-input {
  flex: 1;
  background: #0f172a;
  color: #f8fafc;
  border: 1px solid #334155;
  border-radius: 4px;
  padding: 5px 8px;
  font-size: 11px;
  outline: none;
  font-family: inherit;
}

.clin-input:focus {
  border-color: #0284c7;
}

.btn-generate-clinical {
  width: 100%;
  padding: 6px;
  background: #0284c7;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-generate-clinical:hover:not(:disabled) {
  background: #0369a1;
}

.btn-generate-clinical:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.shift-empty {
  font-size: 11px;
  color: #64748b;
  text-align: center;
  padding: 30px 10px;
}

.shift-reports-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}

.report-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-left: 3.5px solid #38bdf8;
  border-radius: 6px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.report-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.report-title {
  font-size: 12px;
  font-weight: 700;
  color: #38bdf8;
}

.event-total-badge {
  font-size: 10px;
  color: #94a3b8;
  background: #0f172a;
  padding: 1px 6px;
  border-radius: 4px;
}

.report-text {
  font-size: 11.5px;
  line-height: 1.5;
  color: #cbd5e1;
}

.report-metrics-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 10px;
}

.m-pill {
  padding: 1px 5px;
  border-radius: 3px;
  background: #0f172a;
}

.m-pill.p1 { color: #fca5a5; }
.m-pill.p2 { color: #fde047; }
.m-pill.ok { color: #a7f3d0; }
.m-pill.false { color: #94a3b8; }

.report-sign-footer {
  font-size: 10px;
  color: #64748b;
  display: flex;
  justify-content: space-between;
  border-top: 1px dashed #334155;
  padding-top: 4px;
  margin-top: 2px;
}
</style>
