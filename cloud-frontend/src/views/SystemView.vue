<template>
  <div class="system-view">
    <div class="sys-grid">
      <section class="panel acc-neutral sys-models">
        <div class="panel-caption">
          <span class="caption-index">06</span>
          <span class="caption-title">模型版本</span>
          <span class="caption-meta">边缘推理 · 发布与下发</span>
        </div>
        <ModelManage embedded :demo-mode="state.demoMode" />
      </section>

      <aside class="sys-side">
        <!-- 服务拓扑 -->
        <section class="panel acc-accent topo-panel">
          <div class="panel-caption">
            <span class="caption-index">07</span>
            <span class="caption-title">服务拓扑</span>
            <span class="caption-meta">云边协同链路</span>
          </div>
          <ul class="topo-list">
            <li v-for="svc in services" :key="svc.name" class="topo-row">
              <span class="dot" :class="svc.tone" aria-hidden="true"></span>
              <span class="topo-name">{{ svc.name }}</span>
              <span class="topo-port mono">{{ svc.port }}</span>
              <span class="topo-desc">{{ svc.desc }}</span>
            </li>
          </ul>
        </section>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ModelManage from '../components/ModelManage.vue'
import { useWardStore } from '../stores/ward.js'

const store = useWardStore()
const { state } = store

const totalNodes = computed(() => state.stats.total_nodes || state.nodes.length || 0)
const onlineNodes = computed(
  () => state.stats.online_nodes ?? state.nodes.filter((n) => n.status === 'online').length
)

// 服务拓扑（端口为宿主机映射；边缘节点状态来自实时数据）
const services = computed(() => [
  {
    name: '云端事件中心', port: ':8001', desc: 'FastAPI · REST + WS',
    tone: state.apiHealthy ? 'online' : 'alert',
  },
  {
    name: '云 LLM 研判', port: ':8005', desc: 'Qwen2.5-14B · 二次研判',
    tone: state.apiHealthy ? 'online' : 'offline',
  },
  {
    name: '边缘节点 ×3', port: 'MQTT', desc: '本地推理 · 离线缓存',
    tone: onlineNodes.value === totalNodes.value && totalNodes.value > 0 ? 'online' : 'warn',
  },
  {
    name: '训练协调器', port: ':8002', desc: '联邦学习调度',
    tone: 'idle',
  },
  {
    name: '扩散服务', port: ':8003', desc: '合成数据集生成',
    tone: 'idle',
  },
])
</script>

<style scoped>
.system-view {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  min-height: 0;
  overflow-y: auto;
}

/* 主体两列 */
.sys-grid {
  display: grid;
  grid-template-columns: minmax(380px, 1.15fr) minmax(320px, 0.85fr);
  gap: 14px;
  flex: 1;
  min-height: 0;
}
.sys-models { overflow: hidden; }
.sys-models :deep(.model-manage-embedded) { overflow-y: auto; }

.sys-side {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
}

/* 服务拓扑 */
.topo-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.topo-row {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 11px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 9px;
}
.topo-name { color: var(--text); font-size: 12px; font-weight: 700; white-space: nowrap; }
.topo-port { color: var(--primary); font-size: 10px; font-weight: 700; }
.topo-desc { margin-left: auto; color: var(--text-3); font-size: 10px; font-weight: 600; white-space: nowrap; }

@media (max-width: 1020px) {
  .sys-grid {
    display: flex;
    flex-direction: column;
  }
  .sys-models { min-height: 340px; }
}
</style>
