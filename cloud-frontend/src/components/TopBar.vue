<template>
  <header class="topbar" role="banner">
    <div class="topbar-brand">
      <div class="brand-mark" aria-hidden="true">
        <FirstAidKit class="brand-icon" />
      </div>
      <div class="brand-copy">
        <div class="brand-eyebrow">
          <span class="live-dot" aria-hidden="true"></span>
          <span>临床指挥台</span>
          <span class="eyebrow-rule" aria-hidden="true"></span>
          <span>实时监护</span>
        </div>
        <h1>第一人民医院 · 智慧病房</h1>
        <div class="brand-subtitle">
          <span>呼吸与危重症医学科</span>
          <span class="brand-divider" aria-hidden="true"></span>
          <span>W-01 病区</span>
        </div>
      </div>
    </div>

    <section class="shift-info" aria-label="当前值班人员">
      <div class="shift-heading">
        <span class="section-kicker">当前值守</span>
        <span class="shift-live"><span class="status-dot" aria-hidden="true"></span>交班中</span>
      </div>
      <div class="shift-roster">
        <div class="shift-item">
          <span class="person-avatar nurse" aria-hidden="true"><UserFilled class="shift-icon" /></span>
          <span class="shift-detail">
            <span class="shift-label">值班护士</span>
            <strong>张莉 <small>主管护师</small></strong>
          </span>
        </div>
        <span class="shift-divider" aria-hidden="true"></span>
        <div class="shift-item">
          <span class="person-avatar doctor" aria-hidden="true"><Avatar class="shift-icon" /></span>
          <span class="shift-detail">
            <span class="shift-label">责任医生</span>
            <strong>王主任</strong>
          </span>
        </div>
      </div>
    </section>

    <section class="kpi-strip" aria-label="病区运行指标">
      <div v-for="kpi in kpis" :key="kpi.key" class="kpi-card" :class="kpi.tone">
        <div class="kpi-label">
          <component :is="kpi.icon" class="kpi-icon" aria-hidden="true" />
          <span>{{ kpi.label }}</span>
        </div>
        <strong class="kpi-value">{{ kpi.value }}</strong>
      </div>
    </section>

    <div class="topbar-actions">
      <button
        type="button"
        class="model-button"
        title="打开模型管理"
        aria-label="打开模型管理"
        @click="emit('open-model')"
      >
        <Cpu class="action-icon" aria-hidden="true" />
        <span>模型管理</span>
        <span class="button-state" aria-hidden="true">EDGE</span>
      </button>
      <div class="clock-card" aria-label="当前时间">
        <div class="clock-topline">
          <span class="clock-label">值班时间</span>
          <span class="clock-zone">GMT+8</span>
        </div>
        <div class="clock-main">
          <Calendar class="clock-icon" aria-hidden="true" />
          <time class="clock-time" aria-live="polite">{{ props.currentTime || '--:--:--' }}</time>
        </div>
        <div class="clock-date">{{ currentDateStr }}</div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import {
  Avatar,
  Calendar,
  Connection,
  Cpu,
  DataBoard,
  FirstAidKit,
  Monitor,
  UserFilled,
  WarningFilled,
} from '@element-plus/icons-vue'

const props = defineProps({
  stats: {
    type: Object,
    required: true,
    default: () => ({})
  },
  currentTime: {
    type: String,
    required: true,
    default: ''
  }
})

const emit = defineEmits(['open-model'])

const numberValue = (value, fallback = 0) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

const formatCount = (value) => new Intl.NumberFormat('zh-CN').format(numberValue(value))

