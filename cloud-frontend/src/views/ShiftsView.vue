<template>
  <div class="shifts-view">
    <!-- 主：交接班（云端统计摘要 + 边缘 LLM 自然交接班） -->
    <section class="panel acc-neutral shifts-main">
      <div class="panel-caption">
        <span class="caption-index">01</span>
        <span class="caption-title">临床护理交接班</span>
        <span class="caption-meta">交接责任护士：{{ STAFF.onDuty.name }} ({{ STAFF.onDuty.role }})</span>
      </div>

      <!-- 云端规则摘要（保留） -->
      <ShiftPanel
        :shift-summaries="state.shiftSummaries"
        :generating="state.generating"
        v-model:shift-date="state.shiftDate"
        v-model:shift-period="state.shiftPeriod"
        @generate="store.onGenerateSummary"
        @delete-summary="store.onDeleteSummary"
      />

      <div class="panel-divider" aria-hidden="true"></div>

      <!-- 边缘 LLM 自然交接班（agent 生成） -->
      <div class="edge-handover">
        <div class="eh-head">
          <span class="eh-title">
            <el-icon :size="14" aria-hidden="true"><Document /></el-icon>
            边缘 LLM 交接班
          </span>
          <span class="chip chip-primary">由边缘本地模型生成</span>
        </div>
        <div class="eh-form">
          <el-select v-model="state.edgeBedId" size="small" class="eh-bed-select">
            <el-option value="B01" label="B01 · 张阿姨" />
            <el-option value="B02" label="B02 · 李伯伯" />
            <el-option value="B03" label="B03 · 王奶奶" />
          </el-select>
          <el-button
            type="primary"
            size="small"
            :loading="state.handoverGenerating"
            class="eh-generate"
            @click="store.generateEdgeHandover"
          >
            {{ state.handoverGenerating ? '边缘模型生成中…' : '生成自然交接班' }}
          </el-button>
        </div>
        <p v-if="state.edgeHandoverError" class="eh-error">
          <el-icon :size="13" aria-hidden="true"><WarningFilled /></el-icon>
          {{ state.edgeHandoverError }}
        </p>

        <ul v-if="state.edgeHandovers.length" class="eh-list">
          <li v-for="h in state.edgeHandovers" :key="h.id || h.generated_at" class="eh-card">
            <div class="eh-card-head">
              <span class="eh-card-bed">{{ h.bed_id }} · {{ h.shift_date }} {{ periodLabel(h.shift_period) }}</span>
              <span class="eh-badge">
                <el-icon :size="11" aria-hidden="true"><Cpu /></el-icon>
                {{ h.mode === 'real' ? '边缘 LLM' : '边缘 mock' }}
              </span>
            </div>
            <div class="eh-text">{{ h.handover_text }}</div>
            <div v-if="h.watch_points && h.watch_points.length" class="eh-watch">
              <span class="ew-title">交班注意：</span>
              <span v-for="(p, i) in h.watch_points" :key="i" class="ew-item">{{ p }}</span>
            </div>
            <div class="eh-meta">
              <span v-if="h.event_count != null">{{ h.event_count }} 起事件 · P1 {{ h.p1_count }}</span>
              <span>{{ h.model_name }}@{{ h.model_version }}</span>
              <span v-if="h.trace_id">trace {{ String(h.trace_id).slice(0, 12) }}</span>
              <span v-if="h.generated_at">{{ fmtLocal(h.generated_at) }}</span>
            </div>
          </li>
        </ul>
        <div v-else class="eh-empty">暂无边缘 LLM 交接班记录，点击"生成自然交接班"由边端本地模型生成</div>
      </div>
    </section>

    <!-- 侧：事件趋势 + 边缘 Agent 问答 -->
    <aside class="panel acc-accent shifts-side">
      <div class="panel-caption">
        <span class="caption-index">02</span>
        <span class="caption-title">事件趋势</span>
        <span class="caption-meta">24h · 类别占比</span>
      </div>
      <EventTrendChart :demo-mode="state.demoMode" :refresh-tick="state.refreshTick" />
      <div class="panel-divider" aria-hidden="true"></div>
      <div class="shift-stats">
        <div class="shift-stat-row">
          <span class="ss-label">本班次事件</span>
          <strong class="ss-value font-num">{{ state.stats.events_today ?? '—' }}</strong>
        </div>
        <div class="shift-stat-row">
          <span class="ss-label">P1 待处置</span>
          <strong class="ss-value font-num t-danger">{{ state.stats.p1_pending ?? '—' }}</strong>
        </div>
        <div class="shift-stat-row">
          <span class="ss-label">离床告警</span>
          <strong class="ss-value font-num t-warning">{{ state.stats.leave_beds ?? '—' }}</strong>
        </div>
      </div>

      <div class="panel-divider" aria-hidden="true"></div>
      <EdgeAgentAskPanel />
    </aside>
  </div>
