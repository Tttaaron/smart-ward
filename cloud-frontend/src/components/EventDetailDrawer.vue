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

          <!-- trace 链路旅程 -->
          <div class="trace-journey">
            <div class="tj-title">链路追踪旅程</div>
            <ul class="tj-list">
              <li
                v-for="(node, idx) in journeyNodes"
                :key="idx"
                class="tj-node"
                :class="{ done: node.done, active: node.active, warn: node.warn }"
                :style="{ animationDelay: node.done ? `${idx * 0.28}s` : '0s' }"
              >
                <span class="tj-dot" aria-hidden="true"></span>
                <div class="tj-body">
                  <div class="tj-head">
                    <span class="tj-name">{{ node.name }}</span>
                    <span v-if="node.ms" class="tj-ms font-num">{{ node.ms }}</span>
                    <span v-if="node.tag" class="tj-tag">{{ node.tag }}</span>
                  </div>
                  <div v-if="node.desc" class="tj-desc">{{ node.desc }}</div>
                </div>
                <span v-if="idx < journeyNodes.length - 1" class="tj-line" :style="{ animationDelay: `${(idx + 1) * 0.28}s` }" aria-hidden="true"></span>
              </li>
            </ul>
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
              <span class="disp-tag" :class="'disp-' + d.action">{{ dispLabel(d.action) }}</span>
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
import { ElMessage } from 'element-plus'
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
  // 演示事件没有后端持久化记录，直接用队列中的完整对象渲染详情
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

// trace 链路旅程节点：采集 -> 边缘识别 -> 边缘LLM -> 云端研判 -> 护士站告警
const journeyNodes = computed(() => {
  const d = detail.value
  if (!d) return []
  const p = perf.value
  const ci = cloudInference.value
  const fb = d.details?.state_fallback
  const r = route.value
  const fmt = (ms) => (ms != null ? `${Math.round(ms)} ms` : null)
  const cloudInvolved = r === 'cloud' || r === 'hybrid' || !!ci
  const cloudTimedOut = fb === 'timeout' || fb === 'cloud_unavailable'
  return [
    { name: '采集与融合', desc: '摄像头 / 床垫 / 环境三源', ms: fmt(p.inference_ms), done: true, active: false, warn: false },
    { name: '边缘识别', desc: '规则引擎 + YOLO/姿态', ms: null, done: true, active: false, warn: false },
    { name: '边缘 LLM 增强', desc: p.ttft_ms != null ? `首 token ${Math.round(p.ttft_ms)} ms` : '本地语义增强', ms: null, done: r !== 'cloud', active: false, warn: false },
    { name: '云端 14B 二次研判', desc: cloudTimedOut ? '云端超时，边缘判定生效' : (ci ? ci.judgment || '已完成' : '未参与'), ms: cloudInvolved && !cloudTimedOut ? fmt(p.cloud_latency_ms) : null, tag: cloudTimedOut ? '超时回退' : null, done: cloudInvolved && !cloudTimedOut, active: false, warn: cloudTimedOut },
    { name: '护士站告警', desc: '已到达护士工作站', ms: null, done: true, active: true, warn: false },
  ]
})

const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch (e) {
    console.error('复制失败', e)
    ElMessage.error('复制失败')
  }
}

const dispLabel = (a) => ({
  acknowledge: '确认到场', resolve: '确认处置',
  false_positive: '标记误报', escalate: '科室升级',
}[a] || a)
</script>

<style scoped>
.detail-overlay {
  position: fixed;
  inset: 0;
  background: rgba(24, 48, 76, 0.35);
  backdrop-filter: blur(3px);
  display: flex;
  justify-content: flex-end;
  z-index: 2100;
}
.detail-panel {
  width: 460px;
  max-width: 94vw;
  height: 100%;
  background: var(--surface-2);
  border-left: 1px solid var(--line-strong);
  box-shadow: -18px 0 60px rgba(24, 48, 76, 0.22), inset 1px 0 0 rgba(255, 255, 255, 0.9);
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
  border-bottom: 1px solid var(--line);
  background: var(--surface-3);
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
  min-width: 44px;
  height: 21px;
  padding: 0 5px;
  color: var(--primary);
  background: var(--primary-soft);
  border: 1px solid rgba(42, 125, 225, 0.35);
  border-radius: 5px;
  font: 800 8px/1 'Outfit', sans-serif;
  letter-spacing: 0.08em;
}
.detail-title h2 { font-size: 15px; margin: 0; color: var(--text); font-weight: 800; }
.detail-sub {
  display: block;
  max-width: 340px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 5px;
  font-size: 10px;
  color: var(--text-3);
  font-family: monospace;
}
.detail-close {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  color: var(--text-3);
  background: transparent;
  border: 1px solid transparent;
  border-radius: 7px;
  font-size: 22px;
  cursor: pointer;
  line-height: 1;
  transition: all 0.15s ease;
}
.detail-close:hover { color: var(--text); background: var(--surface-4); border-color: var(--line-strong); }
.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 15px 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 13px;
}
.detail-loading { text-align: center; padding: 46px 0; color: var(--text-3); font-size: 12px; }

