<template>
  <div class="event-trend-chart-card">
    <div class="chart-header">
      <div class="chart-tabs">
        <button :class="{ active: activeTab === 'trend' }" @click="switchTab('trend')">事件趋势 (24h)</button>
        <button :class="{ active: activeTab === 'pie' }" @click="switchTab('pie')">类别占比 (24h)</button>
      </div>
      <button class="btn-refresh" @click="fetchData" :disabled="loading">
        <span v-if="loading">...</span>
        <span v-else>刷新</span>
      </button>
    </div>
    
    <div class="chart-body">
      <div v-show="loading" class="chart-loading">数据加载中...</div>
      <div v-show="!loading && hasNoData" class="chart-empty">暂无可用事件分析</div>
      <div ref="chartDom" class="chart-canvas"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import api from '../api/index.js'

const activeTab = ref('trend')
const loading = ref(false)
const hasNoData = ref(false)
const chartDom = ref(null)
let chartInstance = null

const eventTypeLabels = {
  fall_suspected: '疑似跌倒',
  nurse_call: '护士呼叫',
  bed_leave: '离床',
  door_departure: '门区异常',
  night_wandering: '夜间徘徊',
  environment_anomaly: '环境异常',
  node_offline: '节点失联',
  fall_prediction: '坠床预警',
  long_still: '长时间静止',
  abnormal_posture: '异常体态',
  seizure: '抽搐检测',
  bedsore_risk: '压疮预防',
  device_fault: '设备故障',
}

const eventTypeLabel = (t) => eventTypeLabels[t] || t

const switchTab = (tab) => {
  activeTab.value = tab
  renderChart()
}

// Fetch both dataset API calls
let eventsData = []
let typeStatsData = {}

const fetchData = async () => {
  loading.value = true
  try {
    const [eventsRes, typeRes] = await Promise.all([
      api.getEvents({ hours: 24, limit: 1000 }),
      api.getEventsByType({ hours: 24 })
    ])
    eventsData = eventsRes.data.data || []
    typeStatsData = typeRes.data.data || {}
    
    hasNoData.value = eventsData.length === 0
    
    renderChart()
  } catch (e) {
    console.error('加载事件图表数据失败', e)
    hasNoData.value = true
  } finally {
    loading.value = false
  }
}

const renderChart = () => {
  if (!chartDom.value) return
  
  if (!chartInstance) {
    chartInstance = echarts.init(chartDom.value)
  }
  
  chartInstance.clear()
  
  if (hasNoData.value) {
    return
  }
  
  let option = {}
  
  if (activeTab.value === 'trend') {
    // Aggregate events into hourly bins (last 24 hours)
    const now = new Date()
    const hourlyCounts = Array(24).fill(0)
    const hoursLabel = []
    
    for (let i = 23; i >= 0; i--) {
      const d = new Date(now.getTime() - i * 60 * 60 * 1000)
      hoursLabel.push(`${d.getHours()}:00`)
    }
    
    eventsData.forEach(evt => {
      if (!evt.occurred_at) return
      const evtTime = new Date(evt.occurred_at)
      const diffMs = now - evtTime
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
      if (diffHours >= 0 && diffHours < 24) {
        hourlyCounts[23 - diffHours]++
      }
    })
    
    option = {
      tooltip: {
        trigger: 'axis',
        formatter: '{b}<br/>事件数: <strong>{c}</strong>',
        backgroundColor: '#1e293b',
        borderColor: 'rgba(255,255,255,0.08)',
        textStyle: { color: '#cbd5e1', fontSize: 11 }
      },
      grid: { left: '4%', right: '4%', bottom: '5%', top: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: hoursLabel,
        axisLabel: { color: '#64748b', fontSize: 9 },
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } }
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { color: '#64748b', fontSize: 9 },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } }
      },
      series: [{
        name: '事件数量',
        type: 'line',
        smooth: true,
        data: hourlyCounts,
        lineStyle: { color: '#00f2fe', width: 2.5 },
        itemStyle: { color: '#00f2fe' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 242, 254, 0.3)' },
            { offset: 1, color: 'rgba(0, 242, 254, 0)' }
          ])
        }
      }],
      backgroundColor: 'transparent'
    }
  } else {
    // Pie distribution
    const pieData = Object.entries(typeStatsData)
      .map(([type, count]) => ({
        value: count,
        name: eventTypeLabel(type)
      }))
      .filter(item => item.value > 0)
      
    if (pieData.length === 0) {
      hasNoData.value = true
      return
    }
    
    option = {
      tooltip: {
        trigger: 'item',
        formatter: '{b}: <strong>{c} 起 ({d}%)</strong>',
        backgroundColor: '#1e293b',
        borderColor: 'rgba(255,255,255,0.08)',
        textStyle: { color: '#cbd5e1', fontSize: 11 }
      },
      legend: {
        orient: 'vertical',
        right: '2%',
        top: 'middle',
        textStyle: { color: '#64748b', fontSize: 9 },
        itemWidth: 8,
        itemHeight: 8,
        itemGap: 6
      },
      series: [{
        name: '事件类别',
        type: 'pie',
        radius: ['45%', '75%'],
        center: ['38%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#1e293b',
          borderWidth: 1.5
        },
        label: {
          show: false
        },
        data: pieData
      }],
      color: ['#38bdf8', '#00f2fe', '#f43f5e', '#fbbf24', '#34d399', '#a78bfa', '#ec4899'],
      backgroundColor: 'transparent'
    }
  }
  
  chartInstance.setOption(option)
}

const handleResize = () => {
  chartInstance?.resize()
}

onMounted(() => {
  fetchData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})

// Expose the fetchData method to parent component
defineExpose({
  fetchData
})
</script>

<style scoped>
.event-trend-chart-card {
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
.chart-tabs {
  display: flex;
  gap: 4px;
}
.chart-tabs button {
  background: rgba(15, 23, 42, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.04);
  color: #64748b;
  padding: 4px 10px;
  font-size: 10px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s ease;
}
.chart-tabs button.active {
  background: rgba(79, 195, 247, 0.12);
  color: #4fc3f7;
  border-color: rgba(79, 195, 247, 0.3);
  box-shadow: inset 0 1px 1px rgba(79, 195, 247, 0.1);
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
