<template>
  <div class="shift-panel">
    <!-- 表单 -->
    <div class="shift-form">
      <el-date-picker
        :model-value="shiftDate"
        @update:model-value="$emit('update:shiftDate', $event)"
        type="date"
        size="small"
        format="YYYY-MM-DD"
        value-format="YYYY-MM-DD"
        class="form-date"
      />
      <el-select
        :model-value="shiftPeriod"
        @update:model-value="$emit('update:shiftPeriod', $event)"
        size="small"
        class="form-period"
      >
        <el-option value="day" label="白班 (08:00 - 16:00)" />
        <el-option value="evening" label="晚班 (16:00 - 24:00)" />
        <el-option value="night" label="夜班 (00:00 - 08:00)" />
      </el-select>
      <el-button
        type="primary"
        :loading="generating"
        class="generate-btn"
        @click="$emit('generate')"
      >
        <el-icon v-if="!generating" :size="14" aria-hidden="true"><DocumentChecked /></el-icon>
        {{ generating ? '正在归纳班次数据...' : '生成交接摘要' }}
      </el-button>
    </div>

    <!-- 空状态 -->
    <div v-if="shiftSummaries.length === 0" class="shift-empty">
      <el-icon :size="30" aria-hidden="true"><Document /></el-icon>
      <p>暂无选定日期的护理交接记录</p>
    </div>

    <!-- 交接记录列表 -->
    <ul v-else class="shift-list">
      <li v-for="s in shiftSummaries" :key="s.id" class="shift-card">
        <div class="shift-card-head">
          <span class="shift-period">{{ s.shift_date }} · {{ periodLabel(s.shift_period) }}交接</span>
          <span class="chip chip-ghost font-num">{{ s.event_count }} 起护理事件</span>
          <button
            @click.stop="$emit('delete-summary', s.id)"
            class="shift-delete"
            title="删除摘要"
            aria-label="删除摘要"
          >
            <el-icon :size="13" aria-hidden="true"><Close /></el-icon>
          </button>
        </div>

        <div class="shift-text">{{ s.summary_text }}</div>

        <div class="shift-pills">
          <span class="pill"><i>P1特急</i><b class="font-num t-danger">{{ s.p1_count }}</b></span>
          <span class="pill"><i>P2高级</i><b class="font-num t-warning">{{ s.p2_count }}</b></span>
          <span class="pill"><i>已处置</i><b class="font-num t-success">{{ s.resolved_count }}</b></span>
          <span class="pill"><i>误报</i><b class="font-num t-info">{{ s.false_positive_count }}</b></span>
        </div>

        <div class="shift-sign">
          <span>交班人：{{ STAFF.onDuty.name }}（签名确认）</span>
          <span>接班人：{{ STAFF.successor }}（签名确认）</span>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { Close } from '@element-plus/icons-vue'
import { STAFF } from '../mock/wardProfile.js'

defineProps({
  shiftSummaries: { type: Array, required: true, default: () => [] },
  generating: { type: Boolean, required: true, default: false },
  shiftDate: { type: String, required: true },
  shiftPeriod: { type: String, required: true },
})

defineEmits(['update:shiftDate', 'update:shiftPeriod', 'generate', 'delete-summary'])

const periodLabel = (p) => ({ day: '白班', evening: '晚班', night: '夜班' }[p] || p)
</script>

<style scoped>
.shift-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  gap: 12px;
}

.shift-form {
  display: flex;
  gap: 8px;
  flex: 0 0 auto;
  padding: 10px;
  background: rgba(42, 125, 225, 0.04);
  border: 1px solid var(--line);
  border-radius: 10px;
}
.form-date { width: 138px; }
.form-period { flex: 1; min-width: 0; }
.generate-btn { flex: 0 0 auto; font-weight: 700; }

.shift-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 30px 0 10px;
  color: var(--text-3);
  font-size: 12.5px;
}
.shift-empty :deep(.el-icon) { color: var(--primary); opacity: 0.55; }

.shift-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
  list-style: none;
  flex: 1;
  min-height: 0;
  padding-right: 3px;
  overflow-y: auto;
}

.shift-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 11px 12px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-left: 3px solid var(--primary);
  border-radius: 10px;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}
.shift-card:hover {
  border-color: var(--line-strong);
  border-left-color: var(--primary);
  box-shadow: 0 0 14px rgba(42, 125, 225, 0.08);
}

.shift-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.shift-period { color: var(--primary); font-size: 12.5px; font-weight: 800; flex: 1; }
.shift-delete {
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--text-3);
  font-size: 11.5px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.shift-delete:hover {
  color: var(--danger);
  background: var(--danger-soft);
  border-color: rgba(220, 38, 38, 0.35);
}

.shift-text {
  color: var(--text-2);
  font-size: 12.5px;
  line-height: 1.65;
}

.shift-pills { display: flex; flex-wrap: wrap; gap: 6px; }
.pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  background: rgba(24, 48, 76, 0.04);
  border: 1px solid var(--line);
  border-radius: 6px;
  font-size: 12px;
}
.pill i { color: var(--text-3); font-style: normal; font-weight: 600; }
.pill b { font-weight: 800; }
.t-danger { color: var(--danger); }
.t-warning { color: var(--warning); }
.t-success { color: var(--success); }
.t-info { color: var(--info); }

.shift-sign {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding-top: 7px;
  border-top: 1px dashed var(--line);
  color: var(--text-3);
  font-size: 11.5px;
  font-weight: 600;
}

@media (max-width: 640px) {
  .shift-form { flex-wrap: wrap; }
  .form-date { flex: 1; width: auto; }
  .generate-btn { width: 100%; }
}
</style>
