<template>
  <header class="topbar">
    <div class="title">智慧病房 · 护士站工作台</div>
    <div class="metrics">
      <span class="metric">病区 {{ stats.total_wards || 0 }}</span>
      <span class="metric">床位 {{ stats.total_beds || 0 }}</span>
      <span class="metric" :class="{ alert: stats.online_nodes < stats.total_nodes }">
        节点 {{ stats.online_nodes || 0 }}/{{ stats.total_nodes || 0 }}
      </span>
      <span class="metric p1" v-if="stats.p1_pending > 0">
        P1 待处理 {{ stats.p1_pending }}
      </span>
      <span class="metric">{{ currentTime }}</span>
    </div>
  </header>
</template>

<script setup>
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
</script>
