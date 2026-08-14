<template>
  <header class="topbar" role="banner">
    <!-- 左：当前视图标题 -->
    <div class="topbar-heading">
      <div class="heading-line">
        <span class="live-badge" aria-hidden="true">
          <span class="live-dot"></span>LIVE
        </span>
        <h1>{{ pageTitle }}</h1>
      </div>
      <p class="heading-sub">{{ pageSub }}</p>
    </div>

    <!-- 中：病区运行指标 -->
    <section class="kpi-strip" aria-label="病区运行指标">
      <div v-for="kpi in kpis" :key="kpi.key" class="kpi-card" :class="kpi.tone">
        <span class="kpi-top">
          <span class="kpi-label">{{ kpi.label }}</span>
          <el-icon :size="13" class="kpi-icon" aria-hidden="true"><component :is="kpi.icon" /></el-icon>
        </span>
        <strong class="kpi-value font-num">{{ kpi.value }}</strong>
      </div>
    </section>

    <!-- 右：当前值守 + 模型管理 + 时钟 -->
    <div class="topbar-actions">
      <section class="roster" aria-label="当前值守人员">
        <div class="roster-item">
          <span class="roster-avatar nurse" aria-hidden="true"><el-icon :size="12"><UserFilled /></el-icon></span>
          <span class="roster-meta">
            <span class="roster-role">值班护士</span>
            <strong class="roster-name">{{ STAFF.onDuty.name }}<small>{{ STAFF.onDuty.role }}</small></strong>
          </span>
        </div>
        <div class="roster-item">
          <span class="roster-avatar doctor" aria-hidden="true"><el-icon :size="12"><Avatar /></el-icon></span>
          <span class="roster-meta">
            <span class="roster-role">责任医生</span>
            <strong class="roster-name">{{ STAFF.doctor.name }}<small>{{ STAFF.doctor.role }}</small></strong>
          </span>
        </div>
      </section>

      <button
        type="button"
        class="model-button"
        title="打开模型管理"
        aria-label="打开模型管理"
        @click="emit('open-model')"
      >
        <el-icon :size="15" class="model-icon" aria-hidden="true"><Cpu /></el-icon>
        <span class="model-text">模型管理</span>
      </button>

      <div class="clock-card" aria-label="当前时间">
        <span class="clock-label">值班时间 · GMT+8</span>
        <time class="clock-time font-num" aria-live="polite">{{ props.currentTime || '--:--:--' }}</time>
        <span class="clock-date font-num">{{ currentDateStr }}</span>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import {
  Avatar, Connection, Cpu, DataBoard, Monitor, UserFilled, WarningFilled,
} from '@element-plus/icons-vue'
import { STAFF } from '../mock/wardProfile.js'

const props = defineProps({
  stats: { type: Object, required: true, default: () => ({}) },
  currentTime: { type: String, required: true, default: '' },
  pageTitle: { type: String, default: '总览大屏' },
  pageSub: { type: String, default: '' },
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
  --bar-tone: rgba(255, 255, 255, 0.82);

  position: relative;
  z-index: 20;
  display: grid;
  grid-template-columns: minmax(210px, 0.9fr) minmax(300px, 1.35fr) minmax(330px, 1fr);
  align-items: center;
  gap: clamp(14px, 1.6vw, 28px);
  min-height: 72px;
  padding: 10px clamp(14px, 1.6vw, 22px);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0) 46%),
    var(--bar-tone);
  border-bottom: 1px solid var(--line);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  overflow: hidden;
}

/* 底部霓虹下划线 */
.topbar::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent 2%, rgba(42, 125, 225, 0.45) 30%, rgba(14, 165, 233, 0.30) 68%, transparent 98%);
}

/* ---- 左：标题 ---- */
.topbar-heading { min-width: 0; }
.heading-line { display: flex; align-items: center; gap: 10px; min-width: 0; }
.heading-line h1 {
  margin: 0;
  color: var(--text);
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.heading-sub {
  margin: 4px 0 0;
  color: var(--text-3);
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.live-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: 0 0 auto;
  height: 20px;
  padding: 0 8px;
  border-radius: 10px;
  color: var(--primary);
  background: var(--primary-soft);
  border: 1px solid rgba(42, 125, 225, 0.35);
  font: 800 9px/1 'Outfit', 'Inter', sans-serif;
  letter-spacing: 0.12em;
}
.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
  box-shadow: 0 0 7px rgba(42, 125, 225, 0.6);
  animation: med-blink 1.6s ease-in-out infinite;
}