.route-summary {
  border-radius: 10px;
  padding: 12px 13px;
  border: 1px solid;
}
.route-edge { background: var(--success-soft); border-color: rgba(52, 211, 153, 0.3); }
.route-cloud { background: var(--accent-soft); border-color: rgba(56, 189, 248, 0.3); }
.route-hybrid { background: var(--warning-soft); border-color: rgba(251, 191, 36, 0.3); }
.route-badge { display: flex; align-items: center; gap: 10px; }
.route-icon {
  display: inline-grid;
  place-items: center;
  min-width: 52px;
  height: 26px;
  flex: 0 0 auto;
  color: var(--success);
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(22, 163, 74, 0.3);
  border-radius: 6px;
  font: 800 8px/1 'Outfit', sans-serif;
  letter-spacing: 0.08em;
}
.route-hybrid .route-icon { color: var(--warning); border-color: rgba(217, 119, 6, 0.3); }
.route-cloud .route-icon { color: var(--accent); border-color: rgba(14, 165, 233, 0.3); }
.route-label { font-size: 13px; font-weight: 750; color: var(--text); }
.route-meta { font-size: 11px; color: var(--text-2); margin-top: 3px; }

/* trace 链路旅程 */
.trace-journey {
  background: var(--surface-3);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 12px 13px 10px;
}
.tj-title {
  font-size: 12px;
  font-weight: 800;
  color: var(--text-2);
  border-left: 3px solid var(--primary);
  padding-left: 8px;
  margin-bottom: 10px;
}
.tj-list { list-style: none; display: flex; flex-direction: column; gap: 0; }
.tj-node {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding-bottom: 14px;
}
.tj-node:last-child { padding-bottom: 0; }
.tj-dot {
  flex: 0 0 auto;
  width: 11px;
  height: 11px;
  margin-top: 2px;
  border-radius: 50%;
  background: var(--surface-4);
  border: 2px solid var(--line-strong);
  z-index: 1;
}
.tj-node.done .tj-dot { background: var(--success); border-color: var(--success); animation: trace-node-light 0.4s ease both; }
.tj-node.active .tj-dot { background: var(--primary); border-color: var(--primary); animation: trace-pulse-active 1.8s ease-in-out infinite; }
.tj-node.warn .tj-dot { background: var(--warning); border-color: var(--warning); }
.tj-line {
  position: absolute;
  left: 5px;
  top: 14px;
  width: 2px;
  height: calc(100% - 10px);
  background: var(--line-strong);
  border-radius: 2px;
  z-index: 0;
}
.tj-node.done .tj-line { background: var(--success); opacity: 0.4; animation: trace-line-grow 0.4s ease both; }
.tj-body { flex: 1; min-width: 0; }
.tj-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tj-name { font-size: 12px; font-weight: 700; color: var(--text); }
.tj-node.active .tj-name { color: var(--primary); }
.tj-node.warn .tj-name { color: var(--warning); }
.tj-ms {
  font-size: 10.5px;
  font-weight: 700;
  color: var(--primary);
  background: var(--primary-soft);
  padding: 1px 6px;
  border-radius: 4px;
}
.tj-tag {
  font-size: 9.5px;
  font-weight: 700;
  color: var(--warning);
  background: var(--warning-soft);
  border: 1px solid rgba(217, 119, 6, 0.4);
  padding: 1px 6px;
  border-radius: 4px;
}
.tj-desc { font-size: 10.5px; color: var(--text-3); margin-top: 2px; }

