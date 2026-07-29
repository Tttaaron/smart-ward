<template>
  <div class="scene-injector" :class="{ open: isOpen }">
    <!-- Trigger Button -->
    <button class="injector-toggle" @click="isOpen = !isOpen">
      <span class="icon">{{ isOpen ? '→' : '⚡' }}</span>
      <span class="label" v-if="!isOpen">场景注入</span>
    </button>
    
    <!-- Injection Panel -->
    <div class="injector-panel">
      <div class="panel-header">
        <h3>场景模拟注入台</h3>
        <button class="btn-close" @click="isOpen = false">×</button>
      </div>
      
      <div class="panel-body">
        <div class="form-group">
          <label>目标床位：</label>
          <select v-model="selectedBed" class="form-input">
            <option value="B01">1床 (B01)</option>
            <option value="B02">2床 (B02)</option>
            <option value="B03">3床 (B03)</option>
          </select>
        </div>
        
        <div class="form-group">
          <label>置信度：{{ (confidence * 100).toFixed(0) }}%</label>
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
            <h4 class="p2">P2 高优先级</h4>
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
            <h4 class="p3">P3 提醒通知</h4>
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
        
        <div class="toast-message" :class="toastType" v-if="toastMsg">{{ toastMsg }}</div>
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
  right: -300px;
  top: 80px;
  width: 300px;
  height: calc(100vh - 160px);
  background: #1a2942;
  border-left: 1px solid #2a3f5f;
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.4);
  transition: right 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  border-top-left-radius: 8px;
  border-bottom-left-radius: 8px;
}
.scene-injector.open {
  right: 0;
}
.injector-toggle {
  position: absolute;
  left: -42px;
  top: 20px;
  width: 42px;
  padding: 12px 6px;
  background: #ffb74d;
  color: #0f1b2d;
  border: none;
  border-top-left-radius: 8px;
  border-bottom-left-radius: 8px;
  cursor: pointer;
  box-shadow: -2px 0 8px rgba(0,0,0,0.3);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.injector-toggle .icon {
  font-size: 16px;
  font-weight: bold;
}
.injector-toggle .label {
  font-size: 11px;
  writing-mode: vertical-rl;
  letter-spacing: 2px;
  font-weight: 600;
}
.injector-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.panel-header {
  padding: 12px;
  border-bottom: 1px solid #2a3f5f;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #152238;
  border-top-left-radius: 8px;
}
.panel-header h3 {
  font-size: 14px;
  color: #ffb74d;
  margin: 0;
}
.btn-close {
  background: transparent;
  border: none;
  color: #8a9aaa;
  font-size: 20px;
  cursor: pointer;
}
.btn-close:hover {
  color: #fff;
}
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}
.form-group {
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.form-group label {
  font-size: 11px;
  color: #8a9aaa;
}
.form-input {
  background: #243449;
  color: #e0e6ed;
  border: 1px solid #3a4f64;
  border-radius: 4px;
  padding: 6px;
  font-size: 12px;
  outline: none;
}
.form-slider {
  width: 100%;
  accent-color: #ffb74d;
}
.event-categories {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}
.category h4 {
  font-size: 11px;
  margin-bottom: 6px;
  padding-bottom: 2px;
  border-bottom: 1px solid #2a3f5f;
}
.category h4.p1 { color: #ff8a80; }
.category h4.p2 { color: #ffd180; }
.category h4.p3 { color: #80d8ff; }
.btn-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.btn-inject {
  padding: 6px 4px;
  font-size: 11px;
  background: #243449;
  border: 1px solid #3a4f64;
  color: #e0e6ed;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-inject:hover {
  background: #2d4055;
  border-color: #8a9aaa;
}
.btn-inject.p1:hover { border-color: #f44336; color: #ff8a80; }
.btn-inject.p2:hover { border-color: #ff9800; color: #ffd180; }
.btn-inject.p3:hover { border-color: #2196f3; color: #80d8ff; }
.btn-inject:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.toast-message {
  margin-top: 12px;
  padding: 8px;
  font-size: 11px;
  text-align: center;
  border-radius: 4px;
}
.toast-message.success {
  background: rgba(76, 175, 80, 0.2);
  color: #4caf50;
  border: 1px solid #4caf50;
}
.toast-message.error {
  background: rgba(244, 67, 54, 0.2);
  color: #f44336;
  border: 1px solid #f44336;
}
</style>
