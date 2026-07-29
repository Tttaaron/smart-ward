<template>
  <div class="bg-med-surface-2 border border-med-border rounded-lg p-2.5 mt-3">
    <div class="flex justify-between items-center mb-2 pb-1.5 border-b border-med-border">
      <div class="text-[13px] font-bold text-med-primary">边缘节点网络延迟看板</div>
      <el-button size="small" plain @click="fetchData" :loading="loading">刷新</el-button>
    </div>

    <div class="chart-body relative" style="height: 180px;">
      <div v-show="loading" class="absolute inset-0 flex items-center justify-center text-med-text-3 text-xs font-medium">数据加载中...</div>
      <div v-show="!loading && hasNoData" class="absolute inset-0 flex items-center justify-center text-med-text-3 text-xs font-medium">暂无在线设备节点</div>
      <div ref="chartDom" class="w-full h-full"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import api from '../api/index.js'

const loading = ref(false)
const hasNoData = ref(false)
const chartDom = ref(null)
let chartInstance = null
let refreshTimer = null

const fetchData = async () => {
  if (loading.value) return
  loading.value = true
  try {
    const res = await api.getNodes()
    const nodes = res.data.data || []

    if (nodes.length === 0) {
      hasNoData.value = true
      return
    }

    hasNoData.value = false
    renderChart(nodes)
  } catch (e) {
    console.error('加载节点延迟图表失败', e)
    hasNoData.value = true
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

  if (hasNoData.value) return

  const now = new Date()
  const names = []
  const latencies = []
  const gradientColors = []

  nodes.forEach(node => {
    // Label using the bed name or node ID
    names.push(`${node.bed_id || '未定'}床 (${node.id.split('-').pop()})`)

    if (node.status === 'offline' || !node.last_heartbeat) {
      latencies.push(60) // cap offline at 60s for visualization
      gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: '#f53f3f' },
        { offset: 1, color: '#fab0b0' }
      ])) // 红色渐变（浅色系）
    } else {
      const hbTime = new Date(node.last_heartbeat)
      const delaySec = Math.max(0, Math.floor((now - hbTime) / 1000))
      latencies.push(delaySec)

      // 根据网络延迟阈值选择渐变色
      if (delaySec < 5) {
        gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#00b42a' },
          { offset: 1, color: '#a8e6c4' }
        ])) // 绿色渐变
      } else if (delaySec < 15) {
        gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#ff7d00' },
          { offset: 1, color: '#ffd9a8' }
        ])) // 橙色渐变
      } else {
        gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#f53f3f' },
          { offset: 1, color: '#fab0b0' }
        ])) // 红色渐变
      }
    }
  })

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#ffffff',
      borderColor: '#d6e4ff',
      textStyle: { color: '#1d2129', fontSize: 11 },
      formatter: (params) => {
        const p = params[0]
        const val = p.value === 60 ? '<span style="color:#f53f3f;font-weight:700;">离线 (>=60s)</span>' : `<strong>${p.value} 秒</strong>`
        const node = nodes[p.dataIndex]

        let statusColor = '#00b42a'
        if (node.status === 'offline') statusColor = '#f53f3f'
        else if (node.status === 'degraded') statusColor = '#ff7d00'

        return `
          <strong>${node.id}</strong><br/>
          病区: ${node.ward_id}<br/>
          设备状态: <span style="color:${statusColor};font-weight:700;">${node.status}</span><br/>
          心跳延迟: ${val}<br/>
          本地缓存: <strong>${node.buffered_events || 0} 起</strong>
        `
      }
    },
    grid: { left: '3%', right: '4%', bottom: '5%', top: '18%', containLabel: true },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { color: '#86909c', fontSize: 9, interval: 0 },
      axisLine: { lineStyle: { color: '#e5e6eb' } }
    },
    yAxis: {
      type: 'value',
      name: '延迟 (秒)',
      nameTextStyle: { color: '#86909c', fontSize: 8 },
      axisLabel: { color: '#86909c', fontSize: 9 },
      splitLine: { lineStyle: { color: '#f0f0f0' } },
      max: 60
    },
    series: [{
      name: '心跳延迟',
      type: 'bar',
      barWidth: '35%',
      data: latencies,
      itemStyle: {
        color: (params) => gradientColors[params.dataIndex],
        borderRadius: [3, 3, 0, 0]
      }
    }],
    backgroundColor: 'transparent'
  }

  chartInstance.setOption(option)
}

const handleResize = () => {
  chartInstance?.resize()
}

onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
  // Poll nodes status periodically (every 10 seconds)
  refreshTimer = setInterval(fetchData, 10000)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (refreshTimer) clearInterval(refreshTimer)
  chartInstance?.dispose()
})

defineExpose({
  fetchData
})
</script>
