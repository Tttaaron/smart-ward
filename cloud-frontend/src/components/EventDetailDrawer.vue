<template>
  <div v-if="visible" class="detail-overlay" @click.self="$emit('close')">
    <div class="detail-panel" role="dialog" aria-modal="true" aria-labelledby="event-detail-title">
      <div class="detail-head">
        <div class="detail-title">
          <div class="detail-title-row">
            <span class="detail-mark" aria-hidden="true">TRACE</span>
            <h2 id="event-detail-title">事件详情与链路追踪</h2>
          </div>
          <span class="detail-sub">{{ eventId }}</span>
        </div>
        <button class="detail-close" aria-label="关闭事件详情" @click="$emit('close')">&times;</button>
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
  fallbackEvent: { type: Object, default: null },
})

const emit = defineEmits(['close'])

const loading = ref(false)
const detail = ref(null)

const load = async () => {
  if (!props.eventId) return

  const fallback = props.fallbackEvent?.event_id === props.eventId ? props.fallbackEvent : null
  // 演示事件没有后端持久化记录，直接用队列中的完整对象渲染详情，保证答辩链路可演示。
  if (fallback && String(props.eventId).startsWith('demo-')) {
    detail.value = fallback
    loading.value = false
    return
  }

  loading.value = true
  try {
    const res = await api.getEvent(props.eventId)
    detail.value = res.data?.data || fallback
  } catch (e) {
    console.error('加载事件详情失败', e)
    detail.value = fallback
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
const routeIcon = computed(() => ({ edge: 'EDGE', cloud: 'CLOUD', hybrid: 'HYBRID' }[route.value] || 'EDGE'))
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
  background: rgba(23, 43, 46, 0.52);
  backdrop-filter: blur(3px);
  display: flex;
  justify-content: flex-end;
  z-index: 2100;
}
.detail-panel {
  width: 460px;
  max-width: 94vw;
  height: 100%;
  background: #fffdfa;
  border-left: 1px solid #d9d3ca;
  box-shadow: -16px 0 54px rgba(23, 43, 46, 0.2), inset 1px 0 0 rgba(255, 255, 255, 0.76);
  display: flex;
  flex-direction: column;
  animation: slide-in 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes slide-in {
  from { transform: translateX(60px); opacity: 0.4; }
  to { transform: translateX(0); opacity: 1; }
}
.detail-head {
  padding: 16px 18px;
  border-bottom: 1px solid #e1dbd2;
  background: #f6f3ee;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
}
.detail-title { min-width: 0; }
.detail-title-row { display: flex; align-items: center; gap: 8px; }
.detail-mark {
  display: inline-grid;
  place-items: center;
  width: 35px;
  height: 21px;
  color: #147976;
  background: #e3f0ee;
  border: 1px solid #b9d9d5;
  border-radius: 5px;
  font: 800 8px/1 'Outfit', sans-serif;
  letter-spacing: 0.06em;
}
.detail-title h2 { font-size: 15px; margin: 0; color: #1b2a2e; font-weight: 800; }
.detail-sub { display: block; max-width: 340px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 5px; font-size: 10px; color: #8a9796; font-family: monospace; }
.detail-close {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  color: #718083;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 7px;
  font-size: 24px;
  cursor: pointer;
  line-height: 1;
}
.detail-close:hover { color: #1b2a2e; background: #ebe7df; border-color: #d9d3ca; }
.detail-body { flex: 1; overflow-y: auto; padding: 15px 18px 20px; display: flex; flex-direction: column; gap: 13px; }
.detail-loading { text-align: center; padding: 46px 0; color: #718083; font-size: 12px; }

.route-summary {
  border-radius: 9px;
  padding: 12px 13px;
  border: 1px solid;
}
.route-edge { background: #e3f0ee; border-color: #b9d9d5; }
.route-cloud { background: #eef2ed; border-color: #d3ddd4; }
.route-hybrid { background: #fbefd9; border-color: #e8c88f; }
.route-badge { display: flex; align-items: center; gap: 10px; }
.route-icon {
  display: inline-grid;
  place-items: center;
  width: 46px;
  height: 26px;
  flex: 0 0 auto;
  color: #147976;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(20, 121, 118, 0.28);
  border-radius: 6px;
  font: 800 8px/1 'Outfit', sans-serif;
  letter-spacing: 0.06em;
}
.route-hybrid .route-icon { color: #a96b2b; border-color: rgba(169, 107, 43, 0.28); }
.route-cloud .route-icon { color: #536367; border-color: rgba(83, 99, 103, 0.24); }
.route-label { font-size: 13px; font-weight: 750; color: #1b2a2e; }
.route-meta { font-size: 11px; color: #536367; margin-top: 3px; }

.trace-block {
  background: #fbfaf7;
  border: 1px solid #e1dbd2;
  border-radius: 9px;
  padding: 11px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.trace-row { display: flex; align-items: center; gap: 8px; font-size: 11px; }
.trace-label { color: #718083; width: 64px; flex-shrink: 0; font-weight: 700; }
.trace-code {
  font-family: monospace;
  background: #eef4f1;
  color: #147976;
  padding: 2px 6px;
  border: 1px solid #d1e3df;
  border-radius: 5px;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.trace-copy {
  background: #fffdfa;
  border: 1px solid #b9d9d5;
  color: #147976;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 5px;
  cursor: pointer;
}
.trace-copy:hover { background: #e3f0ee; }

.perf-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.perf-item {
  background: #f6f3ee;
  border: 1px solid #e1dbd2;
  border-radius: 8px;
  padding: 10px;
  text-align: center;
}
.perf-label { font-size: 10px; color: #718083; }
.perf-value { font-size: 15px; font-weight: 800; color: #147976; font-family: 'Outfit', sans-serif; margin-top: 2px; }

.model-block {
  background: #fffdfa;
  border: 1px solid #e1dbd2;
  border-radius: 9px;
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
.model-key { color: #718083; width: 64px; flex-shrink: 0; font-weight: 700; }
.model-val { min-width: 0; overflow-wrap: anywhere; color: #1b2a2e; font-weight: 650; }

.timeline {
  background: #fbfaf7;
  border: 1px solid #e1dbd2;
  border-radius: 9px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tl-row { display: flex; gap: 8px; font-size: 11px; }
.tl-key { color: #718083; width: 64px; flex-shrink: 0; font-weight: 700; }
.tl-val { color: #1b2a2e; }

.detail-section { display: flex; flex-direction: column; gap: 8px; }
.section-title { font-size: 12px; font-weight: 800; color: #536367; border-left: 3px solid #147976; padding-left: 8px; }
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; }
.meta-tag {
  background: #e3f0ee; color: #147976; font-size: 10px; font-weight: 700;
  padding: 2px 8px; border-radius: 5px; border: 1px solid #b9d9d5;
}
.evidence-code {
  font-family: monospace; font-size: 10px; color: #536367;
  background: #fbfaf7; border: 1px solid #e1dbd2; padding: 8px;
  border-radius: 6px; overflow-x: auto;
}
.details-pre {
  font-family: monospace; font-size: 10px; color: #536367;
  background: #fbfaf7; border: 1px solid #e1dbd2; padding: 8px;
  border-radius: 6px; overflow-x: auto; white-space: pre-wrap; word-break: break-all;
}
.disp-row { display: flex; align-items: center; gap: 8px; font-size: 11px; }
.disp-op { color: #1b2a2e; font-weight: 650; }
.disp-time { color: #718083; margin-left: auto; }

.detail-panel :deep(.el-tag) { border-radius: 5px; font-weight: 700; }
.detail-panel :deep(.el-tag--success) { --el-tag-bg-color: #e3f0ee; --el-tag-border-color: #b9d9d5; --el-tag-text-color: #147976; }
.detail-panel :deep(.el-tag--warning) { --el-tag-bg-color: #fbefd9; --el-tag-border-color: #e8c88f; --el-tag-text-color: #a96b2b; }
.detail-panel :deep(.el-tag--danger) { --el-tag-bg-color: #f9e6e2; --el-tag-border-color: #e8b3aa; --el-tag-text-color: #b5574d; }
.detail-panel :deep(.el-tag--info) { --el-tag-bg-color: #eeeae3; --el-tag-border-color: #d2cbc1; --el-tag-text-color: #536367; }

@media (max-width: 520px) {
  .detail-panel { max-width: 100vw; width: 100%; }
  .detail-head { padding: 14px; }
  .detail-body { padding: 13px 14px 18px; }
  .detail-sub { max-width: 250px; }
  .trace-row { flex-wrap: wrap; gap: 5px 8px; }
  .trace-code { min-width: 0; }
  .trace-row .trace-copy { margin-left: 72px; }
  .disp-row { flex-wrap: wrap; }
  .disp-time { width: 100%; margin-left: 0; }
}
</style>
