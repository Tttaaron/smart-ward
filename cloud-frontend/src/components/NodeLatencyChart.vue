<template>
  <section class="latency-panel" aria-labelledby="node-latency-title">
    <header class="latency-head">
      <div class="latency-heading">
        <div class="latency-kicker">
          <el-icon :size="13" aria-hidden="true"><Connection /></el-icon>
          <span>设备网络 / 实时监测</span>
        </div>
        <h3 id="node-latency-title">边缘节点心跳</h3>
      </div>

      <div class="latency-actions">
        <span class="latency-summary" :class="{ 'is-muted': !nodeSummary.total }">
          <span class="summary-dot" :class="{ 'is-muted': !nodeSummary.total }" aria-hidden="true"></span>
          {{ nodeSummary.total ? `${nodeSummary.online}/${nodeSummary.total} 在线` : '等待节点' }}
        </span>
        <el-button
          size="small"
          text
          :loading="loading"
          aria-label="刷新节点延迟"
          title="刷新节点延迟"
          @click="fetchData"
        >
          <el-icon v-if="!loading" :size="13"><Refresh /></el-icon>
          <span>刷新</span>
        </el-button>
      </div>
    </header>

    <div class="latency-legend" aria-label="节点延迟状态说明">
      <span class="legend-item"><i class="legend-dot is-good"></i>正常 &lt; 5s</span>
      <span class="legend-item"><i class="legend-dot is-watch"></i>关注 5-15s</span>
      <span class="legend-item"><i class="legend-dot is-danger"></i>离线 / &gt; 15s</span>
    </div>

    <div class="latency-body">
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
  demoMode: { type: Boolean, default: false },
  // 外部刷新信号：父级处置事件/节点心跳后自增触发重取
  refreshTick: { type: Number, default: 0 },
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
  offline: '离线',
}[status] || status || '未知')

const statusColor = (status) => ({
  online: '#16A34A',
  degraded: '#D97706',
  offline: '#DC2626',
}[status] || '#64748B')

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
        { offset: 0, color: '#F87171' },
        { offset: 1, color: '#B91C1C' },
      ]))
    } else {
      const hbTime = new Date(node.last_heartbeat)
      const delaySec = Math.max(0, Math.floor((now - hbTime) / 1000))
      latencies.push(Math.min(delaySec, 60))

      if (delaySec < 5) {
        gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#4ADE80' },
          { offset: 1, color: '#16A34A' },
        ]))
      } else if (delaySec < 15) {
        gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#FCD34D' },
          { offset: 1, color: '#B45309' },
        ]))
      } else {
        gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#F87171' },
          { offset: 1, color: '#B91C1C' },
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
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(42, 125, 225, 0.06)' } },
      backgroundColor: '#FFFFFF',
      borderColor: '#D5E2EE',
      borderWidth: 1,
      padding: [10, 12],
      textStyle: { color: '#12212F', fontSize: 12.5 },
      extraCssText: 'border-radius:8px;box-shadow:0 10px 28px rgba(24,48,76,.14);',
      formatter: (params) => {
        const p = params[0]
        const node = nodes[p.dataIndex] || {}
        const status = node.status === 'offline' || !node.last_heartbeat ? 'offline' : (node.status || 'online')
        const delay = Number(p.value)
        const value = status === 'offline' || delay >= 60
          ? '<span style="color:#DC2626;font-weight:700;">离线 · ≥60 秒</span>'
          : `<strong>${delay} 秒</strong>`
        return `
          <div style="font-weight:700;margin-bottom:6px;">${node.id || node.node_id || '未命名节点'}</div>
          <div style="color:#44586A;line-height:1.8;">病区：${node.ward_id || '—'}</div>
          <div style="color:#44586A;line-height:1.8;">设备状态：<span style="color:${statusColor(status)};font-weight:700;">${statusLabel(status)}</span></div>
          <div style="color:#44586A;line-height:1.8;">心跳延迟：${value}</div>
          <div style="color:#44586A;line-height:1.8;">本地缓存：<strong style="color:#12212F;">${node.buffered_events || 0} 起</strong></div>
        `
      },
    },
    grid: { left: '3%', right: '3%', bottom: 34, top: 16, containLabel: true },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: {
        color: '#64809A',
        fontSize: 12,
        interval: 0,
        hideOverlap: true,
        margin: 12,
        formatter: (value) => (value.length > 11 ? `${value.slice(0, 10)}…` : value),
      },
      axisLine: { lineStyle: { color: 'rgba(24, 48, 76, 0.12)' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: '秒',
      nameLocation: 'end',
      nameGap: 8,
      nameTextStyle: { color: '#64809A', fontSize: 12 },
      axisLabel: { color: '#64809A', fontSize: 12 },
      axisLine: { show: false },
      axisTick: { show: false },
      splitNumber: 3,
      splitLine: { lineStyle: { color: 'rgba(24, 48, 76, 0.06)', type: 'dashed' } },
      max: 60,
    },
    series: [{
      name: '心跳延迟',
      type: 'bar',
      barMaxWidth: 24,
      barMinWidth: 8,
      data: latencies,
      itemStyle: {
        color: (params) => gradientColors[params.dataIndex],
        borderRadius: [5, 5, 1, 1],
      },
      emphasis: { itemStyle: { shadowBlur: 12, shadowColor: 'rgba(42,125,225,.28)' } },
      markLine: {
        silent: true,
        symbol: 'none',
        label: { show: false },
        lineStyle: { type: 'dashed', width: 1 },
        data: [
          { yAxis: 5, lineStyle: { color: '#16A34A', opacity: 0.5 } },
          { yAxis: 15, lineStyle: { color: '#D97706', opacity: 0.6 } },
        ],
      },
    }],
    backgroundColor: 'transparent',
  }

  chartInstance.setOption(option)
}

