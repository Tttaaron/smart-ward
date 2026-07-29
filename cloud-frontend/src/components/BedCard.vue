<template>
  <div class="bed-card" :class="[bed.status, { alert: bed.pending_events > 0 }]">
    <div class="bed-name">{{ bed.name }}</div>
    <div class="bed-alias" v-if="bed.patient_alias">{{ bed.patient_alias }}</div>
    <div class="bed-status">{{ bedStatusLabel(bed.status) }}</div>
    <div class="bed-pending" v-if="bed.pending_events > 0">{{ bed.pending_events }} 待处理</div>
  </div>
</template>

<script setup>
defineProps({
  bed: {
    type: Object,
    required: true
  }
})

const bedStatusLabel = (status) => {
  const map = {
    idle: '空闲',
    occupied: '在床',
    alert: '告警中',
    maintenance: '维护中'
  }
  return map[status] || status
}
</script>
