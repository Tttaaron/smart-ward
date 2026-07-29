<template>
  <div class="bg-med-surface-2 border border-med-border rounded-lg p-3 mb-3">
    <!-- 病区标题栏 -->
    <div class="flex justify-between items-center mb-2.5 pb-2 border-b border-med-border">
      <div class="flex items-center gap-2">
        <span class="text-sm">🏥</span>
        <span class="text-sm font-bold text-med-primary">{{ ward.name }}</span>
        <span class="text-[10px] text-med-text-3 bg-med-surface px-1.5 py-0.5 rounded border border-med-border">{{ ward.location }}</span>
      </div>
      <div class="text-[11px] text-med-text-2 flex gap-2 items-center">
        <span>待处理: <strong class="font-num" :class="ward.pending_alerts > 0 ? 'text-med-danger' : 'text-med-text'">{{ ward.pending_alerts }}</strong></span>
        <span class="text-med-border">|</span>
        <span>摄像头/传感器: <strong class="font-num text-med-text">{{ ward.nodes ? ward.nodes.length : 0 }}</strong></span>
      </div>
    </div>

    <!-- 床位网格 -->
    <div class="grid gap-2.5" style="grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));">
      <BedCard v-for="bed in ward.beds" :key="bed.id" :bed="bed" @show-monitor="(b) => $emit('showMonitor', b)" />
    </div>
  </div>
</template>

<script setup>
import BedCard from './BedCard.vue'

defineProps({
  ward: {
    type: Object,
    required: true
  }
})

defineEmits(['showMonitor'])
</script>
