<template>
  <div
    class="bed-headboard bg-white border rounded-xl p-3 flex flex-col gap-2 relative transition-all duration-300 hover:scale-[1.03] hover:-translate-y-1 hover:shadow-lg cursor-pointer"
    :class="[
      bed.status === 'alert' ? 'border-red-400 bg-red-50/20' : 'border-slate-200/80 hover:border-blue-400',
      { alert: bed.pending_events > 0 }
    ]"
    :style="bed.pending_events > 0 ? 'animation: med-pulse-danger 1.2s infinite;' : ''"
  >
    <!-- 顶行：床号 + 护理等级 -->
    <div class="flex justify-between items-center border-b border-slate-100 pb-2">
      <div class="text-base font-extrabold text-slate-800 font-num flex items-center gap-1.5">
        <span class="w-1.5 h-4 bg-blue-500 rounded-sm"></span>
        {{ bed.name }}
      </div>
      <el-tag size="small" :type="careLevelTagType" effect="plain" class="!text-[10px] !font-extrabold !px-2 !py-0 !rounded-md">
        {{ careLevelText }}
      </el-tag>
    </div>

    <!-- 患者主信息 -->
    <div class="mt-0.5 px-0.5">
      <div v-if="bed.patient_alias" class="flex items-baseline gap-1.5">
        <span class="text-sm font-bold text-slate-800">{{ bed.patient_alias }}</span>
        <span class="text-[11px] text-slate-500 font-medium">({{ genderAgeText }})</span>
      </div>
      <div v-else class="text-[11px] text-slate-400 italic">空床 (无加床登记)</div>
    </div>

    <!-- 医护信息 -->
    <div class="flex justify-between text-[10px] text-slate-600 bg-slate-50/80 px-2 py-1 rounded-md border border-slate-100/50">
      <span>责护: <strong class="text-slate-800">{{ nurseName }}</strong></span>
      <span>主管: <strong class="text-slate-800">{{ doctorName }}</strong></span>
    </div>

    <!-- 风险标签 -->
    <div class="flex gap-1 flex-wrap min-h-[22px] items-center">
      <el-tag
        v-for="tag in riskTags"
        :key="tag.text"
        size="small"
        :type="tag.type"
        effect="light"
        class="!text-[9px] !font-bold !px-1.5 !py-0 !rounded-md"
      >
        {{ tag.text }}
      </el-tag>

      <!-- 最新事件推理链路 -->
      <span
        v-if="latestEvent"
        class="route-chip font-num text-[9px] font-black px-1.5 py-0.5 rounded-md"
        :class="'route-' + routeOf(latestEvent)"
        :title="routeDesc(routeOf(latestEvent))"
      >
        {{ routeIconOf(routeOf(latestEvent)) }} {{ routeLabel(routeOf(latestEvent)) }}
      </span>

      <!-- 节点网络状态 -->
      <span
        v-if="nodeStatus"
        class="net-chip font-num text-[9px] font-black px-1.5 py-0.5 rounded-md"
        :class="'net-' + nodeStatus"
      >
        {{ nodeStatusLabel }}
      </span>
    </div>

    <!-- 底部状态栏 -->
    <div class="flex items-center text-[11px] mt-1 pt-2 border-t border-dashed border-slate-100">
      <span class="status-dot w-2 h-2 rounded-full mr-2" :class="bed.status"></span>
      <span class="font-bold text-slate-600">{{ bedStatusLabel(bed.status) }}</span>

      <!-- 模型版本 -->
      <span v-if="modelVersion" class="ml-2 text-[9px] text-slate-400 font-num truncate max-w-[80px]" :title="modelVersion">
        {{ modelVersion }}
      </span>

      <!-- 正常情况下的隐私监护图标 / 告警情况下的紧急画面按钮 -->
      <button
        @click.stop="$emit('showMonitor', bed)"
        class="ml-auto flex items-center justify-center text-[10px] font-bold px-2 py-0.5 rounded transition-all duration-200"
        :class="bed.status === 'alert'
          ? 'bg-red-500 hover:bg-red-600 text-white animate-pulse shadow-sm shadow-red-200'
          : 'bg-slate-100 hover:bg-blue-50 text-slate-600 hover:text-blue-600 border border-slate-200/50 hover:border-blue-200'"
      >
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-3 h-3 mr-1">
          <path stroke-linecap="round" stroke-linejoin="round" d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
        </svg>
        监护
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { resolveRoute, routeLabel, routeDesc, networkMeta } from '../utils/eventMeta.js'

