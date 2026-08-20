<template>
  <div class="status-bar-wrap">
    <!-- 恢复横幅：断网恢复时短暂展示 -->
    <transition name="banner">
      <div v-if="recoveryBanner" class="status-banner recovery" :class="{ 'dismissing': bannerDismissing }">
        <el-icon class="banner-icon" :size="17" aria-hidden="true"><CircleCheckFilled /></el-icon>
        <div class="banner-body">
          <div class="banner-title">云端链路已恢复</div>
          <div class="banner-detail">
            恢复时间 {{ fmtTime(wsStatus.connectedAt) }} · 累计重连 {{ wsStatus.reconnectCount }} 次 ·
            离线缓存补传 <strong>{{ stats.buffered_events ?? '—' }}</strong> 条
          </div>
        </div>
        <button class="banner-close" @click="dismissBanner">✕</button>
      </div>
    </transition>

    <!-- 断网横幅：云端不可用且重连中 -->
    <transition name="banner">
      <div v-if="offlineBanner && !recoveryBanner" class="status-banner offline">
        <el-icon class="banner-icon" :size="17" aria-hidden="true"><WarningFilled /></el-icon>
        <div class="banner-body">
          <div class="banner-title">云端链路中断 · 边缘继续本地值守</div>
          <div class="banner-detail">
            重连中（第 {{ wsStatus.reconnectCount }} 次尝试）· 事件本地缓存，网络恢复后自动补传
          </div>
        </div>
      </div>
    </transition>

    <!-- 常驻状态条 -->
    <div class="status-bar" :class="{ degraded: cloudDegraded }">
      <div class="status-chip" :class="wsChipClass" :title="wsTooltip">
        <span class="chip-dot"></span>
        <span class="chip-label">云端链路</span>
        <span class="chip-value">{{ wsChipText }}</span>
      </div>

      <div class="status-chip" :class="apiChipClass" :title="apiTooltip">
        <span class="chip-dot"></span>
        <span class="chip-label">云端 API</span>
        <span class="chip-value">{{ apiChipText }}</span>
      </div>

      <div class="status-chip" :class="nodeChipClass">
        <span class="chip-dot"></span>
        <span class="chip-label">边缘节点</span>
        <span class="chip-value">{{ onlineNodes }}/{{ totalNodes }} 在线</span>
      </div>

      <div class="status-chip" :class="heartbeatChipClass" :title="heartbeatTooltip">
        <span class="chip-dot"></span>
        <span class="chip-label">节点心跳</span>
        <span class="chip-value">{{ heartbeatText }}</span>
      </div>

      <div v-if="bufferedCount > 0" class="status-chip warn">
        <span class="chip-dot"></span>
        <span class="chip-label">离线缓存</span>
        <span class="chip-value">{{ bufferedCount }} 条待补传</span>
      </div>

      <div class="status-chip" :class="mqttChipClass">
        <span class="chip-dot"></span>
        <span class="chip-label">MQTT</span>
        <span class="chip-value">{{ mqttChipText }}</span>
      </div>

      <div
        v-if="demoMode"
        class="status-chip demo-chip"
        :title="presentationFallback ? '检测到历史累计告警异常，已启用比赛展示保护' : '云端不可用，当前使用前端演示数据'"
      >
        <span class="chip-dot"></span>
        <span class="chip-label">数据源</span>
        <span class="chip-value">演示</span>
      </div>

      <div v-if="wsStatus.disconnectedAt" class="status-chip dim">
        <span class="chip-label">最近断开</span>
        <span class="chip-value">{{ fmtTime(wsStatus.disconnectedAt) }}</span>
      </div>

      <div class="status-chip dim ml-auto">
        <span class="chip-label">WS 消息</span>
        <span class="chip-value">{{ totalMsg }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { fmtTime } from '../utils/eventMeta.js'

const props = defineProps({
  wsStatus: { type: Object, default: () => ({}) },
  stats: { type: Object, default: () => ({}) },
  nodes: { type: Array, default: () => [] },
  apiHealthy: { type: Boolean, default: true },
  demoMode: { type: Boolean, default: false },
  presentationFallback: { type: Boolean, default: false },
})

const recoveryBanner = ref(false)
const bannerDismissing = ref(false)
let bannerTimer = null

// ---- 状态派生 ----
// 云端链路综合判定：REST 健康轮询（5 秒）+ WebSocket 连接态双信号。
const wsStatusValue = computed(() => props.wsStatus.status || 'disconnected')
const apiDown = computed(() => !props.apiHealthy)
const cloudDegraded = computed(() =>
  apiDown.value || ['reconnecting', 'disconnected'].includes(wsStatusValue.value)
)

const wsChipText = computed(() => {
  if (apiDown.value) return '不可用'
  return {
    connected: '在线',
    connecting: '连接中',
    reconnecting: `重连${props.wsStatus.reconnectCount}次`,
    disconnected: '离线',
  }[wsStatusValue.value] || '未知'
})

const wsChipClass = computed(() => {
  if (apiDown.value) return 'err'
  return {
    connected: 'ok',
    connecting: 'warn',
    reconnecting: 'warn',
    disconnected: 'err',
  }[wsStatusValue.value] || 'dim'
})

const wsTooltip = computed(() => {
  if (apiDown.value) return '云端后端无响应（REST 健康探测失败）'
  return wsStatusValue.value === 'connected'
    ? `连接成功于 ${fmtTime(props.wsStatus.connectedAt)}`
    : wsStatusValue.value === 'reconnecting'
      ? `第 ${props.wsStatus.reconnectCount} 次重连，采用指数退避`
      : '云端 WebSocket 链路断开'
})

const apiChipText = computed(() => (props.apiHealthy ? '正常' : '不可用'))
const apiChipClass = computed(() => (props.apiHealthy ? 'ok' : 'err'))
const apiTooltip = computed(() => (props.apiHealthy ? 'REST 查询接口响应正常' : 'REST 查询接口无响应'))

const totalNodes = computed(() => props.stats.total_nodes || props.nodes.length || 0)
const onlineNodes = computed(() => props.stats.online_nodes ?? props.nodes.filter((n) => n.status === 'online').length)
const nodeChipClass = computed(() => (onlineNodes.value === totalNodes.value && totalNodes.value > 0 ? 'ok' : 'warn'))

// ---- 节点心跳检测（MQTT 链路健康） ----
const HEARTBEAT_STALE_MS = 45000
const nowTick = ref(Date.now())
const heartbeatTimer = setInterval(() => { nowTick.value = Date.now() }, 5000)
onUnmounted(() => clearInterval(heartbeatTimer))

const heartbeatStaleCount = computed(() => {
  if (props.demoMode) return 0
  return props.nodes.filter((n) => {
    if (!n.last_heartbeat) return n.status !== 'offline'
    return nowTick.value - new Date(n.last_heartbeat).getTime() > HEARTBEAT_STALE_MS
  }).length
})
const heartbeatHealthy = computed(() => totalNodes.value - heartbeatStaleCount.value)
const heartbeatText = computed(() =>
  totalNodes.value === 0 ? '—' : `${heartbeatHealthy.value}/${totalNodes.value} 正常`
)
const heartbeatChipClass = computed(() => {
  if (totalNodes.value === 0) return 'dim'
  if (heartbeatStaleCount.value === totalNodes.value) return 'err'
  if (heartbeatStaleCount.value > 0) return 'warn'
  return 'ok'
})
const heartbeatTooltip = computed(() =>
  heartbeatStaleCount.value > 0
    ? `${heartbeatStaleCount.value} 个节点心跳超过 ${HEARTBEAT_STALE_MS / 1000}s 未更新，疑似 MQTT 链路中断`
    : '所有边缘节点心跳正常'
)

const bufferedCount = computed(() => {
  const fromStats = props.stats.buffered_events ?? 0
  const fromNodes = props.nodes.reduce((acc, n) => acc + (n.buffered_events || 0), 0)
  return Math.max(fromStats, fromNodes)
})

const mqttChipText = computed(() => {
  if (props.apiHealthy && props.nodes.some((n) => n.status === 'online')) return '在线'
  if (props.apiHealthy) return '已连接'
  return '未知'
})
const mqttChipClass = computed(() => (mqttChipText.value === '未知' ? 'dim' : 'ok'))

const totalMsg = computed(() =>
  Object.values(props.wsStatus.messageCount || {}).reduce((a, b) => a + b, 0)
)

const offlineBanner = computed(() => cloudDegraded.value)

// ---- 恢复横幅：监听云端链路从"降级" -> "正常" ----
watch(cloudDegraded, (now, prev) => {
  if (prev === true && now === false) showRecoveryBanner()
})

const showRecoveryBanner = () => {
  recoveryBanner.value = true
  bannerDismissing.value = false
  clearTimeout(bannerTimer)
  bannerTimer = setTimeout(() => {
    bannerDismissing.value = true
    setTimeout(() => {
      recoveryBanner.value = false
      bannerDismissing.value = false
    }, 600)
  }, 6000)
}

const dismissBanner = () => {
  clearTimeout(bannerTimer)
  bannerDismissing.value = true
  setTimeout(() => {
    recoveryBanner.value = false
    bannerDismissing.value = false
  }, 300)
}
</script>

<style scoped>
.status-bar-wrap {
  position: relative;
  z-index: 40;
}

.status-bar {
  display: flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  padding: 5px 16px;
  background: rgba(255, 255, 255, 0.88);
  border-bottom: 1px solid var(--line);
  flex-wrap: nowrap;
  overflow-x: auto;
  scrollbar-width: none;
  transition: background 0.3s;
}
.status-bar::-webkit-scrollbar { display: none; }
.status-bar.degraded { background: rgba(255, 247, 232, 0.95); }

.status-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 24px;
  padding: 0 9px;
  background: rgba(24, 48, 76, 0.04);
  border: 1px solid var(--line);
  border-radius: 12px;
  font-size: 11px;
  white-space: nowrap;
  flex: 0 0 auto;
}
.chip-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-3);
}
.status-chip.ok .chip-dot { background: var(--success); box-shadow: 0 0 6px rgba(22, 163, 74, 0.5); }
.status-chip.warn .chip-dot { background: var(--warning); box-shadow: 0 0 6px rgba(217, 119, 6, 0.5); }
.status-chip.err .chip-dot { background: var(--danger); box-shadow: 0 0 7px rgba(220, 38, 38, 0.55); animation: med-blink 1.1s infinite; }
.chip-label { color: var(--text-3); font-weight: 600; }
.chip-value { color: var(--text-2); font-weight: 700; }
.status-chip.err .chip-value { color: var(--danger); }
.status-chip.warn .chip-value { color: var(--warning); }
.status-chip.ok .chip-value { color: var(--success); }
.demo-chip { background: var(--warning-soft); border-color: rgba(217, 119, 6, 0.32); }
.demo-chip .chip-dot { background: var(--warning); box-shadow: 0 0 6px rgba(217, 119, 6, 0.5); }
.demo-chip .chip-value { color: var(--warning); }
.ml-auto { margin-left: auto; }

