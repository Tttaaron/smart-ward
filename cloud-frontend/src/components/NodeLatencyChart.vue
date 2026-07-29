<template>
  <div class="node-latency-chart-card">
    <div class="chart-header">
      <div class="chart-title">边缘节点网络延迟看板</div>
      <button class="btn-refresh" @click="fetchData" :disabled="loading">
        <span v-if="loading">...</span>
        <span v-else>刷新</span>
      </button>
    </div>
    
    <div class="chart-body">
      <div v-show="loading" class="chart-loading">数据加载中...</div>
      <div v-show="!loading && hasNoData" class="chart-empty">暂无在线设备节点</div>
      <div ref="chartDom" class="chart-canvas"></div>
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
        { offset: 0, color: '#f43f5e' },
        { offset: 1, color: '#991b1b' }
      ])) // Rose red gradient
    } else {
      const hbTime = new Date(node.last_heartbeat)
      const delaySec = Math.max(0, Math.floor((now - hbTime) / 1000))
      latencies.push(delaySec)
      
      // Gradient colors based on network latency threshold
      if (delaySec < 5) {
        gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#10b981' },
          { offset: 1, color: '#064e3b' }
        ])) // Emerald green gradient
      } else if (delaySec < 15) {
        gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#fbbf24' },
          { offset: 1, color: '#78350f' }
        ])) // Amber yellow gradient
      } else {
        gradientColors.push(new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#f43f5e' },
          { offset: 1, color: '#991b1b' }
        ])) // Red gradient
      }
    }
  })
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#1e293b',
      borderColor: 'rgba(255,255,255,0.08)',
      textStyle: { color: '#cbd5e1', fontSize: 11 },
      formatter: (params) => {
        const p = params[0]
        const val = p.value === 60 ? '<span style="color:#f43f5e;font-weight:700;">离线 (>=60s)</span>' : `<strong>${p.value} 秒</strong>`
        const node = nodes[p.dataIndex]
        
        let statusColor = '#10b981'
        if (node.status === 'offline') statusColor = '#f43f5e'
        else if (node.status === 'degraded') statusColor = '#fbbf24'
        
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
      axisLabel: { color: '#64748b', fontSize: 9, interval: 0 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
    },
    yAxis: {
      type: 'value',
      name: '延迟 (秒)',
      nameTextStyle: { color: '#64748b', fontSize: 8 },
      axisLabel: { color: '#64748b', fontSize: 9 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
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

<style scoped>
.node-latency-chart-card {
  background: rgba(30, 41, 59, 0.2);
  border-radius: 8px;
  padding: 10px 12px;
  margin-top: 12px;
  border: 1px solid rgba(255, 255, 255, 0.04);
}
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  padding-bottom: 6px;
}
.chart-title {
  font-size: 13px;
  font-weight: 700;
  color: #4fc3f7;
}
.btn-refresh {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.06);
  color: #94a3b8;
  font-size: 9px;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s ease;
}
.btn-refresh:hover {
  background: rgba(255,255,255,0.03);
  border-color: rgba(255,255,255,0.12);
  color: #f1f5f9;
}
.chart-body {
  position: relative;
  height: 180px;
}
.chart-canvas {
  width: 100%;
  height: 100%;
}
.chart-loading, .chart-empty {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #475569;
  font-size: 12px;
  font-weight: 500;
}
</style>
