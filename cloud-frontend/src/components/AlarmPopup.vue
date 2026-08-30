<template>
  <transition name="alarm-pop">
    <div v-if="event" class="alarm-popup" role="alert" aria-live="assertive">
      <div class="alarm-icon" aria-hidden="true">
        <el-icon :size="26"><WarningFilled /></el-icon>
      </div>

      <div class="alarm-body">
        <div class="alarm-head">
          <span class="alarm-tag">P1 紧急告警</span>
          <span class="alarm-time font-num">{{ fmtDateTime(event.occurred_at) }}</span>
          <button class="alarm-close" title="关闭" @click="$emit('close')">×</button>
        </div>
        <div class="alarm-title">{{ eventTypeLabel(event.event_type) }}</div>
        <div class="alarm-meta">
          <span class="meta-bed">{{ event.bed_id || '—' }} 床</span>
          <span class="meta-conf font-num">置信度 {{ pct(event.confidence) }}</span>
          <span v-if="routeOf(event)" class="meta-route">{{ routeLabel(routeOf(event)) }}链路研判</span>
        </div>
      </div>

      <div class="alarm-actions">
        <button class="btn-ack" @click="$emit('ack')">立即到场</button>
        <button class="btn-view" @click="$emit('view')">查看详情</button>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { WarningFilled } from '@element-plus/icons-vue'
import { resolveRoute, routeLabel } from '../utils/eventMeta.js'

defineProps({
  event: { type: Object, default: null },
})

defineEmits(['ack', 'view', 'close'])

const eventTypeLabel = (t) => ({
  fall_suspected: '疑似跌倒',
  nurse_call: '护士呼叫',
  bed_leave: '患者离床',
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
}[t] || t)

const routeOf = (evt) => resolveRoute(evt)

const pct = (v) => {
  const n = Number(v)
  return Number.isFinite(n) ? `${(n * 100).toFixed(0)}%` : '—'
}

const fmtDateTime = (ts) => {
  if (!ts) return '—'
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return String(ts)
  const p = (x) => String(x).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
</script>

<style scoped>
.alarm-popup {
  position: fixed;
  top: 84px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1200;
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 460px;
  max-width: calc(100vw - 260px);
  padding: 12px 16px 12px 14px;
  border-radius: 12px;
  background: linear-gradient(135deg, #FEF2F2 0%, #FFFFFF 55%, #FFF7F7 100%);
  border: 1.5px solid var(--danger);
  box-shadow: 0 14px 40px rgba(220, 38, 38, 0.28), 0 2px 6px rgba(220, 38, 38, 0.12);
  animation: alarm-breathe 1.2s ease-in-out infinite;
}

@keyframes alarm-breathe {
  0%, 100% { box-shadow: 0 14px 40px rgba(220, 38, 38, 0.28), 0 2px 6px rgba(220, 38, 38, 0.12); }
  50% { box-shadow: 0 14px 52px rgba(220, 38, 38, 0.48), 0 2px 10px rgba(220, 38, 38, 0.22); }
}

.alarm-icon {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  color: #fff;
  background: linear-gradient(135deg, var(--danger), var(--danger-strong));
  animation: icon-pulse 1.2s ease-in-out infinite;
}

@keyframes icon-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.08); }
}

.alarm-body {
  flex: 1;
  min-width: 0;
}

.alarm-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.alarm-tag {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: var(--danger-strong);
  background: var(--danger-soft);
  border: 1px solid rgba(220, 38, 38, 0.35);
  border-radius: 999px;
  padding: 2px 10px;
}

.alarm-time {
  font-size: 12px;
  color: var(--text-3);
}

.alarm-close {
  margin-left: auto;
  border: none;
  background: transparent;
  font-size: 18px;
  line-height: 1;
  color: var(--text-3);
  cursor: pointer;
  padding: 0 4px;
}

.alarm-close:hover { color: var(--danger-strong); }

.alarm-title {
  margin-top: 3px;
  font-size: 19px;
  font-weight: 700;
  color: var(--danger-strong);
  line-height: 1.3;
}

.alarm-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 3px;
  font-size: 13px;
  color: var(--text-2);
}

.meta-bed { font-weight: 600; color: var(--text); }

.meta-conf {
  color: var(--danger);
  font-weight: 600;
}

.meta-route {
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 6px;
  padding: 1px 8px;
  font-size: 12px;
}

.alarm-actions {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.btn-ack, .btn-view {
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  padding: 7px 16px;
  white-space: nowrap;
}

.btn-ack {
  color: #fff;
  background: linear-gradient(135deg, var(--danger), var(--danger-strong));
  border: 1px solid var(--danger-strong);
}

.btn-ack:hover { filter: brightness(1.08); }

.btn-view {
  color: var(--text-2);
  background: #fff;
  border: 1px solid var(--line-strong);
}

.btn-view:hover { color: var(--danger-strong); border-color: var(--danger); }

/* 滑入动画 */
.alarm-pop-enter-active { transition: all 0.28s cubic-bezier(0.34, 1.4, 0.64, 1); }
.alarm-pop-leave-active { transition: all 0.2s ease; }
.alarm-pop-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(-16px) scale(0.96);
}
.alarm-pop-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(-10px) scale(0.97);
}
</style>
