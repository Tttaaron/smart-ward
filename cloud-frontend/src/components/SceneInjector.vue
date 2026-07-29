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
