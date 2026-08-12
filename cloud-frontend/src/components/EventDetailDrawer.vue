<template>
  <div v-if="visible" class="detail-overlay" @click.self="$emit('close')">
    <div class="detail-panel">
      <div class="detail-head">
        <div class="detail-title">
          <h2>🔍 事件详情与链路追踪</h2>
          <span class="detail-sub">{{ eventId }}</span>
        </div>
        <button class="detail-close" @click="$emit('close')">&times;</button>
      </div>

      <div class="detail-body">
        <div v-if="loading" class="detail-loading">加载中...</div>
        <template v-else-if="detail">
          <!-- 链路摘要 -->
          <div class="route-summary" :class="'route-' + route">
            <div class="route-badge">
              <span class="route-icon">{{ routeIcon }}</span>
              <div>
                <div class="route-label">推理链路：{{ routeLabel(route) }} · {{ routeDesc(route) }}</div>
                <div class="route-meta">事件 {{ stateLabel(detail.state) }} · {{ priorityLabel }} · {{ detail.bed_id }}床</div>
              </div>
            </div>
          </div>

          <!-- 追踪标识 -->
          <div class="trace-block">
            <div class="trace-row">
              <span class="trace-label">event_id</span>
              <code class="trace-code">{{ detail.event_id }}</code>
              <button class="trace-copy" @click="copyText(detail.event_id)">复制</button>
            </div>
            <div class="trace-row">
              <span class="trace-label">trace_id</span>
              <code class="trace-code">{{ traceId || '—' }}</code>
              <button v-if="traceId" class="trace-copy" @click="copyText(traceId)">复制</button>
            </div>
            <div class="trace-row">
              <span class="trace-label">node_id</span>
              <code class="trace-code">{{ detail.node_id || '—' }}</code>
            </div>
          </div>

          <!-- 性能指标 -->
          <div class="perf-grid">
            <div class="perf-item">
              <div class="perf-label">边缘推理耗时</div>
              <div class="perf-value">{{ fmtMs(perf.inference_ms) }}</div>
            </div>
            <div class="perf-item">
              <div class="perf-label">TTFT 首token</div>
              <div class="perf-value">{{ fmtMs(perf.ttft_ms) }}</div>
            </div>
            <div class="perf-item">
              <div class="perf-label">云端往返延迟</div>
              <div class="perf-value">{{ fmtMs(perf.cloud_latency_ms) }}</div>
            </div>
            <div class="perf-item">
              <div class="perf-label">峰值内存</div>
              <div class="perf-value">{{ fmtBytesToMb(perf.memory_mb) }}</div>
            </div>
          </div>

          <!-- 云端二次研判 -->
          <div v-if="cloudInference" class="cloud-block" :class="'tone-' + cloudTone">
            <div class="section-title">云端二次研判</div>
            <div class="cloud-head">
              <span class="cloud-judge">{{ cloudJudgeLabel }}</span>
              <span class="cloud-status">{{ cloudStatusLabel }}</span>
            </div>
            <div class="cloud-advice">{{ cloudInference.advice || '（云端未给出建议）' }}</div>
            <div class="cloud-meta">
              <span class="cloud-meta-item">置信度 <b class="font-num">{{ cloudConfPct }}</b></span>
              <span class="cloud-meta-item">延迟 <b class="font-num">{{ fmtMs(cloudInference.latency_ms) }}</b></span>
              <span v-if="cloudInference.trace_id" class="cloud-meta-item trace">trace <code>{{ cloudInference.trace_id }}</code></span>
            </div>
          </div>

          <!-- 模型信息 -->
          <div class="model-block">
            <div class="model-line">
              <span class="model-key">模型名称</span>
              <span class="model-val">{{ detail.model?.name || detail.model_name || '—' }}</span>
            </div>
            <div class="model-line">
              <span class="model-key">模型版本</span>
              <span class="model-val">{{ detail.model?.version || detail.model_version || '—' }}</span>
            </div>
            <div class="model-line">
              <span class="model-key">置信度</span>
              <span class="model-val font-num">{{ confPct }}</span>
            </div>
          </div>

          <!-- 时间线 -->
          <div class="timeline">
            <div class="tl-row"><span class="tl-key">发生时间</span><span class="tl-val">{{ fmtDateTime(detail.occurred_at) }}</span></div>
            <div v-if="detail.acknowledged_at" class="tl-row"><span class="tl-key">确认时间</span><span class="tl-val">{{ fmtDateTime(detail.acknowledged_at) }}</span></div>
            <div v-if="detail.resolved_at" class="tl-row"><span class="tl-key">归档时间</span><span class="tl-val">{{ fmtDateTime(detail.resolved_at) }}</span></div>
          </div>

          <!-- 规则命中 / 证据 -->
          <div v-if="detail.rule_hits && detail.rule_hits.length" class="detail-section">
            <div class="section-title">规则命中</div>
            <div class="tag-list">
              <span v-for="(r, i) in detail.rule_hits" :key="i" class="meta-tag">{{ typeof r === 'string' ? r : (r.name || r.rule || JSON.stringify(r)) }}</span>
            </div>
          </div>

          <div v-if="detail.evidence_refs && detail.evidence_refs.length" class="detail-section">
            <div class="section-title">证据引用</div>
            <code class="evidence-code">{{ detail.evidence_refs.join(' · ') }}</code>
          </div>

          <!-- 附加明细 -->
          <div v-if="detail.details && Object.keys(detail.details).length" class="detail-section">
            <div class="section-title">附加明细</div>
            <pre class="details-pre">{{ JSON.stringify(detail.details, null, 2) }}</pre>
          </div>

          <!-- 处置记录 -->
          <div v-if="detail.dispositions && detail.dispositions.length" class="detail-section">
            <div class="section-title">处置记录</div>
            <div v-for="(d, i) in detail.dispositions" :key="i" class="disp-row">
              <el-tag size="small" :type="dispTagType(d.action)" effect="light" class="!text-[10px]">{{ dispLabel(d.action) }}</el-tag>
              <span class="disp-op">{{ d.operator_name || d.operator_id }}</span>
              <span class="disp-time">{{ fmtDateTime(d.occurred_at) }}</span>
            </div>
          </div>
        </template>
        <div v-else class="detail-loading">未找到事件或事件已失效</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import api from '../api/index.js'
