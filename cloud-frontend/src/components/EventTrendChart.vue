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
      <div v-show="loading" class="chart-loading">加载图表中...</div>
      <div v-show="!loading && hasNoData" class="chart-empty">暂无事件数据</div>
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
        formatter: '{b}<br/>事件数: {c}',
        backgroundColor: '#243449',
        borderColor: '#3a4f64',
        textStyle: { color: '#e0e6ed' }
      },
      grid: { left: '4%', right: '4%', bottom: '5%', top: '12%', containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: hoursLabel,
        axisLabel: { color: '#8a9aaa', fontSize: 10 },
        axisLine: { lineStyle: { color: '#2a3f5f' } }
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { color: '#8a9aaa' },
        splitLine: { lineStyle: { color: '#2a3f5f' } }
      },
      series: [{
        name: '事件数量',
        type: 'line',
        smooth: true,
        data: hourlyCounts,
        lineStyle: { color: '#4fc3f7', width: 2.5 },
        itemStyle: { color: '#4fc3f7' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(79, 195, 247, 0.35)' },
            { offset: 1, color: 'rgba(79, 195, 247, 0)' }
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
        formatter: '{b}: {c} ({d}%)',
        backgroundColor: '#243449',
        borderColor: '#3a4f64',
        textStyle: { color: '#e0e6ed' }
      },
      legend: {
        orient: 'vertical',
        right: '5%',
        top: 'middle',
        textStyle: { color: '#b0c4de', fontSize: 10 },
        itemWidth: 10,
        itemHeight: 10
      },
      series: [{
        name: '事件类别',
        type: 'pie',
        radius: ['45%', '75%'],
        center: ['40%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#1a2942',
          borderWidth: 1.5
        },
        label: {
          show: false
        },
        data: pieData
      }],
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
.chart-tabs {
  display: flex;
  gap: 4px;
}
.chart-tabs button {
  background: #243449;
  border: 1px solid #2a3f5f;
  color: #8a9aaa;
  padding: 3px 8px;
  font-size: 11px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.chart-tabs button.active {
  background: #4fc3f7;
  color: #0f1b2d;
  border-color: #4fc3f7;
  font-weight: 600;
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
