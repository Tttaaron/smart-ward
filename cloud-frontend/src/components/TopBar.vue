<template>
  <header class="bg-med-surface border-b-2 border-med-border px-5 py-2.5 flex justify-between items-center shadow-card text-med-text z-50">
    <!-- 品牌 -->
    <div class="flex items-center gap-3">
      <div class="w-11 h-11 rounded-lg bg-med-primary/10 border border-med-primary/30 flex items-center justify-center text-2xl">
        🏥
      </div>
      <div class="flex flex-col">
        <h1 class="text-[17px] font-bold text-med-primary tracking-wide">第一人民医院 · 智慧病房</h1>
        <div class="text-[11px] text-med-text-2 font-medium mt-0.5">呼吸与危重症医学科 (W-01病区)</div>
      </div>
    </div>

    <!-- 值班信息 -->
    <div class="flex items-center gap-2.5 bg-med-surface-2 px-3.5 py-1.5 rounded-md border border-med-border text-xs">
      <div class="flex items-center gap-1.5">
        <span class="text-med-text-3">值班护士：</span>
        <span class="text-med-text font-semibold">张莉 (主管护师)</span>
      </div>
      <div class="text-med-border">|</div>
      <div class="flex items-center gap-1.5">
        <span class="text-med-text-3">责任医生：</span>
        <span class="text-med-text font-semibold">王主任</span>
      </div>
    </div>

    <!-- 指标区 -->
    <div class="flex items-center gap-2">
      <div class="flex flex-col items-center min-w-[65px] bg-med-surface-2 border border-med-border rounded-md px-3 py-1">
        <span class="text-[10px] text-med-text-3">总床位</span>
        <span class="text-sm font-bold font-num text-med-text">{{ stats.total_beds || 3 }}</span>
      </div>
      <div class="flex flex-col items-center min-w-[65px] bg-med-surface-2 border border-med-border rounded-md px-3 py-1">
        <span class="text-[10px] text-med-text-3">在床</span>
        <span class="text-sm font-bold font-num text-med-success">{{ stats.occupied_beds || 2 }}</span>
      </div>
      <div class="flex flex-col items-center min-w-[65px] bg-med-surface-2 border border-med-border rounded-md px-3 py-1">
        <span class="text-[10px] text-med-text-3">离床</span>
        <span class="text-sm font-bold font-num text-med-warning">{{ stats.leave_beds || 1 }}</span>
      </div>
      <div
        class="flex flex-col items-center min-w-[65px] bg-med-surface-2 border rounded-md px-3 py-1"
        :class="stats.online_nodes < stats.total_nodes ? 'border-med-warning/40 bg-med-warning/5' : 'border-med-border'"
      >
        <span class="text-[10px] text-med-text-3">监测节点</span>
        <span class="text-sm font-bold font-num text-med-primary">{{ stats.online_nodes || 0 }}/{{ stats.total_nodes || 0 }}</span>
      </div>
      <div
        v-if="stats.p1_pending > 0"
        class="flex flex-col items-center min-w-[65px] bg-med-danger/10 border border-med-danger/40 rounded-md px-3 py-1"
      >
        <span class="text-[10px] text-med-danger">P1特急</span>
        <span class="text-sm font-bold font-num text-med-danger" style="animation: med-text-pulse 1.2s infinite;">{{ stats.p1_pending }}</span>
      </div>
    </div>

    <!-- 时钟 -->
    <div class="text-right bg-med-surface-2 px-3 py-1.5 rounded-md border border-med-border">
      <div class="text-[10px] text-med-text-3">{{ currentDateStr }}</div>
      <div class="text-[15px] font-bold font-num text-med-primary">{{ currentTime }}</div>
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
