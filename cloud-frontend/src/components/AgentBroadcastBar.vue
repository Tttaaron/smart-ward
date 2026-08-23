<template>
  <div v-if="latest" class="broadcast-bar" :key="latest.text + latest.occurred_at">
    <span class="bb-badge">📢 边缘播报</span>
    <span class="bb-text">{{ latest.text }}</span>
    <span class="bb-meta">
      {{ bedLabel(latest.bed_id) }} · {{ latest.model?.mode || '' }}
      <span v-if="state.agentBroadcasts.length > 1"> · 累计 {{ state.agentBroadcasts.length }} 条</span>
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useWardStore } from '../stores/ward.js'

const store = useWardStore()
const { state } = store

const latest = computed(() => state.agentBroadcasts[0] || null)

const bedLabel = (bedId) => ({ B01: 'B01', B02: 'B02', B03: 'B03' }[bedId] || bedId || '')
</script>

<style scoped>
.broadcast-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 14px;
  background: linear-gradient(90deg, rgba(42, 125, 225, 0.12), rgba(42, 125, 225, 0.04));
  border-bottom: 1px solid var(--line);
  font-size: 12px;
  color: var(--text-2);
  overflow: hidden;
  white-space: nowrap;
}
.bb-badge {
  flex: 0 0 auto;
  padding: 2px 8px;
  font-size: 10.5px;
  font-weight: 800;
  color: var(--primary);
  background: rgba(42, 125, 225, 0.12);
  border-radius: 999px;
}
.bb-text { flex: 1; overflow: hidden; text-overflow: ellipsis; }
.bb-meta { flex: 0 0 auto; color: var(--text-3); font-size: 10px; font-weight: 600; }
</style>
