<template>
  <div class="ward-card">
    <div class="ward-header">{{ ward.name }}（{{ ward.location }}）</div>
    <div class="beds">
      <BedCard v-for="bed in ward.beds" :key="bed.id" :bed="bed" />
    </div>
    <div class="ward-meta">
      <span>待处理告警 {{ ward.pending_alerts }}</span>
      <span>节点 {{ ward.nodes ? ward.nodes.length : 0 }}</span>
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
</script>
