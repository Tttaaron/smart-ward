<template>
  <section class="chart-panel node-latency-panel" aria-labelledby="node-latency-title">
    <header class="chart-header">
      <div class="chart-heading">
        <div class="chart-kicker">
          <el-icon class="chart-kicker-icon"><Connection /></el-icon>
          <span>设备网络</span>
          <span class="chart-kicker-separator">/</span>
          <span>实时监测</span>
        </div>
        <h3 id="node-latency-title" class="chart-title">边缘节点心跳</h3>
      </div>

      <div class="chart-actions">
        <span class="chart-summary" :class="{ 'is-muted': !nodeSummary.total }">
          <span class="summary-dot" :class="{ 'is-muted': !nodeSummary.total }"></span>
          {{ nodeSummary.total ? `${nodeSummary.online}/${nodeSummary.total} 在线` : '等待节点' }}
        </span>
        <el-button
          class="chart-refresh-button"
          size="small"
          text
          :loading="loading"
          aria-label="刷新节点延迟"
          title="刷新节点延迟"
          @click="fetchData"
        >
          <el-icon v-if="!loading"><Refresh /></el-icon>
          <span>刷新</span>
        </el-button>
      </div>
    </header>

    <div class="latency-legend" aria-label="节点延迟状态说明">
      <span class="legend-item"><i class="legend-dot is-good"></i>正常 &lt; 5s</span>
      <span class="legend-item"><i class="legend-dot is-watch"></i>关注 5-15s</span>
      <span class="legend-item"><i class="legend-dot is-danger"></i>离线 / &gt; 15s</span>
    </div>

    <div class="chart-body">
      <div v-show="loading" class="chart-state-overlay" role="status" aria-live="polite">
        <el-icon class="state-icon is-loading"><Loading /></el-icon>
        <span>正在同步节点状态</span>
      </div>
      <div v-show="!loading && hasNoData" class="chart-state-overlay" role="status">
        <el-icon class="state-icon"><Connection /></el-icon>
        <strong>暂无节点数据</strong>
        <span>节点上线后将显示心跳延迟</span>
      </div>
      <div
        ref="chartDom"
        class="chart-canvas"
        :class="{ 'is-obscured': loading || hasNoData }"
        role="img"
        aria-label="边缘节点心跳延迟柱状图"
      ></div>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Connection, Loading, Refresh } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import api from '../api/index.js'

const props = defineProps({
  demoMode: {
    type: Boolean,
    default: false,
  },
})

const loading = ref(false)
const hasNoData = ref(false)
const chartDom = ref(null)
const nodeSummary = ref({ total: 0, online: 0, attention: 0, offline: 0 })
let chartInstance = null
let refreshTimer = null
let resizeObserver = null

const statusLabel = (status) => ({
  online: '在线',
  degraded: '关注',
  offline: '离线'
}[status] || status || '未知')

const statusColor = (status) => ({
  online: '#16855b',
  degraded: '#bf7414',
  offline: '#c84040'
}[status] || '#718096')

const syncSummary = (nodes) => {
  const summary = nodes.reduce((result, node) => {
    result.total += 1
    if (node.status === 'offline' || !node.last_heartbeat) result.offline += 1
    else if (node.status === 'degraded') result.attention += 1
    else result.online += 1
    return result
  }, { total: 0, online: 0, attention: 0, offline: 0 })
  nodeSummary.value = summary
}

const demoNodes = () => ['B01', 'B02', 'B03'].map((bedId) => ({
  id: `EDGE-W01-${bedId}`,
  bed_id: bedId,
  status: 'online',
  last_heartbeat: new Date().toISOString(),
  buffered_events: 0,
}))

const fetchData = async () => {
  if (loading.value) return

  if (props.demoMode) {
    const nodes = demoNodes()
    syncSummary(nodes)
    hasNoData.value = false
    renderChart(nodes)
    return
  }

  loading.value = true
  try {
    const res = await api.getNodes()
    const nodes = res.data.data || []
    syncSummary(nodes)
    hasNoData.value = nodes.length === 0
    renderChart(nodes)
  } catch (e) {
    console.error('加载节点延迟图表失败', e)
    syncSummary([])
    hasNoData.value = true
    renderChart([])
  } finally {
    loading.value = false
  }
}