const kpis = computed(() => {
  const stats = props.stats || {}
  const onlineNodes = numberValue(stats.online_nodes)
  const totalNodes = numberValue(stats.total_nodes)
  const nodeDegraded = totalNodes > 0 && onlineNodes < totalNodes

  return [
    { key: 'beds', label: '总床位', value: stats.total_beds == null ? '—' : formatCount(stats.total_beds), icon: DataBoard, tone: 'neutral' },
    { key: 'occupied', label: '在床', value: stats.occupied_beds == null ? '—' : formatCount(stats.occupied_beds), icon: Monitor, tone: 'success' },
    { key: 'leave', label: '离床告警', value: stats.leave_beds == null ? '—' : formatCount(stats.leave_beds), icon: WarningFilled, tone: 'warning' },
    {
      key: 'nodes',
      label: '监测节点',
      value: totalNodes > 0 ? `${formatCount(onlineNodes)}/${formatCount(totalNodes)}` : '—',
      icon: Connection,
      tone: nodeDegraded ? 'warning' : 'neutral',
    },
    ...(numberValue(stats.p1_pending) > 0
      ? [{ key: 'p1', label: 'P1 待处置', value: formatCount(stats.p1_pending), icon: WarningFilled, tone: 'danger' }]
      : []),
  ]
})

