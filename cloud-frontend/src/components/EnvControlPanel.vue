<template>
  <div class="env-control-card">
    <div class="env-header">
      <h3>🌡️ 环境联动控制</h3>
      <span class="env-badge" :class="connectedClass">{{ connectedText }}</span>
    </div>
    <div class="env-devices">
      <div v-for="dev in devices" :key="dev.id" class="env-device-row">
        <div class="dev-info">
          <span class="dev-icon">{{ dev.icon }}</span>
          <div>
            <div class="dev-name">{{ dev.name }}</div>
            <div class="dev-status" :class="dev.state === 'on' ? 'on' : 'off'">
              {{ dev.state === 'on' ? '运行中' : '已关闭' }}
            </div>
          </div>
        </div>
        <button
          class="env-toggle"
          :class="dev.state === 'on' ? 'active' : ''"
          :disabled="toggling === dev.id"
          @click="toggleDevice(dev)"
        >
          {{ toggling === dev.id ? '...' : dev.state === 'on' ? '关闭' : '开启' }}
        </button>
      </div>
    </div>
    <div v-if="toast" class="env-toast" :class="toastType">{{ toast }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api/index.js'

const devices = ref([
  { id: 'ac', name: '空调', icon: '❄️', state: 'off', node_id: 'EDGE-W01-B01' },
  { id: 'light', name: '灯光', icon: '💡', state: 'on', node_id: 'EDGE-W01-B01' },
  { id: 'fresh_air', name: '新风', icon: '🌀', state: 'off', node_id: 'EDGE-W01-B01' },
])
const toggling = ref(null)
const toast = ref('')
const toastType = ref('')
const connected = ref(true)

const connectedClass = 'online'
const connectedText = '在线'

const showToast = (msg, type = 'success') => {
  toast.value = msg
  toastType.value = type
  setTimeout(() => { toast.value = '' }, 2000)
}

const toggleDevice = async (dev) => {
  toggling.value = dev.id
  try {
    await api.triggerEnvControl({
      node_id: dev.node_id,
      device: dev.id,
      action: dev.state === 'on' ? 'off' : 'on',
      reason: 'manual_control',
    })
    dev.state = dev.state === 'on' ? 'off' : 'on'
    showToast(`${dev.name} 已${dev.state === 'on' ? '开启' : '关闭'}`)
  } catch (e) {
    showToast('控制指令下发失败', 'error')
  } finally {
    toggling.value = null
  }
}
</script>

<style scoped>
.env-control-card {
  background: #ffffff;
  border: 1px solid #d6e4ff;
  border-radius: 8px;
  padding: 12px;
}
.env-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.env-header h3 {
  font-size: 13px;
  color: #1d2129;
  margin: 0;
}
.env-badge {
  font-size: 10px;
  padding: 1px 8px;
  border-radius: 10px;
  font-weight: 600;
}
.env-badge.online {
  background: #e8f8e8;
  color: #00b42a;
  border: 1px solid #b7eb8f;
}
.env-devices {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.env-device-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  background: #f5f9ff;
  border-radius: 6px;
}
.dev-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dev-icon { font-size: 16px; }
.dev-name { font-size: 12px; font-weight: 600; color: #1d2129; }
.dev-status { font-size: 10px; }
.dev-status.on { color: #00b42a; }
.dev-status.off { color: #86909c; }
.env-toggle {
  padding: 3px 10px;
  border-radius: 4px;
  border: 1px solid #d6e4ff;
  background: #f0f5ff;
  color: #4e5969;
  font-size: 11px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s;
}
.env-toggle.active {
  background: #1677ff;
  color: #fff;
  border-color: #1677ff;
}
.env-toggle:disabled { opacity: 0.5; cursor: not-allowed; }
.env-toast {
  margin-top: 8px;
  padding: 6px;
  font-size: 11px;
  text-align: center;
  border-radius: 4px;
}
.env-toast.success {
  background: #e8f8e8;
  color: #00b42a;
  border: 1px solid #b7eb8f;
}
.env-toast.error {
  background: #fff0f0;
  color: #f53f3f;
  border: 1px solid #ffccc7;
}
</style>
