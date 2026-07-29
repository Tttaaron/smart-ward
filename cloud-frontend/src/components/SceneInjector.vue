<template>
  <div class="scene-injector" :class="{ open: isOpen }">
    <!-- Trigger Button -->
    <button class="injector-toggle" @click="isOpen = !isOpen">
      <span class="icon">{{ isOpen ? '→' : '⚡' }}</span>
      <span class="label" v-if="!isOpen">调试注入</span>
    </button>
    
    <!-- Injection Panel -->
    <div class="injector-panel">
      <div class="panel-header">
        <h3>调试模拟注入台</h3>
        <button class="btn-close" @click="isOpen = false">×</button>
      </div>
      
      <div class="panel-body">
        <div class="form-group">
          <label>目标床位</label>
          <select v-model="selectedBed" class="form-input">
            <option value="B01">1床 (B01)</option>
            <option value="B02">2床 (B02)</option>
            <option value="B03">3床 (B03)</option>
          </select>
        </div>
        
        <div class="form-group">
          <div class="slider-label-row">
            <label>置信度</label>
            <span class="conf-val num-font">{{ (confidence * 100).toFixed(0) }}%</span>
          </div>
          <input v-model.number="confidence" type="range" min="0.5" max="1.0" step="0.05" class="form-slider" />
        </div>
        
        <div class="event-categories">
          <!-- P1 Panel -->
          <div class="category">
            <h4 class="p1">P1 紧急告警</h4>
            <div class="btn-grid">
              <button 
                v-for="evt in p1Events" 
                :key="evt.type" 
                class="btn-inject p1"
                @click="triggerEvent(evt.type)"
                :disabled="injecting"
              >
                {{ evt.name }}
              </button>
            </div>
          </div>
          
          <!-- P2 Panel -->
          <div class="category">
            <h4 class="p2">P2 高级告警</h4>
            <div class="btn-grid">
              <button 
                v-for="evt in p2Events" 
                :key="evt.type" 
                class="btn-inject p2"
                @click="triggerEvent(evt.type)"
                :disabled="injecting"
              >
                {{ evt.name }}
              </button>
            </div>
          </div>
          
          <!-- P3 Panel -->
          <div class="category">
            <h4 class="p3">P3 常规提示</h4>
            <div class="btn-grid">
              <button 
                v-for="evt in p3Events" 
                :key="evt.type" 
                class="btn-inject p3"
                @click="triggerEvent(evt.type)"
                :disabled="injecting"
              >
                {{ evt.name }}
              </button>
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
import { ref } from 'vue'
import api from '../api/index.js'

const isOpen = ref(false)
const injecting = ref(false)
const selectedBed = ref('B01')
const confidence = ref(0.9)
const toastMsg = ref('')
const toastType = ref('')

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

const triggerEvent = async (eventType) => {
  injecting.value = true
  try {
    const res = await api.injectEvent({
      ward_id: 'W-01',
      bed_id: selectedBed.value,
      event_type: eventType,
      confidence: confidence.value
    })
    if (res.data.code === 0) {
      showToast('事件注入成功！', 'success')
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
  background: rgba(22, 38, 66, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-left: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: -10px 0 35px rgba(0, 0, 0, 0.5);
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
  background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%);
  color: #0f172a;
  border: none;
  border-top-left-radius: 10px;
  border-bottom-left-radius: 10px;
  cursor: pointer;
  box-shadow: -4px 0 12px rgba(217, 119, 6, 0.3);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  transition: all 0.2s ease;
}
.injector-toggle:hover {
  filter: brightness(1.1);
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
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(15, 23, 42, 0.4);
  border-top-left-radius: 12px;
}
.panel-header h3 {
  font-size: 14px;
  color: #fbbf24;
  margin: 0;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.btn-close {
  background: transparent;
  border: none;
  color: #64748b;
  font-size: 22px;
  cursor: pointer;
  line-height: 1;
}
.btn-close:hover {
  color: #f1f5f9;
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
  color: #64748b;
  font-weight: 600;
}
.slider-label-row {
  display: flex;
  justify-content: space-between;
}
.conf-val {
  font-size: 11px;
  color: #fbbf24;
  font-weight: 700;
}
.form-input {
  background: rgba(15, 23, 42, 0.45);
  color: #f1f5f9;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  padding: 7px;
  font-size: 12px;
  outline: none;
  font-family: inherit;
}
.form-input option {
  background: #1e293b;
  color: #f1f5f9;
}
.form-slider {
  width: 100%;
  accent-color: #fbbf24;
  background: rgba(15,23,42,0.45);
  height: 4px;
  border-radius: 2px;
  outline: none;
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
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  font-weight: 700;
}
.category h4.p1 { color: #f87171; }
.category h4.p2 { color: #fbbf24; }
.category h4.p3 { color: #60a5fa; }
.btn-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.btn-inject {
  padding: 7px 4px;
  font-size: 11px;
  background: rgba(30, 41, 59, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.04);
  color: #cbd5e1;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.btn-inject:hover:not(:disabled) {
  background: rgba(30, 41, 59, 0.75);
  transform: translateY(-1px);
}
.btn-inject.p1:hover:not(:disabled) { border-color: #ef4444; color: #f87171; box-shadow: 0 0 8px rgba(239,68,68,0.25); }
.btn-inject.p2:hover:not(:disabled) { border-color: #f59e0b; color: #fbbf24; box-shadow: 0 0 8px rgba(245,158,11,0.2); }
.btn-inject.p3:hover:not(:disabled) { border-color: #3b82f6; color: #60a5fa; box-shadow: 0 0 8px rgba(59,130,246,0.2); }
.btn-inject:disabled {
  opacity: 0.45;
  cursor: not-allowed;
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
  background: rgba(16, 185, 129, 0.12);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.25);
}
.toast-message.success .toast-indicator {
  background: #10b981;
  box-shadow: 0 0 6px #10b981;
}
.toast-message.error {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.25);
}
.toast-message.error .toast-indicator {
  background: #ef4444;
  box-shadow: 0 0 6px #ef4444;
}
.num-font {
  font-family: 'Outfit', sans-serif;
}
</style>
