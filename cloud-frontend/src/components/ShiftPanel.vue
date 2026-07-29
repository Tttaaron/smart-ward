<template>
  <div class="flex flex-col h-full min-h-0">
    <!-- 标题 -->
    <div class="mb-2.5 pb-1.5 border-b border-med-border">
      <h2 class="text-[15px] font-bold text-med-primary m-0 mb-1">病区护理交接班记录</h2>
      <div class="text-[11px] text-med-text-3">
        交接责任护士：<strong class="text-med-text">张莉 (主管护师)</strong>
      </div>
    </div>

    <!-- 表单 -->
    <div class="bg-med-surface-2 border border-med-border rounded-md p-2.5 mb-2.5 flex flex-col gap-2">
      <div class="flex gap-1.5">
        <el-date-picker
          :model-value="shiftDate"
          @update:model-value="$emit('update:shiftDate', $event)"
          type="date"
          size="small"
          format="YYYY-MM-DD"
          value-format="YYYY-MM-DD"
          class="flex-1"
        />
        <el-select
          :model-value="shiftPeriod"
          @update:model-value="$emit('update:shiftPeriod', $event)"
          size="small"
          class="flex-1"
        >
          <el-option value="day" label="白班 (08:00 - 16:00)" />
          <el-option value="evening" label="晚班 (16:00 - 24:00)" />
          <el-option value="night" label="夜班 (00:00 - 08:00)" />
        </el-select>
      </div>
      <el-button
        type="primary"
        :loading="generating"
        @click="$emit('generate')"
        class="w-full !font-bold"
      >
        {{ generating ? '正在归纳班次数据...' : '📋 生成临床护理交接摘要' }}
      </el-button>
    </div>

    <!-- 空状态 -->
    <el-empty v-if="shiftSummaries.length === 0" description="暂无选定日期的护理交接记录" :image-size="56" />

    <!-- 交接记录列表 -->
    <ul v-else class="list-none flex flex-col gap-2 overflow-y-auto flex-1">
      <li
        v-for="s in shiftSummaries"
        :key="s.id"
        class="report-card bg-med-surface-2 border border-med-border rounded-md p-2.5 flex flex-col gap-1.5"
      >
        <div class="flex justify-between items-center">
          <span class="text-xs font-bold text-med-primary">{{ s.shift_date }} · {{ periodLabel(s.shift_period) }}交接</span>
          <span class="text-[10px] text-med-text-3 bg-med-surface px-1.5 py-0.5 rounded">{{ s.event_count }} 起护理事件</span>
        </div>

        <div class="text-[11.5px] leading-relaxed text-med-text">{{ s.summary_text }}</div>

        <div class="flex gap-1.5 flex-wrap text-[10px]">
          <span class="m-pill px-1.5 py-0.5 rounded bg-med-surface"><span class="text-med-text-3">P1特急:</span> <strong class="text-med-danger font-num">{{ s.p1_count }}</strong></span>
          <span class="m-pill px-1.5 py-0.5 rounded bg-med-surface"><span class="text-med-text-3">P2高级:</span> <strong class="text-med-warning font-num">{{ s.p2_count }}</strong></span>
          <span class="m-pill px-1.5 py-0.5 rounded bg-med-surface"><span class="text-med-text-3">已处置:</span> <strong class="text-med-success font-num">{{ s.resolved_count }}</strong></span>
          <span class="m-pill px-1.5 py-0.5 rounded bg-med-surface"><span class="text-med-text-3">误报:</span> <strong class="text-med-info font-num">{{ s.false_positive_count }}</strong></span>
        </div>

        <div class="text-[10px] text-med-text-3 flex justify-between border-t border-dashed border-med-border pt-1 mt-0.5">
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
.report-card {
  border-left-width: 3.5px;
  border-left-color: #1677ff;
}
</style>