import {
  resolveRoute, routeLabel, routeDesc,
  stateLabel, getPerf, fmtMs, fmtBytesToMb, fmtDateTime,
  getCloudInference, cloudJudgmentMeta,
} from '../utils/eventMeta.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  eventId: { type: String, default: '' },
})

const emit = defineEmits(['close'])

const loading = ref(false)
const detail = ref(null)

const load = async () => {
  if (!props.eventId) return
  loading.value = true
  try {
    const res = await api.getEvent(props.eventId)
    detail.value = res.data?.data || null
  } catch (e) {
    console.error('加载事件详情失败', e)
    detail.value = null
  } finally {
    loading.value = false
  }
}

watch(() => props.visible, (v) => {
  if (v) load()
})

watch(() => props.eventId, () => {
  if (props.visible) load()
})

const route = computed(() => resolveRoute(detail.value || {}))
const routeIcon = computed(() => ({ edge: '⚡', cloud: '☁️', hybrid: '🔁' }[route.value] || '⚡'))
const perf = computed(() => getPerf(detail.value || {}))

// 云端研判
const cloudInference = computed(() => getCloudInference(detail.value))
const cloudTone = computed(() => cloudJudgmentMeta(cloudInference.value?.judgment).tone)
const cloudJudgeLabel = computed(() => cloudJudgmentMeta(cloudInference.value?.judgment).label)
const cloudStatusLabel = computed(() =>
  cloudInference.value?.status === 'completed' ? '已完成' : '已回退边缘')
const cloudConfPct = computed(() => {
  const c = cloudInference.value?.confidence
  return c != null ? `${(c * 100).toFixed(0)}%` : '—'
})
const confPct = computed(() => {
  const c = detail.value?.confidence
  return c != null ? `${(c * 100).toFixed(0)}%` : '—'
})
const priorityLabel = computed(() => detail.value?.priority || '—')
const traceId = computed(() => detail.value?.details?.trace_id || detail.value?.trace_id || null)

const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    alert('已复制到剪贴板')
  } catch (e) {
    console.error('复制失败', e)
  }
}

const dispLabel = (a) => ({
  acknowledge: '确认到场', resolve: '确认处置',
  false_positive: '标记误报', escalate: '科室升级',
}[a] || a)

const dispTagType = (a) => ({
  acknowledge: 'warning', resolve: 'success',
  false_positive: 'info', escalate: 'danger',
}[a] || 'info')
</script>

