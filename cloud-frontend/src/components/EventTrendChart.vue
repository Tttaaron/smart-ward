<template>
  <div class="trend-panel">
    <div class="trend-head">
      <el-radio-group v-model="activeTab" size="small" @change="renderChart">
        <el-radio-button value="trend">事件趋势 (24h)</el-radio-button>
        <el-radio-button value="pie">类别占比 (24h)</el-radio-button>
      </el-radio-group>
      <el-button size="small" plain :loading="loading" @click="fetchData">
        <el-icon v-if="!loading" :size="13"><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <div class="chart-body">
      <div v-show="loading" class="chart-state">数据加载中...</div>
      <div v-show="!loading && hasNoData" class="chart-state">暂无可用事件分析</div>
      <div ref="chartDom" class="chart-canvas"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'
import api from '../api/index.js'

const props = defineProps({
  demoMode: { type: Boolean, default: false },
  // 外部刷新信号：父级处置事件后自增触发重取
  refreshTick: { type: Number, default: 0 },
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

let eventsData = []
let typeStatsData = {}

// 浅色临床图表通用配色
const CHART = {
  text: '#64809A',
  grid: 'rgba(24, 48, 76, 0.06)',
  axis: 'rgba(24, 48, 76, 0.12)',
  tooltipBg: '#FFFFFF',
  tooltipBorder: '#D5E2EE',
  tooltipText: '#12212F',
  // 评审现场为投影/大屏，轴标签不得小于 12px
  axisFont: 12,
  tooltipFont: 12.5,
}

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
      api.getEventsByType({ hours: 24 }),
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

  if (hasNoData.value) return

  let option = {}

  if (activeTab.value === 'trend') {
    const now = new Date()
    const hourlyCounts = Array(24).fill(0)
    const hoursLabel = []

    for (let i = 23; i >= 0; i--) {
      const d = new Date(now.getTime() - i * 60 * 60 * 1000)
      hoursLabel.push(`${d.getHours()}:00`)
    }

    eventsData.forEach((evt) => {
      if (!evt.occurred_at) return
      const evtTime = new Date(evt.occurred_at)
      const diffHours = Math.floor((now - evtTime) / (1000 * 60 * 60))
      if (diffHours >= 0 && diffHours < 24) hourlyCounts[23 - diffHours]++
    })

    option = {
      tooltip: {
        trigger: 'axis',
        formatter: '{b}<br/>事件数: <strong>{c}</strong>',
        backgroundColor: CHART.tooltipBg,
        borderColor: CHART.tooltipBorder,
        textStyle: { color: CHART.tooltipText, fontSize: CHART.tooltipFont },
      },
      grid: { left: '4%', right: '4%', bottom: '4%', top: '14%', containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: hoursLabel,
        axisLabel: { color: CHART.text, fontSize: CHART.axisFont },
        axisLine: { lineStyle: { color: CHART.axis } },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { color: CHART.text, fontSize: CHART.axisFont },
        splitLine: { lineStyle: { color: CHART.grid } },
      },
      series: [{
        name: '事件数量',
        type: 'line',
        smooth: true,
        data: hourlyCounts,
        lineStyle: { color: '#2A7DE1', width: 2.5, shadowColor: 'rgba(42, 125, 225, 0.35)', shadowBlur: 8 },
        itemStyle: { color: '#2A7DE1', borderColor: '#FFFFFF', borderWidth: 1 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(42, 125, 225, 0.22)' },
            { offset: 1, color: 'rgba(42, 125, 225, 0)' },
          ]),
        },
      }],
      backgroundColor: 'transparent',
    }
  } else {
    const pieData = Object.entries(typeStatsData)
      .map(([type, count]) => ({ value: count, name: eventTypeLabel(type) }))
      .filter((item) => item.value > 0)

    if (pieData.length === 0) {
      hasNoData.value = true
      return
    }

    option = {
      tooltip: {
        trigger: 'item',
        formatter: '{b}: <strong>{c} 起 ({d}%)</strong>',
        backgroundColor: CHART.tooltipBg,
        borderColor: CHART.tooltipBorder,
        textStyle: { color: CHART.tooltipText, fontSize: CHART.tooltipFont },
      },
      legend: {
        orient: 'vertical',
        right: '2%',
        top: 'middle',
        textStyle: { color: CHART.text, fontSize: CHART.axisFont },
        itemWidth: 8,
        itemHeight: 8,
        itemGap: 6,
      },
      series: [{
        name: '事件类别',
        type: 'pie',
        radius: ['45%', '75%'],
        center: ['38%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#FFFFFF',
          borderWidth: 1.5,
        },
        label: { show: false },
        data: pieData,
      }],
      color: ['#2A7DE1', '#0EA5E9', '#DC2626', '#D97706', '#16A34A', '#7C6CE8', '#E86CA0'],
      backgroundColor: 'transparent',
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

watch(() => props.refreshTick, () => {
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

defineExpose({ fetchData })
</script>

<style scoped>
.trend-panel {
  padding: 10px 11px 8px;
  background: rgba(42, 125, 225, 0.04);
  border: 1px solid var(--line);
  border-radius: 10px;
}
.trend-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line);
}
.chart-body {
  position: relative;
  height: 168px;
}
.chart-canvas { width: 100%; height: 100%; }
.chart-state {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-3);
  font-size: 12px;
  font-weight: 600;
}
</style>
