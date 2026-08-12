<template>
  <div class="env-control-card">
    <div class="env-header">
      <h3><el-icon :size="16" aria-hidden="true"><SetUp /></el-icon><span>环境联动控制</span></h3>
      <span class="env-badge" :class="connectedClass">{{ connectedText }}</span>
    </div>
    <div class="env-devices">
      <div v-for="dev in devices" :key="dev.id" class="env-device-row">
        <div class="dev-info">
          <el-icon class="dev-icon" :size="17" aria-hidden="true"><component :is="deviceIcon(dev.id)" /></el-icon>
          <div>
            <div class="dev-name">{{ dev.name }}</div>
            <div class="dev-status" :class="dev.state === 'on' ? 'on' : 'off'">
              {{ dev.state === 'on' ? '运行中' : '已关闭' }}
            </div>
          </div>
        </div>
        <button
          type="button"
          role="switch"
          :aria-checked="dev.state === 'on'"
          :aria-label="`${dev.name}${dev.state === 'on' ? '运行中' : '已关闭'}`"
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

const deviceIcon = (id) => ({
  ac: 'MostlyCloudy',
  light: 'Sunny',
  fresh_air: 'WindPower',
}[id] || 'SetUp')

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
  background: transparent;
  border: 0;
  border-radius: 0;
  padding: 0;
}
.env-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.env-header h3 {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #17212b;
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
  background: #f7f9fb;
  border: 1px solid #e5ebef;
  border-radius: 6px;
}
.dev-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dev-icon { color: var(--color-primary); flex: 0 0 auto; }
.dev-name { font-size: 12px; font-weight: 600; color: var(--color-text); }
.dev-status { font-size: 10px; }
.dev-status.on { color: #00b42a; }
.dev-status.off { color: #86909c; }
.env-toggle {
  min-width: 56px;
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid #cddae2;
  background: #ffffff;
  color: #52606d;
  font-size: 11px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.2s;
}
.env-toggle.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
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
