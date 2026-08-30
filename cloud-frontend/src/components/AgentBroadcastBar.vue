<template>
  <div v-if="latest" class="broadcast-bar" :key="latest.text + latest.occurred_at">
    <span class="bb-badge">
      <el-icon :size="12" aria-hidden="true"><Microphone /></el-icon>
      边缘播报
    </span>
    <span class="bb-text">{{ latest.text }}</span>
    <span class="bb-meta">
      {{ bedLabel(latest.bed_id) }} · {{ latest.model?.mode || '' }}
      <span v-if="state.agentBroadcasts.length > 1"> · 累计 {{ state.agentBroadcasts.length }} 条</span>
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Microphone } from '@element-plus/icons-vue'
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
  font-size: 12.5px;
  color: var(--text-2);
  overflow: hidden;
  white-space: nowrap;
}
.bb-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex: 0 0 auto;
  padding: 3px 9px;
  font-size: var(--fs-micro);
  font-weight: 800;
  color: var(--primary);
  background: rgba(42, 125, 225, 0.12);
  border: 1px solid rgba(42, 125, 225, 0.28);
  border-radius: 999px;
  white-space: nowrap;
}
.bb-text { flex: 1; overflow: hidden; text-overflow: ellipsis; font-size: var(--fs-body); }
.bb-meta { flex: 0 0 auto; color: var(--text-3); font-size: var(--fs-caption); font-weight: 600; }
</style>
