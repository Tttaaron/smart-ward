<template>
  <div class="scene-injector" :class="{ open: isOpen }">
    <!-- 触发按钮 -->
    <button
      class="injector-toggle"
      :title="isOpen ? '收起演示工具' : '打开演示工具'"
      :aria-label="isOpen ? '收起演示工具' : '打开演示工具'"
      @click="isOpen = !isOpen"
    >
      <el-icon class="icon" :size="16" aria-hidden="true"><component :is="isOpen ? 'ArrowRight' : 'Lightning'" /></el-icon>
      <span class="label" v-if="!isOpen">演示工具</span>
    </button>

    <!-- 注入面板 -->
    <div class="injector-panel">
      <div class="panel-header">
        <h3>调试模拟注入台</h3>
        <button class="btn-close" title="关闭演示工具" aria-label="关闭演示工具" @click="isOpen = false">
          <el-icon :size="16"><Close /></el-icon>
        </button>
      </div>

      <div class="panel-body">
        <div class="form-group">
          <label>目标床位</label>
          <el-select v-model="selectedBed" size="small" class="field-wide">
            <el-option value="B01" label="1床 (B01)" />
            <el-option value="B02" label="2床 (B02)" />
            <el-option value="B03" label="3床 (B03)" />
          </el-select>
        </div>

        <div class="form-group">
          <label>推理链路（edge / cloud / hybrid）</label>
          <div class="route-options">
            <button
              v-for="r in routeOptions"
              :key="r.key"
              class="route-option"
              :class="['route-opt-' + r.key, { active: selectedRoute === r.key }]"
              @click="selectedRoute = r.key"
            >
              <el-icon class="ro-icon" :size="15" aria-hidden="true"><component :is="r.icon" /></el-icon>
              <span class="ro-label">{{ r.label }}</span>
            </button>
          </div>
          <div class="route-hint">{{ routeHint }}</div>
        </div>

        <div class="form-group">
          <label>模拟网络状态（断网/降级/在线）</label>
          <div class="net-options">
            <button
              v-for="n in netOptions"
              :key="n.key"
              class="net-option"
              :class="['net-opt-' + n.key, { active: selectedNet === n.key }]"
              @click="selectedNet = n.key"
            >
              {{ n.label }}
            </button>
          </div>
          <div class="route-hint">{{ netHint }}</div>
        </div>

        <div class="form-group">
          <label class="switch-label">
            <el-switch v-model="simulateTimeout" size="small" />
            <span>模拟云端超时 → 边缘回退（timeout）</span>
          </label>
        </div>

        <div class="form-group">
          <div class="slider-label-row">
            <label>置信度</label>
            <span class="conf-val font-num">{{ (confidence * 100).toFixed(0) }}%</span>
          </div>
          <el-slider
            v-model="confidence"
            :min="0.5"
            :max="1.0"
            :step="0.05"
            :show-tooltip="false"
          />
        </div>

        <div class="form-group">
          <label>活动日志注入（observation.activity）</label>
          <div class="activity-inject-row">
            <el-select v-model="activityLabel" size="small" class="field-flex">
              <el-option value="sitting" label="坐姿 sitting" />
              <el-option value="standing" label="站立 standing" />
              <el-option value="lying" label="卧躺 lying" />
              <el-option value="walking" label="行走 walking" />
              <el-option value="sleeping" label="睡眠 sleeping" />
            </el-select>
            <el-button
              size="small"
              type="primary"
              plain
              :disabled="injecting"
              @click="injectActivity"
            >注入活动</el-button>
          </div>
          <div class="route-hint">模拟摄像头活动状态切换，驱动活动日志面板</div>
        </div>

        <div class="event-categories">
          <div class="category">
            <h4 class="p1">P1 紧急告警</h4>
            <div class="btn-grid">
              <el-button
                v-for="evt in p1Events"
                :key="evt.type"
                size="small"
                type="danger"
                plain
                :disabled="injecting"
                @click="triggerEvent(evt.type)"
              >{{ evt.name }}</el-button>
            </div>
          </div>

          <div class="category">
            <h4 class="p2">P2 高级告警</h4>
            <div class="btn-grid">
              <el-button
                v-for="evt in p2Events"
                :key="evt.type"
                size="small"
                type="warning"
                plain
                :disabled="injecting"
                @click="triggerEvent(evt.type)"
              >{{ evt.name }}</el-button>
            </div>
          </div>

          <div class="category">
            <h4 class="p3">P3 常规提示</h4>
            <div class="btn-grid">
              <el-button
                v-for="evt in p3Events"
                :key="evt.type"
                size="small"
                type="primary"
                plain
                :disabled="injecting"
                @click="triggerEvent(evt.type)"
              >{{ evt.name }}</el-button>
            </div>
          </div>
        </div>

        <div class="toast-message" :class="toastType" v-if="toastMsg">
          <span class="toast-indicator" aria-hidden="true"></span>
          <span>{{ toastMsg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import api from '../api/index.js'

const isOpen = ref(false)
const injecting = ref(false)
const selectedBed = ref('B01')
const confidence = ref(0.9)
const selectedRoute = ref('edge')
const selectedNet = ref('online')
const simulateTimeout = ref(false)
const activityLabel = ref('sitting')
// 每床最近一次注入的活动（用于构造 previous，形成切换链）
const lastActivityByBed = {}
const toastMsg = ref('')
const toastType = ref('')

const routeOptions = [
  { key: 'edge', label: '边缘', icon: 'Lightning' },
  { key: 'cloud', label: '云端', icon: 'Cloudy' },
  { key: 'hybrid', label: '协同', icon: 'Connection' },
]

const netOptions = [
  { key: 'online', label: '在线' },
  { key: 'degraded', label: '降级' },
  { key: 'offline', label: '断网' },
]

// 云端模型配置（模拟云端 14B 接入）
const CLOUD_MODEL = { model_name: 'qwen2.5-14b-instruct', model_version: '1.0.0-vllm' }
// 边缘模型配置
const EDGE_MODEL = { model_name: 'qwen2.5-1.5b-instruct', model_version: '1.0.0-q4' }

const routeHint = computed(() => ({
  edge: '纯边缘：本地 LLM 即时研判，低延迟',
  cloud: '纯云端：请求云端 14B 大模型研判',
  hybrid: '云边协同：边缘初判 + 云端复核',
}[selectedRoute.value]))

const netHint = computed(() => ({
  online: '网络正常，事件实时上报云端',
  degraded: '网络降级：边缘本地处理，缓存待补传',
  offline: '断网：完全边缘值守，缓存事件待恢复补传',
}[selectedNet.value]))

const p1Events = [
  { type: 'fall_suspected', name: '疑似跌倒' },
  { type: 'nurse_call', name: '护士呼叫' },
  { type: 'fall_prediction', name: '坠床预警' },
  { type: 'seizure', name: '抽搐检测' },
]

const p2Events = [
  { type: 'bed_leave', name: '患者离床' },
  { type: 'door_departure', name: '门区离开' },
  { type: 'night_wandering', name: '夜间徘徊' },
  { type: 'long_still', name: '长时间静止' },
  { type: 'abnormal_posture', name: '异常体态' },
]

const p3Events = [
  { type: 'environment_anomaly', name: '环境异常' },
  { type: 'node_offline', name: '节点失联' },
  { type: 'bedsore_risk', name: '压疮预防' },
  { type: 'device_fault', name: '设备故障' },
]

const showToast = (msg, type = 'success') => {
  toastMsg.value = msg
  toastType.value = type
  setTimeout(() => {
    toastMsg.value = ''
  }, 2500)
}

// 生成链路追踪标识（用于截图标注与跨模块回查）
const genTraceId = () => {
  try {
    return crypto.randomUUID()
  } catch (e) {
    return `trace-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  }
}

// 依据所选链路构造 details 中的性能指标与模型
const buildDetails = (eventType) => {
  const isCloud = selectedRoute.value === 'cloud'
  const isHybrid = selectedRoute.value === 'hybrid'
  const model = isCloud ? CLOUD_MODEL : EDGE_MODEL
  const base = {
    route: selectedRoute.value,
    network: selectedNet.value,
    trace_id: genTraceId(),
    route_source: isCloud ? 'TaskRouter: cloud' : isHybrid ? 'TaskRouter: hybrid' : 'TaskRouter: edge',
    // 边缘模型推理耗时（模拟）
    inference_ms: isCloud ? 12 : Math.round(180 + Math.random() * 120),
    // 边缘 TTFT（首token，目标 <200ms）
    ttft_ms: isCloud ? 8 : Math.round(90 + Math.random() * 80),
    // 云端往返延迟（仅 cloud/hybrid 有）
    cloud_latency_ms: isCloud || isHybrid ? Math.round(380 + Math.random() * 220) : null,
    // 峰值内存 RSS（MB）
    memory_mb: isCloud ? 640 : Math.round(880 + Math.random() * 160),
  }
  // 云端超时回退模拟
  if (simulateTimeout.value) {
    base.state_fallback = 'timeout'
    base.cloud_latency_ms = 60000 // 超时标记
    base.fallback_note = '云端 60s 未响应，已按边缘决策回退'
  }
  // 断网模拟：网络 offline -> 事件走离线缓存
  if (selectedNet.value === 'offline') {
    base.state_fallback = 'cloud_unavailable'
    base.fallback_note = '网络中断，边缘本地值守，事件缓存待补传'
  }
  return { model, details: base }
}

const triggerEvent = async (eventType) => {
  injecting.value = true
  try {
    const { model, details } = buildDetails(eventType)
    const res = await api.injectEvent({
      ward_id: 'W-01',
      bed_id: selectedBed.value,
      node_id: `EDGE-W01-${selectedBed.value}`,
      event_type: eventType,
      confidence: confidence.value,
      model,
      details,
    })
    if (res.data.code === 0) {
      const routeCn = { edge: '边缘', cloud: '云端', hybrid: '协同' }[selectedRoute.value]
      const suffix = simulateTimeout.value ? ' · 模拟云端超时' : selectedNet.value !== 'online' ? ` · 模拟${selectedNet.value}` : ''
      showToast(`[${routeCn}链路] 事件注入成功${suffix}`, 'success')
    } else {
      showToast('注入失败: ' + res.data.message, 'error')
    }
  } catch (e) {
    console.error(e)
    showToast('网络错误，注入失败', 'error')
  } finally {
    injecting.value = false
  }
}

// 注入活动状态观测（observation.activity），驱动活动日志面板
const injectActivity = async () => {
  injecting.value = true
  try {
    const bed = selectedBed.value
    const label = activityLabel.value
    const since = Date.now() / 1000
    const previous = lastActivityByBed[bed] || null
    const res = await api.injectObservation({
      ward_id: 'W-01',
      node_id: `EDGE-W01-${bed}`,
      bed_id: bed,
      sources: [{
        source_type: 'camera',
        data: {
          presence: true,
          person_count: 1,
          posture: label === 'walking' ? 'walking' : label === 'lying' ? 'lying' : label === 'standing' ? 'standing' : 'sitting',
          fall_score: 0.0,
          activity: {
            label,
            since: Math.round(since * 100) / 100,
            switched: previous !== label,
            previous,
          },
        },
        quality: { confidence: 0.95, latency_ms: 45, degraded: false },
      }],
    })
    if (res.data.code === 0) {
      lastActivityByBed[bed] = label
      showToast(`[${bed}] 活动注入成功: ${label}`, 'success')
    } else {
      showToast('活动注入失败: ' + res.data.message, 'error')
    }
  } catch (e) {
    console.error(e)
    showToast('网络错误，活动注入失败', 'error')
  } finally {
    injecting.value = false
  }
}
</script>

<style scoped>
.scene-injector {
  position: fixed;
  right: -310px;
  bottom: 46px;
  width: 310px;
  height: min(720px, calc(100vh - 100px));
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-left: 1px solid var(--line-strong);
  box-shadow: -12px 0 38px rgba(24, 48, 76, 0.18);
  transition: right 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  z-index: 60;
  display: flex;
  flex-direction: column;
  border-top-left-radius: 13px;
  border-bottom-left-radius: 13px;
}
.scene-injector.open { right: 0; }

.injector-toggle {
  position: absolute;
  left: -42px;
  top: 50%;
  transform: translateY(-50%);
  width: 42px;
  padding: 14px 6px;
  background: linear-gradient(135deg, #5B9BFF 0%, #1E63C7 100%);
  color: #FFFFFF;
  border: none;
  border-top-left-radius: 10px;
  border-bottom-left-radius: 10px;
  cursor: pointer;
  box-shadow: -4px 0 14px rgba(42, 125, 225, 0.32);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  transition: all 0.2s ease;
}
.injector-toggle:hover { filter: brightness(1.06); }
.injector-toggle:focus-visible { outline: 2px solid rgba(42, 125, 225, 0.6); outline-offset: 2px; }
.scene-injector:not(.open) .injector-toggle {
  top: auto;
  bottom: 104px;
  transform: none;
}
.injector-toggle .icon { font-size: 15px; font-weight: 800; }
.injector-toggle .label {
  font-size: 11px;
  writing-mode: vertical-rl;
  letter-spacing: 3px;
  font-weight: 700;
}

.injector-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  padding: 14px;
  border-bottom: 1px solid var(--line);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--surface-3);
  border-top-left-radius: 13px;
}
.panel-header h3 {
  font-size: 14px;
  color: var(--primary);
  margin: 0;
  font-weight: 700;
}
.btn-close {
  background: transparent;
  border: none;
  color: var(--text-3);
  font-size: 16px;
  cursor: pointer;
  line-height: 1;
  transition: color 0.15s ease;
}
.btn-close :deep(.el-icon) { vertical-align: middle; }
.btn-close:hover { color: var(--text); }

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
}

.form-group {
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.form-group label {
  font-size: 11px;
  color: var(--text-2);
  font-weight: 600;
}
.field-wide { width: 100%; }
.field-flex { flex: 1; min-width: 0; }
.switch-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}
.slider-label-row {
  display: flex;
  justify-content: space-between;
}
.conf-val {
  font-size: 11px;
  color: var(--primary);
  font-weight: 700;
}

/* 链路选择 */
.route-options {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 6px;
}
.route-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 8px 4px;
  border-radius: 8px;
  border: 1px solid var(--line-strong);
  background: var(--surface-2);
  cursor: pointer;
  transition: all 0.2s;
}
.route-option.active { border-width: 1px; }
.route-option.route-opt-edge.active {
  border-color: var(--success);
  background: var(--success-soft);
  box-shadow: 0 0 10px rgba(52, 211, 153, 0.15);
}
.route-option.route-opt-cloud.active {
  border-color: var(--accent);
  background: var(--accent-soft);
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.15);
}
.route-option.route-opt-hybrid.active {
  border-color: var(--warning);
  background: var(--warning-soft);
  box-shadow: 0 0 10px rgba(251, 191, 36, 0.15);
}
.ro-icon { font-size: 15px; color: var(--text-2); }
.ro-label { font-size: 11px; font-weight: 700; color: var(--text-2); }
.route-option.active .ro-icon,
.route-option.active .ro-label { color: var(--text); }

.activity-inject-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.route-hint {
  font-size: 10px;
  color: var(--text-3);
  background: var(--surface-3);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 5px 8px;
  line-height: 1.5;
}

/* 网络选择 */
.net-options {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 6px;
}
.net-option {
  padding: 7px 4px;
  border-radius: 8px;
  border: 1px solid var(--line-strong);
  background: var(--surface-2);
  font-size: 11px;
  font-weight: 700;
  color: var(--text-2);
  cursor: pointer;
  transition: all 0.2s;
}
.net-option.net-opt-online.active {
  border-color: var(--success);
  background: var(--success-soft);
  color: var(--success);
}
.net-option.net-opt-degraded.active {
  border-color: var(--warning);
  background: var(--warning-soft);
  color: var(--warning);
}
.net-option.net-opt-offline.active {
  border-color: var(--danger);
  background: var(--danger-soft);
  color: var(--danger);
}

.event-categories {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 14px;
}
.category h4 {
  font-size: 11px;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--line);
  font-weight: 700;
}
.category h4.p1 { color: var(--danger); }
.category h4.p2 { color: var(--warning); }
.category h4.p3 { color: var(--primary); }

.btn-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.toast-message {
  margin-top: 14px;
  padding: 8px 12px;
  font-size: 11px;
  border-radius: 7px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
.toast-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex: 0 0 auto;
}
.toast-message.success {
  background: var(--success-soft);
  color: var(--success);
  border: 1px solid rgba(52, 211, 153, 0.3);
}
.toast-message.success .toast-indicator {
  background: var(--success);
  box-shadow: 0 0 6px var(--success);
}
.toast-message.error {
  background: var(--danger-soft);
  color: var(--danger);
  border: 1px solid rgba(220, 38, 38, 0.3);
}
.toast-message.error .toast-indicator {
  background: var(--danger);
  box-shadow: 0 0 6px var(--danger);
}

@media (max-width: 720px) {
  .scene-injector { width: min(320px, calc(100vw - 18px)); right: calc(-1 * min(320px, calc(100vw - 18px)) + 8px); bottom: 38px; }
  .scene-injector.open { right: 8px; }
  .injector-toggle { left: -38px; width: 38px; }
}
@media (max-width: 1450px) {
  .scene-injector:not(.open) .injector-toggle { width: 42px; height: 42px; padding: 0; }
  .scene-injector:not(.open) .injector-toggle .label { display: none; }
}
</style>