/* ---- 横幅 ---- */
.status-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  font-size: 12px;
  border-left: 3px solid transparent;
}
.status-banner.recovery {
  background: #EAF9F0;
  border-bottom: 1px solid rgba(22, 163, 74, 0.22);
  border-left-color: var(--success);
  color: var(--text);
}
.status-banner.offline {
  background: #FDF0EE;
  border-bottom: 1px solid rgba(220, 38, 38, 0.20);
  border-left-color: var(--danger);
  color: var(--text);
}
.banner-icon { color: var(--success); flex: 0 0 auto; }
.status-banner.offline .banner-icon { color: var(--danger); }
.banner-title { font-weight: 800; }
.banner-detail { color: var(--text-2); font-size: 11px; margin-top: 1px; }
.banner-detail strong { color: var(--text); }
.banner-close {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--text-3);
  font-size: 14px;
  cursor: pointer;
}
.banner-close:hover { color: var(--text); }
.status-banner.dismissing { opacity: 0; transition: opacity 0.6s; }

.banner-enter-active, .banner-leave-active { transition: all 0.4s; }
.banner-enter-from, .banner-leave-to { opacity: 0; transform: translateY(-8px); }

@media (max-width: 720px) {
  .status-bar { padding-inline: 10px; }
  .status-chip { padding-inline: 8px; }
  .status-chip.ml-auto { margin-left: 0; }
  .status-banner { padding-inline: 10px; }
}
</style>
