<template>
  <div class="bg-med-surface-2 border border-med-border rounded-lg p-2.5 mt-3">
    <div class="flex justify-between items-center mb-2 pb-1.5 border-b border-med-border">
      <el-radio-group v-model="activeTab" size="small" @change="renderChart">
        <el-radio-button value="trend">事件趋势 (24h)</el-radio-button>
        <el-radio-button value="pie">类别占比 (24h)</el-radio-button>
      </el-radio-group>
      <el-button size="small" plain @click="fetchData" :loading="loading">刷新</el-button>
    </div>

    <div class="chart-body relative" style="height: 180px;">
      <div v-show="loading" class="absolute inset-0 flex items-center justify-center text-med-text-3 text-xs font-medium">数据加载中...</div>
      <div v-show="!loading && hasNoData" class="absolute inset-0 flex items-center justify-center text-med-text-3 text-xs font-medium">暂无可用事件分析</div>
      <div ref="chartDom" class="w-full h-full"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import api from '../api/index.js'

const props = defineProps({
  demoMode: {
    type: Boolean,
    default: false,
  },
})

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

// Fetch both dataset API calls
let eventsData = []
let typeStatsData = {}

const useDemoData = () => {
  const now = Date.now()
  eventsData = [
    { event_type: 'fall_prediction', occurred_at: new Date(now - 18 * 60 * 1000).toISOString() },
    { event_type: 'nurse_call', occurred_at: new Date(now - 43 * 60 * 1000).toISOString() },
    { event_type: 'long_still', occurred_at: new Date(now - 96 * 60 * 1000).toISOString() },
    { event_type: 'bed_leave', occurred_at: new Date(now - 142 * 60 * 1000).toISOString() },
  ]
  typeStatsData = eventsData.reduce((counts, event) => {
    counts[event.event_type] = (counts[event.event_type] || 0) + 1
    return counts
  }, {})
  hasNoData.value = false
}

const fetchData = async () => {
  if (props.demoMode) {
    useDemoData()
    renderChart()
    return
  }

  loading.value = true
  try {
    const [eventsRes, typeRes] = await Promise.all([
      api.getEvents({ hours: 24, limit: 1000 }),
      api.getEventsByType({ hours: 24 })
    ])
    if (props.demoMode) return

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
        backgroundColor: '#ffffff',
        borderColor: '#d9d3ca',
        textStyle: { color: '#1b2a2e', fontSize: 11 }
      },
      grid: { left: '4%', right: '4%', bottom: '5%', top: '15%', containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: hoursLabel,
        axisLabel: { color: '#86909c', fontSize: 9 },
        axisLine: { lineStyle: { color: '#e5e6eb' } }
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { color: '#86909c', fontSize: 9 },
        splitLine: { lineStyle: { color: '#f0f0f0' } }
      },
      series: [{
        name: '事件数量',
        type: 'line',
        smooth: true,
        data: hourlyCounts,
        lineStyle: { color: '#147976', width: 2.5 },
        itemStyle: { color: '#147976' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(20, 121, 118, 0.24)' },
            { offset: 1, color: 'rgba(20, 121, 118, 0)' }
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
        backgroundColor: '#ffffff',
        borderColor: '#d9d3ca',
        textStyle: { color: '#1b2a2e', fontSize: 11 }
      },
      legend: {
        orient: 'vertical',
        right: '2%',
        top: 'middle',
        textStyle: { color: '#4e5969', fontSize: 9 },
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
          borderColor: '#ffffff',
          borderWidth: 1.5
        },
        label: {
          show: false
        },
        data: pieData
      }],
      color: ['#147976', '#5b9f99', '#c85b50', '#bd762b', '#18835e', '#8c6b9d', '#c77b87'],
      backgroundColor: 'transparent'
    }
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