<style scoped>
.detail-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  justify-content: flex-end;
  z-index: 2100;
}
.detail-panel {
  width: 440px;
  max-width: 92vw;
  height: 100%;
  background: #fff;
  box-shadow: -12px 0 40px rgba(15, 23, 42, 0.18);
  display: flex;
  flex-direction: column;
  animation: slide-in 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes slide-in {
  from { transform: translateX(60px); opacity: 0.4; }
  to { transform: translateX(0); opacity: 1; }
}
.detail-head {
  padding: 16px;
  border-bottom: 1px solid #e5e6eb;
  background: #f0f5ff;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.detail-title h2 { font-size: 15px; margin: 0; color: #1677ff; }
.detail-sub { font-size: 10px; color: #86909c; font-family: monospace; }
.detail-close { background: none; border: none; font-size: 24px; color: #86909c; cursor: pointer; line-height: 1; }
.detail-body { flex: 1; overflow-y: auto; padding: 14px 16px; display: flex; flex-direction: column; gap: 12px; }
.detail-loading { text-align: center; padding: 40px 0; color: #86909c; font-size: 12px; }

.route-summary {
  border-radius: 8px;
  padding: 12px;
  border: 1px solid;
}
.route-edge { background: #e8f8e8; border-color: #b7eb8f; }
.route-cloud { background: #e6f7ff; border-color: #91caff; }
.route-hybrid { background: #fff7e6; border-color: #ffd9a8; }
.route-badge { display: flex; align-items: center; gap: 10px; }
.route-icon { font-size: 22px; }
.route-label { font-size: 13px; font-weight: 700; color: #1d2129; }
.route-meta { font-size: 11px; color: #4e5969; margin-top: 2px; }

.trace-block {
  background: #fafafa;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.trace-row { display: flex; align-items: center; gap: 8px; font-size: 11px; }
.trace-label { color: #86909c; width: 64px; flex-shrink: 0; font-weight: 600; }
.trace-code {
  font-family: monospace;
  background: #f0f5ff;
  color: #1677ff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.trace-copy {
  background: #fff;
  border: 1px solid #d6e4ff;
  color: #1677ff;
  font-size: 10px;
  padding: 1px 8px;
  border-radius: 4px;
  cursor: pointer;
}
.trace-copy:hover { background: #f0f5ff; }

.perf-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.perf-item {
  background: #f5f9ff;
  border: 1px solid #d6e4ff;
  border-radius: 8px;
  padding: 10px;
  text-align: center;
}
.perf-label { font-size: 10px; color: #86909c; }
.perf-value { font-size: 15px; font-weight: 800; color: #1677ff; font-family: 'Outfit', sans-serif; margin-top: 2px; }

.model-block {
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 云端二次研判 */
.cloud-block {
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: #fafafa;
}
.cloud-block.tone-danger { border-color: #ffccc7; background: #fff2f0; }
.cloud-block.tone-warning { border-color: #ffd9a8; background: #fff7e6; }
.cloud-block.tone-info { border-color: #d6e4ff; background: #f0f5ff; }
.cloud-head { display: flex; align-items: center; gap: 8px; }
.cloud-judge {
  font-size: 13px; font-weight: 800;
  padding: 2px 10px; border-radius: 4px; color: #fff;
}
.cloud-block.tone-danger .cloud-judge { background: #f5222d; }
.cloud-block.tone-warning .cloud-judge { background: #fa8c16; }
.cloud-block.tone-info .cloud-judge { background: #1677ff; }
.cloud-status { font-size: 10px; color: #86909c; }
.cloud-advice {
  font-size: 12px; color: #1d2129; line-height: 1.6;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 6px; padding: 8px 10px;
}
.cloud-meta { display: flex; flex-wrap: wrap; gap: 12px; font-size: 11px; color: #4e5969; }
.cloud-meta-item b { color: #1d2129; }
.cloud-meta-item.trace code {
  font-family: monospace; font-size: 10px; color: #1677ff;
  background: #f0f5ff; padding: 1px 6px; border-radius: 4px;
}
.model-line { display: flex; gap: 8px; font-size: 11px; }
.model-key { color: #86909c; width: 64px; flex-shrink: 0; font-weight: 600; }
.model-val { color: #1d2129; font-weight: 600; }

.timeline {
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tl-row { display: flex; gap: 8px; font-size: 11px; }
.tl-key { color: #86909c; width: 64px; flex-shrink: 0; font-weight: 600; }
.tl-val { color: #1d2129; }

.detail-section { display: flex; flex-direction: column; gap: 8px; }
.section-title { font-size: 12px; font-weight: 700; color: #4e5969; border-left: 3px solid #1677ff; padding-left: 8px; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; }
.meta-tag {
  background: #f0f5ff; color: #1677ff; font-size: 10px; font-weight: 600;
  padding: 2px 8px; border-radius: 4px; border: 1px solid #d6e4ff;
}
.evidence-code {
  font-family: monospace; font-size: 10px; color: #4e5969;
  background: #fafafa; border: 1px solid #e5e6eb; padding: 8px;
  border-radius: 6px; overflow-x: auto;
}
.details-pre {
  font-family: monospace; font-size: 10px; color: #4e5969;
  background: #fafafa; border: 1px solid #e5e6eb; padding: 8px;
  border-radius: 6px; overflow-x: auto; white-space: pre-wrap; word-break: break-all;
}
.disp-row { display: flex; align-items: center; gap: 8px; font-size: 11px; }
.disp-op { color: #1d2129; font-weight: 600; }
.disp-time { color: #86909c; margin-left: auto; }
</style>