/* ---- 中：KPI ---- */
.kpi-strip {
  display: flex;
  gap: 8px;
  min-width: 0;
  justify-content: center;
}
.kpi-card {
  position: relative;
  flex: 1 1 0;
  min-width: 58px;
  max-width: 108px;
  padding: 7px 10px 8px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 9px;
  overflow: hidden;
}
.kpi-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--info);
  opacity: 0.6;
}
.kpi-card.success::before { background: var(--success); }
.kpi-card.warning::before { background: var(--warning); }
.kpi-card.danger::before { background: var(--danger); box-shadow: 0 0 8px rgba(220, 38, 38, 0.6); }

.kpi-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  color: var(--text-3);
}
.kpi-label { font-size: 10px; font-weight: 700; white-space: nowrap; }
.kpi-icon { flex: 0 0 auto; }
.kpi-card.success .kpi-icon { color: var(--success); }
.kpi-card.warning .kpi-icon { color: var(--warning); }
.kpi-card.danger .kpi-icon { color: var(--danger); }
.kpi-card.neutral .kpi-icon { color: var(--primary); }

.kpi-value {
  display: block;
  margin-top: 5px;
  color: var(--text);
  font-size: 20px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}
.kpi-card.success .kpi-value { color: var(--success); }
.kpi-card.warning .kpi-value { color: var(--warning); }
.kpi-card.danger .kpi-value {
  color: var(--danger);
  text-shadow: 0 0 12px rgba(220, 38, 38, 0.30);
  animation: med-text-pulse 1.6s ease-in-out infinite;
}

/* ---- 右：值守 / 按钮 / 时钟 ---- */
.topbar-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  min-width: 0;
}

.roster {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(24, 48, 76, 0.04);
  border: 1px solid var(--line);
  border-radius: 9px;
}
.roster-item {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  padding-right: 8px;
  border-right: 1px solid var(--line);
}
.roster-item:last-child { padding-right: 0; border-right: 0; }
.roster-avatar {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  flex: 0 0 26px;
  border-radius: 50%;
  color: #FFFFFF;
}
.roster-avatar.nurse { background: linear-gradient(135deg, #7CB4FF, #2A7DE1); box-shadow: 0 0 8px rgba(42, 125, 225, 0.3); }
.roster-avatar.doctor { background: linear-gradient(135deg, #FDE68A, #FBBF24); box-shadow: 0 0 8px rgba(217, 119, 6, 0.25); }
.roster-meta { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.roster-role { color: var(--text-3); font-size: 9px; font-weight: 700; line-height: 1; white-space: nowrap; }
.roster-name {
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
}
.roster-name small { margin-left: 4px; color: var(--text-3); font-size: 9px; font-weight: 600; }

.model-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 34px;
  padding: 0 12px;
  color: var(--text-2);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  background: transparent;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.model-button:hover, .model-button:focus-visible {
  color: var(--primary);
  background: var(--primary-soft);
  border-color: rgba(42, 125, 225, 0.45);
  box-shadow: 0 0 12px rgba(42, 125, 225, 0.14);
  outline: none;
}
.model-button:active { transform: translateY(1px); }
.model-icon { color: var(--primary); }

.clock-card {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  min-width: 132px;
  padding: 6px 12px 7px;
  background: var(--bg-deep);
  border: 1px solid var(--line-strong);
  border-radius: 9px;
  box-shadow: inset 0 0 22px rgba(42, 125, 225, 0.06);
}
.clock-label { color: var(--text-3); font-size: 9px; font-weight: 700; line-height: 1; }
.clock-time {
  color: var(--primary);
  font-size: 21px;
  font-weight: 800;
  line-height: 1;
  text-shadow: 0 0 14px rgba(42, 125, 225, 0.25);
  letter-spacing: 0.04em;
}
.clock-date { color: var(--text-3); font-size: 9px; line-height: 1; }

/* ---- 响应式 ---- */
@media (max-width: 1380px) {
  .topbar { grid-template-columns: minmax(190px, 0.8fr) minmax(280px, 1.25fr) auto; }
  .roster { display: none; }
}
@media (max-width: 1080px) {
  .topbar {
    grid-template-columns: minmax(180px, 1fr) auto;
    grid-template-areas: 'heading actions' 'kpis kpis';
    row-gap: 8px;
    min-height: 0;
    padding-block: 10px;
  }
  .topbar-heading { grid-area: heading; }
  .kpi-strip { grid-area: kpis; justify-content: flex-start; overflow-x: auto; }
  .topbar-actions { grid-area: actions; }
}
@media (max-width: 640px) {
  .topbar { grid-template-columns: 1fr; grid-template-areas: 'heading' 'actions' 'kpis'; }
  .topbar-actions { justify-content: space-between; }
  .clock-card { min-width: 124px; }
}
@media (prefers-reduced-motion: reduce) {
  .live-dot, .kpi-card.danger .kpi-value { animation: none; }
}
</style>