</template>

<script setup>
import ShiftPanel from '../components/ShiftPanel.vue'
import EventTrendChart from '../components/EventTrendChart.vue'
import EdgeAgentAskPanel from '../components/EdgeAgentAskPanel.vue'
import { Document, WarningFilled, Cpu } from '@element-plus/icons-vue'
import { useWardStore } from '../stores/ward.js'
import { STAFF } from '../mock/wardProfile.js'

const store = useWardStore()
const { state } = store

const periodLabel = (p) => ({ day: '白班', evening: '晚班', night: '夜班' }[p] || p)

const fmtLocal = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.shifts-view {
  display: grid;
  grid-template-columns: minmax(440px, 1.4fr) minmax(320px, 0.8fr);
  gap: 14px;
  height: 100%;
  min-height: 0;
}

.shifts-main, .shifts-side { overflow-y: auto; }

.shift-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.shift-stat-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 11px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 9px;
}
.ss-label { color: var(--text-3); font-size: var(--fs-body); font-weight: 600; }
.ss-value { color: var(--text); font-size: var(--fs-title); font-weight: 800; }

/* 边缘 LLM 交接班 */
.edge-handover { display: flex; flex-direction: column; gap: 10px; margin-top: 4px; }
.eh-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.eh-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--primary);
  font-size: var(--fs-body-lg);
  font-weight: 800;
}
.eh-form { display: flex; gap: 8px; }
.eh-bed-select { width: 150px; }
.eh-generate { font-weight: 700; }
.eh-error {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--danger);
  font-size: var(--fs-body);
  font-weight: 600;
}
.eh-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
  list-style: none;
  padding: 0;
  margin: 0;
}
.eh-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 13px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-left: 3px solid var(--success);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
}
.eh-card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.eh-card-bed { color: var(--primary); font-size: var(--fs-body-lg); font-weight: 800; }
.eh-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-micro);
  font-weight: 700;
  color: var(--success);
  background: rgba(22, 163, 74, 0.1);
  border: 1px solid rgba(22, 163, 74, 0.28);
  padding: 3px 8px;
  border-radius: 999px;
  white-space: nowrap;
}
.eh-text { color: var(--text-2); font-size: var(--fs-body); line-height: 1.75; white-space: pre-wrap; }
.eh-watch { display: flex; flex-wrap: wrap; gap: 6px; align-items: baseline; }
.ew-title { color: var(--text-3); font-size: var(--fs-caption); font-weight: 700; }
.ew-item {
  font-size: var(--fs-caption);
  font-weight: 600;
  color: var(--warning);
  background: rgba(217, 119, 6, 0.08);
  border: 1px solid rgba(217, 119, 6, 0.25);
  padding: 3px 8px;
  border-radius: 6px;
}
.eh-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--text-3);
  font-size: 11.5px;
  font-weight: 600;
}
.eh-empty { color: var(--text-3); font-size: 12px; padding: 8px 2px; }

@media (max-width: 1020px) {
  .shifts-view {
    display: flex;
    flex-direction: column;
    height: auto;
    min-height: 100%;
    overflow-y: auto;
  }
  .shifts-main { min-height: 460px; }
}
</style>
