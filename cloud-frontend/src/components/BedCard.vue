<template>
  <div
    class="bed-card"
    :class="[
      bed.status === 'alert' ? 'bed-card-alert' : 'bed-card-normal',
      { alert: bed.pending_events > 0 }
    ]"
  >
    <!-- 顶行：床号 + 护理等级 -->
    <div class="bed-head">
      <div class="bed-name font-num">
        <span class="bed-index-bar" aria-hidden="true"></span>
        {{ bed.name }}
      </div>
      <span class="chip" :class="'chip-' + patient.careLevel.tone">{{ patient.careLevel.label }}</span>
    </div>

    <!-- 患者主信息 -->
    <div class="bed-patient">
      <template v-if="bed.patient_alias">
        <span class="patient-alias">{{ bed.patient_alias }}</span>
        <span v-if="patient.gender || patient.age" class="patient-meta font-num">
          ({{ patient.gender }}{{ patient.age != null ? `, ${patient.age}岁` : '' }})
        </span>
      </template>
      <span v-else class="patient-empty">空床 (无加床登记)</span>
    </div>

    <!-- 医护信息 -->
    <div class="bed-staff">
      <span class="staff-item">责护 <strong>{{ patient.nurse }}</strong></span>
      <span class="staff-item">主管 <strong>{{ patient.doctor }}</strong></span>
    </div>

    <!-- 风险标签 + 链路/网络徽章 -->
    <div class="bed-tags">
      <span
        v-for="tag in patient.risks"
        :key="tag.text"
        class="chip"
        :class="'chip-' + tag.tone"
      >{{ tag.text }}</span>

      <span
        v-if="latestEvent"
        class="chip font-num"
        :class="'chip-' + routeOf(latestEvent)"
        :title="routeDesc(routeOf(latestEvent))"
      >
        <span class="route-mark" aria-hidden="true"></span>{{ routeLabel(routeOf(latestEvent)) }}
      </span>

      <span
        v-if="nodeStatus"
        class="chip font-num"
        :class="'chip-net-' + nodeStatus"
      >{{ nodeStatusLabel }}</span>
    </div>

    <!-- 底部状态栏 -->
    <div class="bed-foot">
      <span class="dot" :class="bed.status" aria-hidden="true"></span>
      <span class="bed-status">{{ bedStatusLabel(bed.status) }}</span>

      <span v-if="modelVersion" class="bed-model font-num" :title="modelVersion">{{ modelVersion }}</span>

      <button
        @click.stop="$emit('showMonitor', bed)"
        class="bed-monitor-btn"
        :class="bed.status === 'alert' ? 'is-alert' : 'is-normal'"
        :aria-label="`打开${bed.name}监护画面`"
      >
        <el-icon :size="13" aria-hidden="true"><VideoCamera /></el-icon>
        监护
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { VideoCamera } from '@element-plus/icons-vue'
import { resolveRoute, routeLabel, routeDesc, networkMeta } from '../utils/eventMeta.js'
import { patientOf } from '../mock/wardProfile.js'

const props = defineProps({
  bed: { type: Object, required: true },
  // 该床最新事件（用于展示推理链路）
  latestEvent: { type: Object, default: null },
  // 节点状态 online/degraded/offline
  nodeStatus: { type: String, default: '' },
  // 节点模型版本
  modelVersion: { type: String, default: '' },
})

defineEmits(['showMonitor'])

const patient = computed(() => patientOf(props.bed.id))

const routeOf = (evt) => resolveRoute(evt)

const nodeStatusLabel = computed(() => {
  if (!props.nodeStatus) return ''
  return networkMeta(props.nodeStatus).label.replace('网络', '')
})

const bedStatusLabel = (status) => ({
  idle: '空闲',
  occupied: '在床',
  alert: '告警/呼叫中',
  maintenance: '设备维护',
}[status] || status)
</script>

<style scoped>
.bed-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 12px 11px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 11px;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
.bed-card:hover {
  transform: translateY(-1px);
  border-color: rgba(42, 125, 225, 0.42);
  box-shadow: 0 8px 20px rgba(24, 48, 76, 0.10), 0 0 12px rgba(42, 125, 225, 0.08);
}

/* 告警态：呼吸光晕 */
.bed-card.alert {
  border-color: rgba(220, 38, 38, 0.45);
  background:
    linear-gradient(180deg, rgba(220, 38, 38, 0.05), rgba(220, 38, 38, 0) 42%),
    var(--surface-2);
  animation: med-pulse-danger 1.9s ease-in-out infinite;
}

/* 头部 */
.bed-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line);
}
.bed-name {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--text);
  font-size: 17px;
  font-weight: 800;
}
.bed-index-bar {
  width: 4px;
  height: 16px;
  border-radius: 2px;
  background: linear-gradient(180deg, #7CB4FF, var(--primary));
  box-shadow: 0 0 6px rgba(42, 125, 225, 0.35);
}
.bed-card.alert .bed-index-bar {
  background: linear-gradient(180deg, #FCA5A5, var(--danger));
  box-shadow: 0 0 6px rgba(220, 38, 38, 0.4);
}

/* 患者 */
.bed-patient { display: flex; align-items: baseline; gap: 6px; min-height: 20px; }
.patient-alias { color: var(--text); font-size: 14px; font-weight: 700; }
.patient-meta { color: var(--text-3); font-size: 11.5px; font-weight: 600; }
.patient-empty { color: var(--text-3); font-size: 11.5px; font-style: italic; }

/* 医护 */
.bed-staff {
  display: flex;
  justify-content: space-between;
  padding: 5px 9px;
  background: rgba(24, 48, 76, 0.04);
  border: 1px solid var(--line);
  border-radius: 7px;
}
.staff-item { color: var(--text-3); font-size: 12px; font-weight: 600; }
.staff-item strong { color: var(--text-2); font-weight: 700; }

/* 标签 */
.bed-tags {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  min-height: 20px;
  align-items: center;
}
.route-mark {
  display: inline-block;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

/* 底部 */
.bed-foot {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  padding-top: 8px;
  border-top: 1px dashed var(--line);
}
.bed-status {
  color: var(--text-2);
  font-size: 11.5px;
  font-weight: 700;
  white-space: nowrap;
}
.bed-model {
  margin-left: 2px;
  color: var(--text-3);
  font-size: 11.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 86px;
}

.bed-monitor-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  height: 24px;
  padding: 0 9px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
}
.bed-monitor-btn.is-normal {
  color: var(--text-2);
  background: transparent;
  border: 1px solid var(--line-strong);
}
.bed-monitor-btn.is-normal:hover {
  color: var(--primary);
  background: var(--primary-soft);
  border-color: rgba(42, 125, 225, 0.45);
}
.bed-monitor-btn.is-alert {
  color: #fff;
  background: var(--danger-strong);
  border: 1px solid var(--danger-strong);
  box-shadow: 0 3px 10px rgba(220, 38, 38, 0.28);
}
.bed-monitor-btn.is-alert:hover { background: #D63B3B; border-color: #D63B3B; }

@media (max-width: 1450px) {
  .bed-model { display: none; }
}
</style>
