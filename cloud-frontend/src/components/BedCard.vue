<template>
  <div
    class="bed-headboard bg-white border rounded-lg p-3 flex flex-col gap-2 relative transition-colors duration-200 hover:shadow-sm cursor-pointer"
    :class="[
      bed.status === 'alert' ? 'bed-card-alert' : 'bed-card-normal',
      { alert: bed.pending_events > 0 }
    ]"
  >
    <!-- 顶行：床号 + 护理等级 -->
    <div class="flex justify-between items-center border-b border-slate-100 pb-2">
      <div class="text-base font-extrabold text-slate-800 font-num flex items-center gap-1.5">
        <span class="bed-index-bar"></span>
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
        <span class="route-mark" aria-hidden="true"></span>{{ routeLabel(routeOf(latestEvent)) }}
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
    <div class="flex items-center min-w-0 text-[11px] mt-1 pt-2 border-t border-dashed border-slate-100">
      <span class="status-dot w-2 h-2 rounded-full mr-2 flex-shrink-0" :class="bed.status"></span>
      <span class="font-bold text-slate-600 whitespace-nowrap">{{ bedStatusLabel(bed.status) }}</span>

      <!-- 模型版本 -->
      <span v-if="modelVersion" class="bed-model-version ml-2 text-[9px] text-slate-400 font-num truncate max-w-[80px]" :title="modelVersion">
        {{ modelVersion }}
      </span>

      <!-- 正常情况下的隐私监护图标 / 告警情况下的紧急画面按钮 -->
      <button
        @click.stop="$emit('showMonitor', bed)"
        class="ml-auto flex items-center justify-center text-[10px] font-bold px-2 py-0.5 rounded transition-all duration-200"
        :class="bed.status === 'alert' ? 'is-alert' : 'is-normal'"
      >
        <el-icon :size="13" class="mr-1" aria-hidden="true"><VideoCamera /></el-icon>
        监护
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { VideoCamera } from '@element-plus/icons-vue'
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
  background: var(--color-success);
  box-shadow: 0 0 6px rgba(24, 131, 94, 0.45);
}
.status-dot.idle {
  background: #8c8c8c;
}
.status-dot.maintenance {
  background: var(--color-warning);
}
.status-dot.alert {
  background: var(--color-danger);
  box-shadow: 0 0 8px rgba(200, 91, 80, 0.45);
}

/* 告警态卡片高亮 */
.bed-headboard.alert {
  background: #fffaf8 !important;
  border-color: #e4c9c2 !important;
}

.bed-card-normal { border-color: rgba(217, 211, 202, 0.8); }
.bed-card-normal:hover { border-color: rgba(20, 121, 118, 0.45); }
.bed-card-alert { border-color: rgba(200, 91, 80, 0.45); background: #fffaf8; }
.bed-index-bar {
  width: 6px;
  height: 17px;
  border-radius: 3px;
  background: var(--color-primary);
}
.bed-monitor-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 25px;
  padding: 2px 9px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  transition: all 0.2s ease;
}
.bed-monitor-button.is-normal {
  color: var(--color-text-2);
  background: var(--color-surface-3);
  border: 1px solid var(--color-border);
}
.bed-monitor-button.is-normal:hover {
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-color: rgba(20, 121, 118, 0.38);
}
.bed-monitor-button.is-alert {
  color: #fff;
  background: var(--color-danger);
  border: 1px solid var(--color-danger);
  box-shadow: 0 3px 8px rgba(200, 91, 80, 0.22);
}
.bed-monitor-button.is-alert:hover { background: #b64f47; border-color: #b64f47; }
.bed-headboard.alert::before {
  content: '';
  position: absolute;
  left: -1px;
  top: 14px;
  bottom: 14px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--color-danger);
}

@media (max-width: 1450px) {
  .bed-model-version { display: none; }
}

/* 推理链路 route 徽章 */
.route-chip.route-edge {
  background: rgba(46, 161, 33, 0.08);
  color: var(--color-success);
  border: 1px solid rgba(24, 131, 94, 0.3);
}
.route-chip.route-cloud {
  background: rgba(20, 121, 118, 0.08);
  color: var(--color-primary);
  border: 1px solid rgba(20, 121, 118, 0.3);
}
.route-chip.route-hybrid {
  background: rgba(250, 140, 22, 0.08);
  color: var(--color-warning);
  border: 1px solid rgba(189, 118, 43, 0.3);
}

/* 节点网络状态徽章 */
.net-chip.net-online {
  background: rgba(46, 161, 33, 0.08);
  color: var(--color-success);
  border: 1px solid rgba(24, 131, 94, 0.25);
}
.net-chip.net-degraded {
  background: rgba(250, 140, 22, 0.08);
  color: var(--color-warning);
  border: 1px solid rgba(189, 118, 43, 0.3);
}
.net-chip.net-offline {
  background: rgba(200, 91, 80, 0.08);
  color: var(--color-danger);
  border: 1px solid rgba(200, 91, 80, 0.3);
}
.route-mark {
  display: inline-block;
  width: 5px;
  height: 5px;
  margin-right: 4px;
  border-radius: 50%;
  background: currentColor;
  vertical-align: middle;
}
</style>