const props = defineProps({
  bed: {
    type: Object,
    required: true
  },
  // 该床最新事件（用于展示推理链路）
  latestEvent: {
    type: Object,
    default: null
  },
  // 节点状态 online/degraded/offline
  nodeStatus: {
    type: String,
    default: ''
  },
  // 节点模型版本
  modelVersion: {
    type: String,
    default: ''
  }
})

defineEmits(['showMonitor'])

// 护理等级文本
const careLevelText = computed(() => {
  if (props.bed.id === 'B01') return '特级护理'
  if (props.bed.id === 'B02') return 'Ⅰ级护理'
  return 'Ⅱ级护理'
})

// 映射为 Element Plus tag type
const careLevelTagType = computed(() => {
  if (props.bed.id === 'B01') return 'danger'
  if (props.bed.id === 'B02') return 'warning'
  return 'primary'
})

const genderAgeText = computed(() => {
  if (props.bed.id === 'B01') return '男, 68岁'
  if (props.bed.id === 'B02') return '女, 74岁'
  return '男, 59岁'
})

const nurseName = computed(() => {
  if (props.bed.id === 'B01') return '张莉'
  if (props.bed.id === 'B02') return '李秀'
  return '王婷'
})

const doctorName = computed(() => {
  if (props.bed.id === 'B01') return '王主任'
  if (props.bed.id === 'B02') return '陈医师'
  return '刘医师'
})

const riskTags = computed(() => {
  if (props.bed.id === 'B01') return [
    { text: '防跌倒', type: 'danger' },
    { text: '防压疮', type: 'warning' },
    { text: '禁食', type: 'info' }
  ]
  if (props.bed.id === 'B02') return [
    { text: '防跌倒', type: 'danger' },
    { text: '高龄', type: 'info' }
  ]
  return [
    { text: '防坠床', type: 'warning' }
  ]
})

const routeOf = (evt) => resolveRoute(evt)
const routeIconOf = (r) => ({ edge: '⚡', cloud: '☁️', hybrid: '🔁' }[r] || '⚡')
const nodeStatusLabel = computed(() => {
  if (!props.nodeStatus) return ''
  return networkMeta(props.nodeStatus).label.replace('网络', '')
})

const bedStatusLabel = (status) => {
  const map = {
    idle: '空闲',
    occupied: '在床',
    alert: '告警/呼叫中',
    maintenance: '设备维护'
  }
  return map[status] || status
}
</script>

<style scoped>
/* 状态指示点 */
.status-dot.occupied {
  background: #2ea121;
  box-shadow: 0 0 6px rgba(46, 161, 33, 0.6);
}
.status-dot.idle {
  background: #8c8c8c;
}
.status-dot.maintenance {
  background: #fa8c16;
}
.status-dot.alert {
  background: #f5222d;
  box-shadow: 0 0 8px rgba(245, 34, 45, 0.6);
}

/* 告警态卡片高亮 */
.bed-headboard.alert {
  background: rgba(245, 34, 45, 0.04) !important;
}

/* 推理链路 route 徽章 */
.route-chip.route-edge {
  background: rgba(46, 161, 33, 0.08);
  color: #2ea121;
  border: 1px solid rgba(46, 161, 33, 0.3);
}
.route-chip.route-cloud {
  background: rgba(24, 144, 255, 0.08);
  color: #1890ff;
  border: 1px solid rgba(24, 144, 255, 0.3);
}
.route-chip.route-hybrid {
  background: rgba(250, 140, 22, 0.08);
  color: #fa8c16;
  border: 1px solid rgba(250, 140, 22, 0.3);
}

/* 节点网络状态徽章 */
.net-chip.net-online {
  background: rgba(46, 161, 33, 0.08);
  color: #2ea121;
  border: 1px solid rgba(46, 161, 33, 0.25);
}
.net-chip.net-degraded {
  background: rgba(250, 140, 22, 0.08);
  color: #fa8c16;
  border: 1px solid rgba(250, 140, 22, 0.3);
}
.net-chip.net-offline {
  background: rgba(245, 34, 45, 0.08);
  color: #f5222d;
  border: 1px solid rgba(245, 34, 45, 0.3);
}
</style>
