<template>
  <div class="system-view">
    <!-- 链路状态卡 -->
    <div class="link-row">
      <div class="link-card" :class="wsTone">
        <span class="dot" :class="wsDot" aria-hidden="true"></span>
        <div class="link-copy">
          <span class="link-label">云端链路 · WebSocket</span>
          <strong class="link-value">{{ wsText }}</strong>
        </div>
      </div>
      <div class="link-card" :class="state.apiHealthy ? 'ok' : 'err'">
        <span class="dot" :class="state.apiHealthy ? 'online' : 'alert'" aria-hidden="true"></span>
        <div class="link-copy">
          <span class="link-label">云端 API · REST</span>
          <strong class="link-value">{{ state.apiHealthy ? '响应正常' : '无响应' }}</strong>
        </div>
      </div>
      <div class="link-card" :class="nodeTone">
        <span class="dot" :class="nodeDot" aria-hidden="true"></span>
        <div class="link-copy">
          <span class="link-label">边缘节点</span>
          <strong class="link-value">{{ onlineNodes }}/{{ totalNodes }} 在线</strong>
        </div>
      </div>
      <div class="link-card ok">
        <span class="dot online" aria-hidden="true"></span>
        <div class="link-copy">
          <span class="link-label">MQTT Broker</span>
          <strong class="link-value">已连接</strong>
        </div>
      </div>
      <div class="link-card" :class="state.demoMode ? 'warn' : 'ok'">
        <span class="dot" :class="state.demoMode ? 'warn' : 'online'" aria-hidden="true"></span>
        <div class="link-copy">
          <span class="link-label">数据源</span>
          <strong class="link-value">{{ state.demoMode ? '前端演示数据' : '实时链路' }}</strong>
        </div>
      </div>
    </div>

    <!-- 模型版本 + 服务拓扑 -->
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

        <!-- 病区信息 -->
        <section class="panel acc-neutral ward-info">
          <div class="panel-caption">
            <span class="caption-index">08</span>
            <span class="caption-title">病区信息</span>
            <span class="caption-meta">W-01</span>
          </div>
          <div class="ward-rows">
            <div class="ward-row"><span>病区名称</span><strong>{{ wardInfo?.name || '普通病房 W-01' }}</strong></div>
            <div class="ward-row"><span>位置</span><strong>{{ wardInfo?.location || '三楼东侧' }}</strong></div>
            <div class="ward-row"><span>床位</span><strong class="font-num">{{ totalBeds }} 张</strong></div>
            <div class="ward-row"><span>值守护士</span><strong>{{ STAFF.onDuty.name }} ({{ STAFF.onDuty.role }})</strong></div>
            <div class="ward-row"><span>责任医生</span><strong>{{ STAFF.doctor.name }}</strong></div>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ModelManage from '../components/ModelManage.vue'
import { useWardStore } from '../stores/ward.js'
import { STAFF } from '../mock/wardProfile.js'

const store = useWardStore()
const { state } = store

const wardInfo = computed(() => state.wards[0] || null)
const totalBeds = computed(() =>
  state.wards.reduce((acc, w) => acc + (w.beds?.length || 0), 0)
)
const totalNodes = computed(() => state.stats.total_nodes || state.nodes.length || 0)
const onlineNodes = computed(
  () => state.stats.online_nodes ?? state.nodes.filter((n) => n.status === 'online').length
)

// ---- 链路状态派生 ----
const wsText = computed(() => {
  if (!state.apiHealthy) return '不可用'
  const map = {
    connected: '在线',
    connecting: '连接中',
    reconnecting: `重连 ${state.wsStatus.reconnectCount} 次`,
    disconnected: '离线',
  }
  return map[state.wsStatus.status] || '未知'
})
const wsDot = computed(() => {
  if (!state.apiHealthy) return 'alert'
  if (state.wsStatus.status === 'connected') return 'online'
  if (['connecting', 'reconnecting'].includes(state.wsStatus.status)) return 'warn'
  return 'offline'
})
const wsTone = computed(() => {
  if (!state.apiHealthy) return 'err'
  if (state.wsStatus.status === 'connected') return 'ok'
  if (['connecting', 'reconnecting'].includes(state.wsStatus.status)) return 'warn'
  return 'err'
})

const nodeTone = computed(
  () => (totalNodes.value > 0 && onlineNodes.value === totalNodes.value ? 'ok' : 'warn')
)
const nodeDot = computed(
  () => (totalNodes.value > 0 && onlineNodes.value === totalNodes.value ? 'online' : 'warn')
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

/* 链路状态卡 */
.link-row {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  flex: 0 0 auto;
}
.link-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 13px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 11px;
  box-shadow: var(--shadow-panel), inset 0 1px 0 rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(14px);
}
.link-card.ok { border-color: rgba(52, 211, 153, 0.25); }
.link-card.warn { border-color: rgba(251, 191, 36, 0.3); }
.link-card.err { border-color: rgba(220, 38, 38, 0.3); }
.link-copy { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.link-label { color: var(--text-3); font-size: 10.5px; font-weight: 700; white-space: nowrap; }
.link-value { color: var(--text); font-size: 13.5px; font-weight: 800; white-space: nowrap; }
.link-card.err .link-value { color: var(--danger); }
.link-card.warn .link-value { color: var(--warning); }
.link-card.ok .link-value { color: var(--success); }

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

/* 病区信息 */
.ward-rows { display: flex; flex-direction: column; gap: 7px; }
.ward-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 11px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 9px;
  font-size: 11.5px;
}
.ward-row span { color: var(--text-3); font-weight: 600; }
.ward-row strong { color: var(--text); font-weight: 700; }

@media (max-width: 1280px) {
  .link-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 1020px) {
  .sys-grid {
    display: flex;
    flex-direction: column;
  }
  .sys-models { min-height: 340px; }
}
@media (max-width: 640px) {
  .link-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