.trace-block {
  background: var(--surface-3);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 11px 12px;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.trace-row { display: flex; align-items: center; gap: 8px; font-size: 11px; }
.trace-label { color: var(--text-3); width: 64px; flex-shrink: 0; font-weight: 700; }
.trace-code {
  font-family: 'Cascadia Code', Consolas, monospace;
  background: var(--bg-deep);
  color: var(--primary);
  padding: 3px 7px;
  border: 1px solid rgba(42, 125, 225, 0.22);
  border-radius: 5px;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.trace-copy {
  background: transparent;
  border: 1px solid rgba(42, 125, 225, 0.35);
  color: var(--primary);
  font-size: 10px;
  padding: 3px 9px;
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.trace-copy:hover { background: var(--primary-soft); }

.perf-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.perf-item {
  background: var(--surface-3);
  border: 1px solid var(--line);
  border-radius: 9px;
  padding: 10px;
  text-align: center;
}
.perf-label { font-size: 10px; color: var(--text-3); }
.perf-value {
  font-size: 15px;
  font-weight: 800;
  color: var(--primary);
  font-family: 'Outfit', sans-serif;
  margin-top: 3px;
  text-shadow: 0 0 10px rgba(42, 125, 225, 0.18);
}

.model-block {
  background: var(--surface-3);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* 云端二次研判 */
.cloud-block {
  border: 1px solid var(--line-strong);
  border-radius: 9px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 7px;
  background: var(--surface-3);
}
.cloud-block.tone-danger { border-color: rgba(220, 38, 38, 0.4); background: rgba(220, 38, 38, 0.07); }
.cloud-block.tone-warning { border-color: rgba(251, 191, 36, 0.4); background: rgba(251, 191, 36, 0.06); }
.cloud-block.tone-info { border-color: rgba(56, 189, 248, 0.4); background: rgba(56, 189, 248, 0.06); }
.cloud-head { display: flex; align-items: center; gap: 8px; }
.cloud-judge {
  font-size: 12px;
  font-weight: 800;
  padding: 2px 10px;
  border-radius: 5px;
  color: #fff;
}
.cloud-block.tone-danger .cloud-judge { background: var(--danger-strong); box-shadow: 0 0 8px rgba(220, 38, 38, 0.3); }
.cloud-block.tone-warning .cloud-judge { background: #B45309; }
.cloud-block.tone-info .cloud-judge { background: #0369A1; }
.cloud-status { font-size: 10px; color: var(--text-3); }
.cloud-advice {
  font-size: 12px;
  color: var(--text-2);
  line-height: 1.65;
  background: rgba(24, 48, 76, 0.04);
  border-radius: 6px;
  padding: 8px 10px;
}
.cloud-meta { display: flex; flex-wrap: wrap; gap: 12px; font-size: 11px; color: var(--text-2); }
.cloud-meta-item b { color: var(--text); }
.cloud-meta-item.trace code {
  font-family: monospace;
  font-size: 10px;
  color: var(--accent);
  background: var(--accent-soft);
  padding: 1px 6px;
  border-radius: 4px;
}

.model-line { display: flex; gap: 8px; font-size: 11px; }
.model-key { color: var(--text-3); width: 64px; flex-shrink: 0; font-weight: 700; }
.model-val { min-width: 0; overflow-wrap: anywhere; color: var(--text); font-weight: 650; }

.timeline {
  background: var(--surface-3);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tl-row { display: flex; gap: 8px; font-size: 11px; }
.tl-key { color: var(--text-3); width: 64px; flex-shrink: 0; font-weight: 700; }
.tl-val { color: var(--text); }

.detail-section { display: flex; flex-direction: column; gap: 8px; }
.section-title {
  font-size: 12px;
  font-weight: 800;
  color: var(--text-2);
  border-left: 3px solid var(--primary);
  padding-left: 8px;
}
.tag-list { display: flex; flex-wrap: wrap; gap: 6px; }
.meta-tag {
  background: var(--primary-soft);
  color: var(--primary);
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 5px;
  border: 1px solid rgba(42, 125, 225, 0.3);
}
.evidence-code, .details-pre {
  font-family: 'Cascadia Code', Consolas, monospace;
  font-size: 10px;
  color: var(--text-2);
  background: var(--bg-deep);
  border: 1px solid var(--line);
  padding: 8px 10px;
  border-radius: 7px;
  overflow-x: auto;
}
.details-pre { white-space: pre-wrap; word-break: break-all; }

.disp-row { display: flex; align-items: center; gap: 8px; font-size: 11px; }
.disp-tag {
  padding: 2px 8px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 700;
  border: 1px solid transparent;
}
.disp-acknowledge { color: var(--warning); background: var(--warning-soft); border-color: rgba(251, 191, 36, 0.3); }
.disp-resolve { color: var(--success); background: var(--success-soft); border-color: rgba(52, 211, 153, 0.3); }
.disp-false_positive { color: var(--info); background: var(--info-soft); border-color: rgba(140, 163, 181, 0.3); }
.disp-escalate { color: var(--danger); background: var(--danger-soft); border-color: rgba(220, 38, 38, 0.3); }
.disp-op { color: var(--text); font-weight: 650; }
.disp-time { color: var(--text-3); margin-left: auto; }

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
