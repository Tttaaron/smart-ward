<template>
  <div
    class="bed-headboard bg-med-surface border rounded-lg p-2.5 flex flex-col gap-1.5 relative transition-all duration-200"
    :class="[
      bed.status === 'alert' ? 'border-med-danger' : 'border-med-border',
      { alert: bed.pending_events > 0 }
    ]"
    :style="bed.pending_events > 0 ? 'animation: med-pulse-danger 1.2s infinite;' : ''"
  >
    <!-- 顶行：床号 + 护理等级 -->
    <div class="flex justify-between items-center border-b border-med-border pb-1.5">
      <div class="text-[15px] font-extrabold text-med-text font-num">{{ bed.name }}</div>
      <el-tag size="small" :type="careLevelTagType" effect="light" class="!text-[10px] !font-bold !px-1.5 !py-0">
        {{ careLevelText }}
      </el-tag>
    </div>

    <!-- 患者主信息 -->
    <div class="mt-0.5">
      <div v-if="bed.patient_alias" class="flex items-baseline gap-1">
        <span class="text-[13px] font-bold text-med-text">{{ bed.patient_alias }}</span>
        <span class="text-[11px] text-med-text-2">({{ genderAgeText }})</span>
      </div>
      <div v-else class="text-[11px] text-med-text-3 italic">空床 (无加床登记)</div>
    </div>

    <!-- 医护信息 -->
    <div class="flex justify-between text-[10px] text-med-text-2 bg-med-surface-2 px-1.5 py-0.5 rounded">
      <span>责护: {{ nurseName }}</span>
      <span>主管: {{ doctorName }}</span>
    </div>

    <!-- 风险标签 -->
    <div class="flex gap-1 flex-wrap min-h-[20px]">
      <el-tag
        v-for="tag in riskTags"
        :key="tag.text"
        size="small"
        :type="tag.type"
        effect="light"
        class="!text-[9px] !font-semibold !px-1.5 !py-0"
      >
        {{ tag.text }}
      </el-tag>
    </div>

    <!-- 底部状态栏 -->
    <div class="flex items-center text-[11px] mt-0.5 pt-1 border-t border-dashed border-med-border">
      <span class="status-dot w-1.5 h-1.5 rounded-full mr-1.5" :class="bed.status"></span>
      <span class="font-semibold text-med-text-2">{{ bedStatusLabel(bed.status) }}</span>
      <span v-if="bed.pending_events > 0" class="ml-auto text-[10px] text-med-danger font-bold">
        ⚠️ {{ bed.pending_events }}起待处理
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  bed: {
    type: Object,
    required: true
  }
})

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
  background: #00b42a;
  box-shadow: 0 0 6px rgba(0, 180, 42, 0.6);
}
.status-dot.idle {
  background: #86909c;
}
.status-dot.maintenance {
  background: #ff7d00;
}
.status-dot.alert {
  background: #f53f3f;
  box-shadow: 0 0 8px rgba(245, 63, 63, 0.6);
}

/* 告警态卡片高亮 */
.bed-headboard.alert {
  background: rgba(245, 63, 63, 0.06) !important;
}
</style>
