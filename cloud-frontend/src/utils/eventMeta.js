/**
 * 事件元信息工具（护士站可观测性）
 *
 * 集中处理：
 * - 推理链路 route 判定（edge / cloud / hybrid）
 * - 处置状态中文映射（含 timeout / fallback 降级状态）
 * - 性能指标（TTFT / 云端延迟 / 内存 / 推理耗时）归一化读取
 *
 * route 判定优先级：
 *   1. details.route 显式字段（场景注入 / 云端回传写入）
 *   2. details.cloud_reviewed === true            -> hybrid
 *   3. 模型名或版本含 cloud/14b/vllm 等云端标识   -> cloud
 *   4. 默认                              -> edge
 */

// ---- 推理链路 ----
export const ROUTES = {
  edge: { label: '边缘', tag: 'success', desc: '本地 LLM 即时研判' },
  cloud: { label: '云端', tag: 'primary', desc: '云端大模型研判' },
  hybrid: { label: '协同', tag: 'warning', desc: '边缘初判 + 云端复核' },
}

export function resolveRoute(evt) {
  if (!evt) return 'edge'
  const details = evt.details || {}
  // 1) 显式 route 字段
  if (details.route && ROUTES[details.route]) return details.route
  // 2) hybrid 标记
  if (details.cloud_reviewed === true || details.cloud_reviewed === 'true') return 'hybrid'
  // 3) 云端模型标识
  const name = (evt.model_name || '').toLowerCase()
  const ver = (evt.model_version || '').toLowerCase()
  if (/(cloud|14b|vllm)/.test(`${name} ${ver}`)) return 'cloud'
  // 4) 默认边缘
  return 'edge'
}

export function routeLabel(route) {
  return (ROUTES[route] || ROUTES.edge).label
}

export function routeTagType(route) {
  return (ROUTES[route] || ROUTES.edge).tag
}

export function routeDesc(route) {
  return (ROUTES[route] || ROUTES.edge).desc
}

// ---- 处置状态 ----
export const STATE_MAP = {
  new: { label: '待处置', tag: 'danger' },
  notified: { label: '已通知', tag: 'danger' },
  acknowledged: { label: '确认到场', tag: 'warning' },
  resolved: { label: '已归档', tag: 'success' },
  false_positive: { label: '判定误报', tag: 'info' },
  escalated: { label: '升级上报', tag: 'danger' },
  timeout: { label: '云端超时·边缘回退', tag: 'warning' },
  fallback: { label: '云端不可用·边缘值守', tag: 'warning' },
  offline_buffered: { label: '离线缓存·待补传', tag: 'info' },
}

export function stateLabel(s) {
  return (STATE_MAP[s] || { label: s || '未知' }).label
}

export function stateTagType(s) {
  return (STATE_MAP[s] || { tag: 'info' }).tag
}

/**
 * 判断事件是否处于"超时/降级"状态（用于异常视觉提示）
 * 判定来源：
 *   1. details.state_fallback 标记（超时回退 / 云端不可用）
 *   2. 事件等待时长超过阈值（默认 180s）且仍未处置
 */
export function resolveFallback(evt, nowTs = Date.now()) {
  if (!evt) return null
  const details = evt.details || {}
  if (details.state_fallback === 'timeout') return 'timeout'
  if (details.state_fallback === 'cloud_unavailable') return 'fallback'
  // 等待超时推断
  if (evt.occurred_at && ['new', 'notified', 'acknowledged'].includes(evt.state)) {
    const waitSec = Math.floor((nowTs - new Date(evt.occurred_at).getTime()) / 1000)
    if (waitSec > 180) return 'timeout'
  }
  return null
}

// ---- 性能指标归一化读取（从 details 或事件顶层读取） ----
export function getPerf(evt) {
  if (!evt) return {}
  const d = evt.details || {}
  return {
    ttft_ms: d.ttft_ms ?? evt.ttft_ms ?? null,                       // 首 token 时延（边缘 LLM）
    cloud_latency_ms: d.cloud_latency_ms ?? evt.cloud_latency_ms ?? null, // 云端往返延迟
    inference_ms: d.inference_ms ?? evt.inference_ms ?? null,         // 融合推理耗时
    memory_mb: d.memory_mb ?? evt.memory_mb ?? null,                  // 峰值 RSS(MB)
    network: d.network ?? evt.network ?? null,                        // online/degraded/offline
    route_source: d.route_source ?? null,                             // route 的原始来源说明
  }
}

// ---- 格式化 ----
export function fmtMs(ms) {
  if (ms == null || Number.isNaN(ms)) return '—'
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`
  return `${Math.round(ms)} ms`
}

export function fmtBytesToMb(bytes) {
  if (bytes == null || Number.isNaN(bytes)) return '—'
  if (bytes > 1024) return `${(bytes / 1024).toFixed(1)} GB`
  return `${Math.round(bytes)} MB`
}

export function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function fmtDateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function fmtDuration(sec) {
  if (sec == null || Number.isNaN(sec)) return '—'
  if (sec < 60) return `${sec} 秒`
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${m} 分 ${s} 秒`
}

// ---- 网络状态 ----
export const NETWORK_MAP = {
  online: { label: '网络在线', tag: 'success' },
  degraded: { label: '网络降级', tag: 'warning' },
  offline: { label: '网络离线', tag: 'danger' },
}

export function networkMeta(network) {
  return NETWORK_MAP[network] || { label: '网络未知', tag: 'info' }
}
