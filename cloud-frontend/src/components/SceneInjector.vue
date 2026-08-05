<template>
  <div class="scene-injector" :class="{ open: isOpen }">
    <!-- 触发按钮 -->
    <button class="injector-toggle" @click="isOpen = !isOpen">
      <span class="icon">{{ isOpen ? '→' : '⚡' }}</span>
      <span class="label" v-if="!isOpen">调试注入</span>
    </button>

    <!-- 注入面板 -->
    <div class="injector-panel">
      <div class="panel-header">
        <h3>调试模拟注入台</h3>
        <button class="btn-close" @click="isOpen = false">×</button>
      </div>

      <div class="panel-body">
        <div class="form-group">
          <label>目标床位</label>
          <el-select v-model="selectedBed" size="small" class="w-full">
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
              <span class="ro-icon">{{ r.icon }}</span>
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
          <label class="inline-flex items-center gap-2 cursor-pointer">
            <el-switch v-model="simulateTimeout" size="small" />
            <span class="text-[11px] text-slate-600">模拟云端超时 → 边缘回退（timeout）</span>
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

        <div class="event-categories">
          <!-- P1 -->
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

          <!-- P2 -->
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

          <!-- P3 -->
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
          <span class="toast-indicator"></span>
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
const toastMsg = ref('')
const toastType = ref('')

const routeOptions = [
  { key: 'edge', label: '边缘', icon: '⚡' },
  { key: 'cloud', label: '云端', icon: '☁️' },
  { key: 'hybrid', label: '协同', icon: '🔁' },
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
  edge: '⚡ 纯边缘：本地 LLM 即时研判，低延迟',
  cloud: '☁️ 纯云端：请求云端 14B 大模型研判',
  hybrid: '🔁 云边协同：边缘初判 + 云端复核',
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
  { type: 'seizure', name: '抽搐检测' }
]

const p2Events = [
  { type: 'bed_leave', name: '患者离床' },
  { type: 'door_departure', name: '门区离开' },
  { type: 'night_wandering', name: '夜间徘徊' },
  { type: 'long_still', name: '长时间静止' },
  { type: 'abnormal_posture', name: '异常体态' }
]

const p3Events = [
  { type: 'environment_anomaly', name: '环境异常' },
  { type: 'node_offline', name: '节点失联' },
  { type: 'bedsore_risk', name: '压疮预防' },
  { type: 'device_fault', name: '设备故障' }
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
</script>

<style scoped>
.scene-injector {
  position: fixed;
  right: -310px;
  top: 90px;
  width: 310px;
  height: calc(100vh - 160px);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-left: 1px solid #d6e4ff;
  box-shadow: -10px 0 35px rgba(22, 119, 255, 0.12);
  transition: right 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  z-index: 999;
  display: flex;
  flex-direction: column;
  border-top-left-radius: 12px;
  border-bottom-left-radius: 12px;
}
.scene-injector.open {
  right: 0;
}

.injector-toggle {
  position: absolute;
  left: -42px;
  top: 24px;
  width: 42px;
  padding: 14px 6px;
  background: linear-gradient(135deg, #4096ff 0%, #1677ff 100%);
  color: #fff;
  border: none;
  border-top-left-radius: 10px;
  border-bottom-left-radius: 10px;
  cursor: pointer;
  box-shadow: -4px 0 12px rgba(22, 119, 255, 0.3);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  transition: all 0.2s ease;
}
.injector-toggle:hover {
  filter: brightness(1.05);
}
.injector-toggle .icon {
  font-size: 15px;
  font-weight: 800;
}
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
  border-bottom: 1px solid #e5e6eb;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(240, 245, 255, 0.6);
  border-top-left-radius: 12px;
}
.panel-header h3 {
  font-size: 14px;
  color: #1677ff;
  margin: 0;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.btn-close {
  background: transparent;
  border: none;
  color: #86909c;
  font-size: 22px;
  cursor: pointer;
  line-height: 1;
}
.btn-close:hover {
  color: #1d2129;
}

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
  color: #4e5969;
  font-weight: 600;
}
.slider-label-row {
  display: flex;
  justify-content: space-between;
}
.conf-val {
  font-size: 11px;
  color: #1677ff;
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
  gap: 2px;
  padding: 8px 4px;
  border-radius: 8px;
  border: 1px solid #e5e6eb;
  background: #fafafa;
  cursor: pointer;
  transition: all 0.2s;
}
.route-option.active {
  border-width: 2px;
}
.route-option.route-opt-edge.active {
  border-color: #2ea121;
  background: #e8f8e8;
}
.route-option.route-opt-cloud.active {
  border-color: #1890ff;
  background: #e6f7ff;
}
.route-option.route-opt-hybrid.active {
  border-color: #fa8c16;
  background: #fff7e6;
}
.ro-icon { font-size: 15px; }
.ro-label { font-size: 11px; font-weight: 700; color: #1d2129; }
.route-hint {
  font-size: 10px;
  color: #8a98a8;
  background: #f5f9ff;
  border-radius: 6px;
  padding: 5px 8px;
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
  border: 1px solid #e5e6eb;
  background: #fafafa;
  font-size: 11px;
  font-weight: 700;
  color: #4e5969;
  cursor: pointer;
  transition: all 0.2s;
}
.net-option.net-opt-online.active {
  border-color: #2ea121;
  background: #e8f8e8;
  color: #2ea121;
}
.net-option.net-opt-degraded.active {
  border-color: #fa8c16;
  background: #fff7e6;
  color: #fa8c16;
}
.net-option.net-opt-offline.active {
  border-color: #f5222d;
  background: #fff1f0;
  color: #f5222d;
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
  padding-bottom: 3px;
  border-bottom: 1px solid #e5e6eb;
  font-weight: 700;
}
.category h4.p1 { color: #f53f3f; }
.category h4.p2 { color: #ff7d00; }
.category h4.p3 { color: #1677ff; }

.btn-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.toast-message {
  margin-top: 14px;
  padding: 8px 12px;
  font-size: 11px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
.toast-indicator {
  width: 5px;
  height: 5px;
  border-radius: 50%;
}
.toast-message.success {
  background: rgba(0, 180, 42, 0.08);
  color: #00b42a;
  border: 1px solid rgba(0, 180, 42, 0.25);
}
.toast-message.success .toast-indicator {
  background: #00b42a;
  box-shadow: 0 0 6px #00b42a;
}
.toast-message.error {
  background: rgba(245, 63, 63, 0.08);
  color: #f53f3f;
  border: 1px solid rgba(245, 63, 63, 0.25);
}
.toast-message.error .toast-indicator {
  background: #f53f3f;
  box-shadow: 0 0 6px #f53f3f;
}
</style>