const handleResize = () => {
  chartInstance?.resize()
}

watch(() => props.demoMode, () => {
  fetchData()
})

watch(() => props.refreshTick, () => {
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

defineExpose({ fetchData })
</script>

<style scoped>
.latency-panel {
  width: 100%;
  min-width: 0;
  padding: 12px 12px 10px;
  background: rgba(42, 125, 225, 0.04);
  border: 1px solid var(--line);
  border-radius: 11px;
}

.latency-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  min-height: 38px;
  padding-bottom: 9px;
  border-bottom: 1px solid var(--line);
}
.latency-heading { min-width: 0; }
.latency-kicker {
  display: flex;
  align-items: center;
  gap: 5px;
  color: var(--text-3);
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.latency-kicker :deep(.el-icon) { color: var(--primary); }
.latency-heading h3 {
  margin: 3px 0 0;
  color: var(--text);
  font-size: 14px;
  font-weight: 800;
  line-height: 1.25;
}

.latency-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.latency-summary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 9px;
  border: 1px solid rgba(22, 163, 74, 0.32);
  border-radius: 999px;
  color: var(--success);
  background: var(--success-soft);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}
.latency-summary.is-muted {
  border-color: var(--line-strong);
  color: var(--text-3);
  background: rgba(24, 48, 76, 0.04);
}
.summary-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--success); }
.summary-dot.is-muted { background: var(--text-3); }

.latency-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  padding: 8px 0 2px;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text-3);
  font-size: 12px;
  white-space: nowrap;
}
.legend-dot { width: 7px; height: 7px; border-radius: 2px; }
.legend-dot.is-good { background: var(--success); }
.legend-dot.is-watch { background: var(--warning); }
.legend-dot.is-danger { background: var(--danger); }

.latency-body {
  position: relative;
  width: 100%;
  height: clamp(168px, 18vw, 220px);
  min-height: 168px;
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
  gap: 5px;
  border-radius: 8px;
  color: var(--text-3);
  background: rgba(255, 255, 255, 0.88);
  font-size: 12px;
}
.chart-state-overlay strong { color: var(--text-2); font-size: 12.5px; }
.state-icon { color: var(--text-3); font-size: 22px; margin-bottom: 2px; }
.state-icon.is-loading { color: var(--primary); }

@media (max-width: 720px) {
  .latency-panel { padding: 10px; }
  .latency-summary { display: none; }
  .latency-body { height: 200px; }
}
</style>