const renderChart = (nodes) => {
  if (!chartDom.value) return

  if (!chartInstance) {
    chartInstance = echarts.init(chartDom.value)
  }

  chartInstance.clear()

  if (hasNoData.value || nodes.length === 0) return

  const now = new Date()
  const names = []
  const latencies = []
  const gradientColors = []

  nodes.forEach((node, index) => {
    const nodeId = String(node.id || node.node_id || `node-${index + 1}`)
    const nodeSuffix = nodeId.includes('-') ? nodeId.split('-').pop() : nodeId
    names.push(`${node.bed_id || '未定'}床 · ${nodeSuffix}`)

    if (node.status === 'offline' || !node.last_heartbeat) {
      latencies.push(60)
      gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: '#c84040' },
        { offset: 1, color: '#f2b4b4' }
      ]))
    } else {
      const hbTime = new Date(node.last_heartbeat)
      const delaySec = Math.max(0, Math.floor((now - hbTime) / 1000))
      latencies.push(Math.min(delaySec, 60))

      if (delaySec < 5) {
        gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#16855b' },
          { offset: 1, color: '#8fd1b4' }
        ]))
      } else if (delaySec < 15) {
        gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#bf7414' },
          { offset: 1, color: '#f3c889' }
        ]))
      } else {
        gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#c84040' },
          { offset: 1, color: '#f2b4b4' }
        ]))
      }
    }
  })

  const option = {
    animationDuration: 450,
    animationEasing: 'cubicOut',
    aria: { enabled: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(20, 121, 118, 0.08)' } },
      backgroundColor: '#17212b',
      borderColor: 'rgba(255,255,255,0.12)',
      borderWidth: 1,
      padding: [10, 12],
      textStyle: { color: '#f7f9fb', fontSize: 11 },
      extraCssText: 'border-radius:8px;box-shadow:0 8px 24px rgba(23,33,43,.18);',
      formatter: (params) => {
        const p = params[0]
        const node = nodes[p.dataIndex] || {}
        const status = node.status === 'offline' || !node.last_heartbeat ? 'offline' : (node.status || 'online')
        const delay = Number(p.value)
        const value = status === 'offline' || delay >= 60
          ? '<span style="color:#ff9c9c;font-weight:700;">离线 · ≥60 秒</span>'
          : `<strong>${delay} 秒</strong>`
        return `
          <div style="font-weight:700;margin-bottom:6px;">${node.id || node.node_id || '未命名节点'}</div>
          <div style="color:#b8c6d1;line-height:1.8;">病区：${node.ward_id || '—'}</div>
          <div style="color:#b8c6d1;line-height:1.8;">设备状态：<span style="color:${statusColor(status)};font-weight:700;">${statusLabel(status)}</span></div>
          <div style="color:#b8c6d1;line-height:1.8;">心跳延迟：${value}</div>
          <div style="color:#b8c6d1;line-height:1.8;">本地缓存：<strong style="color:#f7f9fb;">${node.buffered_events || 0} 起</strong></div>
        `
      }
    },
    grid: { left: '3%', right: '3%', bottom: 34, top: 16, containLabel: true },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: {
        color: '#52606d',
        fontSize: 10,
        interval: 0,
        hideOverlap: true,
        margin: 12,
        formatter: (value) => value.length > 11 ? `${value.slice(0, 10)}…` : value
      },
      axisLine: { lineStyle: { color: '#d9e2e8' } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      name: '秒',
      nameLocation: 'end',
      nameGap: 8,
      nameTextStyle: { color: '#82909c', fontSize: 10 },
      axisLabel: { color: '#82909c', fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
      splitNumber: 3,
      splitLine: { lineStyle: { color: '#e9eff2', type: 'dashed' } },
      max: 60
    },
    series: [{
      name: '心跳延迟',
      type: 'bar',
      barMaxWidth: 24,
      barMinWidth: 8,
      data: latencies,
      itemStyle: {
        color: (params) => gradientColors[params.dataIndex],
        borderRadius: [5, 5, 1, 1]
      },
      emphasis: { itemStyle: { shadowBlur: 12, shadowColor: 'rgba(20,121,118,.22)' } },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { show: false },
        lineStyle: { type: 'dashed', width: 1 },
        data: [
          { yAxis: 5, lineStyle: { color: '#16855b', opacity: 0.55 } },
          { yAxis: 15, lineStyle: { color: '#bf7414', opacity: 0.65 } }
        ]
      }
    }],
    backgroundColor: 'transparent'
  }

  chartInstance.setOption(option)
}

