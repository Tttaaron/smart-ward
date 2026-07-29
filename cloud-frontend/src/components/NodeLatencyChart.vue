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
      <div v-show="loading" class="chart-loading">加载图表中...</div>
      <div v-show="!loading && hasNoData" class="chart-empty">暂无可用节点</div>
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
  const colors = []
  
  nodes.forEach(node => {
    // Label using the bed name or node ID
    names.push(`${node.bed_id || '未知'}床 (${node.id.split('-').pop()})`)
    
    if (node.status === 'offline' || !node.last_heartbeat) {
      latencies.push(60) // cap offline at 60s for visualization
      colors.push('#f44336') // Red
    } else {
      const hbTime = new Date(node.last_heartbeat)
      const delaySec = Math.max(0, Math.floor((now - hbTime) / 1000))
      latencies.push(delaySec)
      
      // Color-coding based on latency threshold
      if (delaySec < 5) {
        colors.push('#4caf50') // Green (Healthy)
      } else if (delaySec < 15) {
        colors.push('#ff9800') // Orange (Warning)
      } else {
        colors.push('#f44336') // Red (Critical)
      }
    }
  })
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#243449',
      borderColor: '#3a4f64',
      textStyle: { color: '#e0e6ed' },
      formatter: (params) => {
        const p = params[0]
        const val = p.value === 60 ? '离线 (>=60s)' : `${p.value} 秒`
        const node = nodes[p.dataIndex]
        return `
          <strong>${node.id}</strong><br/>
          病区: ${node.ward_id}<br/>
          状态: <span style="color:${p.color}">${node.status}</span><br/>
          心跳延迟: ${val}<br/>
          缓存事件: ${node.buffered_events || 0}
        `
      }
    },
    grid: { left: '3%', right: '4%', bottom: '8%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { color: '#8a9aaa', fontSize: 10, interval: 0 },
      axisLine: { lineStyle: { color: '#2a3f5f' } }
    },
    yAxis: {
      type: 'value',
      name: '延迟 (秒)',
      nameTextStyle: { color: '#8a9aaa', fontSize: 9 },
      axisLabel: { color: '#8a9aaa' },
      splitLine: { lineStyle: { color: '#2a3f5f' } },
      max: 60
    },
    series: [{
      name: '心跳延迟',
      type: 'bar',
      barWidth: '35%',
      data: latencies,
      itemStyle: {
        color: (params) => colors[params.dataIndex],
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
  background: #1a2942;
  border-radius: 6px;
  padding: 10px 12px;
  margin-top: 12px;
  border: 1px solid #2a3f5f;
}
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  border-bottom: 1px solid #2a3f5f;
  padding-bottom: 6px;
}
.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: #4fc3f7;
}
.btn-refresh {
  background: transparent;
  border: 1px solid #3a4f64;
  color: #e0e6ed;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  cursor: pointer;
}
.btn-refresh:hover {
  background: #2d4055;
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
  color: #6a7a8a;
  font-size: 12px;
}
</style>