const currentDateStr = computed(() => {
  const d = new Date()
  const weekDays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day} ${weekDays[d.getDay()]}`
})
</script>

<style scoped>
.topbar {
  --ink: #12272c;
  --ink-deep: #0c1c20;
  --ink-panel: #1b3439;
  --ink-line: rgba(207, 230, 224, 0.16);
  --warm: #f5f1e9;
  --warm-muted: #b7c6c2;
  --teal: #82d1c1;
  --teal-bright: #a8e6d8;
  --amber: #f1c88f;
  --coral: #ff8b78;

  position: relative;
  z-index: 20;
  display: grid;
  grid-template-columns: minmax(230px, 1.35fr) minmax(215px, .92fr) minmax(285px, 1.14fr) minmax(180px, .72fr);
  align-items: center;
  gap: clamp(10px, 1.1vw, 20px);
  min-height: 84px;
  padding: 12px clamp(14px, 2vw, 30px);
  color: var(--warm);
  background: var(--ink);
  border-bottom: 1px solid rgba(130, 209, 193, .35);
  box-shadow: 0 8px 24px rgba(11, 28, 32, .18);
  overflow: hidden;
}

.topbar::after {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: 2px;
  content: '';
  background: var(--teal);
  opacity: .65;
}

.topbar-brand,
.brand-eyebrow,
.brand-subtitle,
.shift-roster,
.shift-item,
.shift-heading,
.kpi-strip,
.kpi-label,
.topbar-actions,
.clock-topline,
.clock-main {
  display: flex;
  align-items: center;
}

.topbar-brand {
  min-width: 0;
  gap: 12px;
}

.brand-mark {
  display: grid;
  flex: 0 0 46px;
  place-items: center;
  width: 46px;
  height: 46px;
  color: var(--ink);
  background: var(--warm);
  border: 1px solid rgba(245, 241, 233, .8);
  border-radius: 10px;
  box-shadow: inset 0 0 0 4px rgba(130, 209, 193, .22), 0 5px 12px rgba(7, 22, 25, .24);
}

.brand-icon { width: 24px; height: 24px; }

.brand-copy { min-width: 0; }

.brand-eyebrow {
  gap: 6px;
  min-height: 14px;
  color: var(--teal-bright);
  font-size: 10px;
  line-height: 1;
  font-weight: 700;
  letter-spacing: 0;
  white-space: nowrap;
  text-transform: uppercase;
}

.live-dot,
.status-dot {
  display: inline-block;
  flex: 0 0 auto;
  width: 6px;
  height: 6px;
  background: var(--teal);
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgba(130, 209, 193, .16);
}

.eyebrow-rule {
  width: 22px;
  height: 1px;
  margin: 0 2px;
  background: rgba(168, 230, 216, .42);
}

.brand-copy h1 {
  margin: 4px 0 0;
  overflow: hidden;
  color: var(--warm);
  font-size: 18px;
  line-height: 1.15;
  font-weight: 800;
  letter-spacing: 0;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.brand-subtitle {
  gap: 8px;
  margin-top: 5px;
  overflow: hidden;
  color: var(--warm-muted);
  font-size: 11px;
  line-height: 1;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.brand-divider,
.shift-divider {
  width: 1px;
  height: 12px;
  flex: 0 0 1px;
  background: var(--ink-line);
}

.shift-info {
  min-width: 0;
  padding: 9px 12px 10px;
  background: rgba(255, 255, 255, .045);
  border: 1px solid var(--ink-line);
  border-radius: 8px;
}

.shift-heading {
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.section-kicker {
  color: var(--warm-muted);
  font-size: 10px;
  line-height: 1;
  letter-spacing: 0;
}

.shift-live {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--teal-bright);
  font-size: 10px;
  line-height: 1;
  white-space: nowrap;
}

.shift-live .status-dot {
  width: 5px;
  height: 5px;
  box-shadow: none;
}

.shift-roster {
  gap: 10px;
  min-width: 0;
}

.shift-item {
  min-width: 0;
  flex: 1 1 0;
  gap: 7px;
}

.person-avatar {
  display: grid;
  flex: 0 0 25px;
  place-items: center;
  width: 25px;
  height: 25px;
  color: var(--ink);
  border-radius: 50%;
}

.person-avatar.nurse { background: var(--teal); }
.person-avatar.doctor { background: var(--amber); }
.shift-icon { width: 13px; height: 13px; }

.shift-detail {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.shift-label {
  overflow: hidden;
  color: var(--warm-muted);
  font-size: 10px;
  line-height: 1;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.shift-item strong {
  overflow: hidden;
  color: var(--warm);
  font-size: 12px;
  line-height: 1;
  font-weight: 700;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.shift-item small {
  color: var(--warm-muted);
  font-size: 10px;
  font-weight: 500;
}

.kpi-strip {
  min-width: 0;
  gap: 6px;
  overflow-x: auto;
  scrollbar-width: none;
}

.kpi-strip::-webkit-scrollbar { display: none; }

.kpi-card {
  position: relative;
  min-width: 61px;
  flex: 0 0 auto;
  padding: 7px 8px 6px;
  overflow: hidden;
  text-align: center;
  background: var(--ink-panel);
  border: 1px solid var(--ink-line);
  border-radius: 8px;
}

.kpi-card::before {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  height: 2px;
  content: '';
  background: rgba(245, 241, 233, .3);
}

.kpi-card.success::before { background: var(--teal); }
.kpi-card.warning::before { background: var(--amber); }
.kpi-card.danger::before { background: var(--coral); }

.kpi-label {
  justify-content: center;
  gap: 4px;
  color: var(--warm-muted);
  font-size: 9px;
  line-height: 1;
  white-space: nowrap;
}

.kpi-icon { width: 11px; height: 11px; }
.kpi-card.neutral .kpi-icon { color: var(--teal); }
.kpi-card.success .kpi-icon { color: var(--teal-bright); }
.kpi-card.warning .kpi-icon { color: var(--amber); }
.kpi-card.danger .kpi-icon { color: var(--coral); }

.kpi-value {
  display: block;
  margin-top: 5px;
  color: var(--warm);
  font-family: 'Outfit', 'Inter', sans-serif;
  font-size: 16px;
  line-height: 1;
  font-weight: 800;
  white-space: nowrap;
}

.kpi-card.success .kpi-value { color: var(--teal-bright); }
.kpi-card.warning .kpi-value { color: var(--amber); }
.kpi-card.danger .kpi-value {
  color: var(--coral);
  animation: critical-value-pulse 1.6s ease-in-out infinite;
}

.topbar-actions {
  justify-content: flex-end;
  gap: 8px;
  min-width: 0;
}

.model-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 86px;
  min-height: 36px;
  padding: 0 10px;
  color: var(--warm);
  font: 600 11px/1 'Inter', 'PingFang SC', sans-serif;
  white-space: nowrap;
  background: transparent;
  border: 1px solid rgba(130, 209, 193, .42);
  border-radius: 8px;
  cursor: pointer;
  transition: color .2s ease, border-color .2s ease, background .2s ease, transform .2s ease;
}

.model-button:hover,
.model-button:focus-visible {
  color: var(--teal-bright);
  background: rgba(130, 209, 193, .1);
  border-color: var(--teal);
  outline: none;
}

.model-button:active { transform: translateY(1px); }
.action-icon { width: 14px; height: 14px; color: var(--teal); }

.button-state {
  padding: 3px 4px;
  color: var(--teal-bright);
  font-size: 8px;
  line-height: 1;
  letter-spacing: 0;
  background: rgba(130, 209, 193, .12);
  border-radius: 3px;
}

.clock-card {
  min-width: 142px;
  padding: 7px 10px 6px;
  background: var(--ink-deep);
  border: 1px solid var(--ink-line);
  border-radius: 8px;
}

.clock-topline {
  justify-content: space-between;
  gap: 8px;
  color: var(--warm-muted);
  font-size: 9px;
  line-height: 1;
}

.clock-zone {
  color: rgba(183, 198, 194, .66);
  font-size: 8px;
  letter-spacing: 0;
}

.clock-main {
  gap: 5px;
  margin-top: 4px;
}

.clock-icon { width: 12px; height: 12px; color: var(--teal); }

.clock-time {
  color: var(--warm);
  font-family: 'Outfit', 'Inter', sans-serif;
  font-size: 18px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: 0;
  white-space: nowrap;
}

.clock-date {
  margin-top: 5px;
  color: var(--warm-muted);
  font-size: 9px;
  line-height: 1;
  white-space: nowrap;
}

@keyframes critical-value-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: .62; }
}

@media (max-width: 1320px) {
  .topbar {
    grid-template-columns: minmax(215px, 1.25fr) minmax(205px, .9fr) minmax(280px, 1.1fr) auto;
    gap: 10px;
    padding-inline: 15px;
  }

  .brand-copy h1 { font-size: 16px; }
  .shift-info { padding-inline: 10px; }
  .shift-item small { display: none; }
  .kpi-card { min-width: 58px; padding-inline: 6px; }
  .button-state { display: none; }
  .model-button { min-width: 36px; width: 36px; padding: 0; }
  .model-button span { display: none; }
}

@media (max-width: 1050px) {
  .topbar {
    grid-template-columns: minmax(210px, 1fr) auto;
    grid-template-areas:
      'brand actions'
      'shift kpis';
    row-gap: 8px;
    min-height: 116px;
  }

  .topbar-brand { grid-area: brand; }
  .shift-info { grid-area: shift; }
  .kpi-strip { grid-area: kpis; max-width: 100%; }
  .topbar-actions { grid-area: actions; }
  .model-button span { display: inline; }
  .model-button { width: auto; min-width: 86px; padding-inline: 10px; }
}

@media (max-width: 680px) {
  .topbar {
    grid-template-columns: 1fr;
    grid-template-areas: 'brand' 'actions' 'shift' 'kpis';
    min-height: 0;
    padding: 11px 12px 13px;
  }

  .topbar-brand { align-items: flex-start; }
  .brand-mark { flex-basis: 40px; width: 40px; height: 40px; border-radius: 9px; }
  .brand-icon { width: 21px; height: 21px; }
  .brand-copy h1 { font-size: 16px; }
  .brand-subtitle { margin-top: 4px; }
  .topbar-actions { justify-content: space-between; }
  .model-button { flex: 1 1 auto; }
  .clock-card { flex: 0 0 auto; min-width: 144px; }
  .shift-info { padding: 9px 10px; }
  .kpi-strip { justify-content: flex-start; padding-bottom: 1px; }
}

@media (max-width: 420px) {
  .topbar { gap: 9px; }
  .brand-eyebrow { font-size: 9px; }
  .brand-subtitle { font-size: 10px; }
  .shift-roster { gap: 7px; }
  .shift-item { gap: 5px; }
  .shift-item strong { font-size: 11px; }
  .clock-card { min-width: 132px; padding-inline: 8px; }
  .clock-time { font-size: 16px; }
  .clock-zone { display: none; }
}

@media (prefers-reduced-motion: reduce) {
  .kpi-card.danger .kpi-value { animation: none; }
  .model-button { transition: none; }
}
</style>