const handleResize = () => {
  chartInstance?.resize()
}

watch(() => props.demoMode, () => {
  fetchData()
})

onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
  if (typeof ResizeObserver !== 'undefined' && chartDom.value) {
    resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(chartDom.value)
  }
  refreshTimer = setInterval(fetchData, 10000)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (refreshTimer) clearInterval(refreshTimer)
  resizeObserver?.disconnect()
  chartInstance?.dispose()
})

defineExpose({
  fetchData
})
</script>

<style scoped>
.chart-panel {
  --chart-ink: #17212b;
  --chart-muted: #82909c;
  --chart-border: #d9e2e8;
  --chart-surface: #ffffff;
  width: 100%;
  min-width: 0;
  margin-top: 0.7rem;
  padding: 0.85rem 0.9rem 0.75rem;
  border: 1px solid var(--chart-border);
  border-radius: 10px;
  background: var(--chart-surface);
  box-shadow: 0 2px 10px rgba(32, 54, 70, 0.045);
}

.chart-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.7rem;
  min-height: 42px;
  padding-bottom: 0.65rem;
  border-bottom: 1px solid #edf1f3;
}

.chart-heading { min-width: 0; }
.chart-kicker {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--chart-muted);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.chart-kicker-icon { color: var(--color-primary); font-size: 13px; }
.chart-kicker-separator { color: #c0cdd5; }
.chart-title {
  margin: 0.17rem 0 0;
  color: var(--chart-ink);
  font-size: 14px;
  font-weight: 700;
  line-height: 1.25;
}

.chart-actions {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  flex-shrink: 0;
}
.chart-summary {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.28rem 0.48rem;
  border: 1px solid #cfe9dc;
  border-radius: 999px;
  color: #16855b;
  background: #f1faf5;
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}
.chart-summary.is-muted { border-color: #e3e9ed; color: #82909c; background: #f7f9fb; }
.summary-dot { width: 5px; height: 5px; border-radius: 50%; background: #16855b; }
.summary-dot.is-muted { background: #9caab3; }
.chart-refresh-button {
  min-height: 28px;
  padding: 0 0.38rem;
  color: #52606d;
  font-size: 11px;
}
.chart-refresh-button:hover { color: var(--color-primary); background: var(--color-primary-soft); }
.chart-refresh-button :deep(.el-icon) { margin-right: 0.2rem; font-size: 13px; }

.latency-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 0.8rem;
  padding: 0.65rem 0 0.1rem;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  color: #82909c;
  font-size: 10px;
  white-space: nowrap;
}
.legend-dot { width: 7px; height: 7px; border-radius: 2px; }
.legend-dot.is-good { background: #16855b; }
.legend-dot.is-watch { background: #bf7414; }
.legend-dot.is-danger { background: #c84040; }

.chart-body {
  position: relative;
  width: 100%;
  height: clamp(184px, 20vw, 236px);
  min-height: 184px;
  margin-top: 0.1rem;
}
.chart-canvas { width: 100%; height: 100%; transition: opacity 0.2s ease; }
.chart-canvas.is-obscured { opacity: 0.08; }
.chart-state-overlay {
  position: absolute;
  z-index: 2;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 0.35rem;
  border-radius: 7px;
  color: #82909c;
  background: rgba(255, 255, 255, 0.9);
  font-size: 11px;
}
.chart-state-overlay strong { color: #52606d; font-size: 12px; }
.state-icon { color: #9aabb5; font-size: 22px; margin-bottom: 0.15rem; }
.state-icon.is-loading { color: var(--color-primary); }

@media (max-width: 720px) {
  .chart-panel { padding: 0.75rem 0.72rem 0.6rem; }
  .chart-header { align-items: center; }
  .chart-summary { display: none; }
  .chart-body { height: 214px; }
}
</style>
