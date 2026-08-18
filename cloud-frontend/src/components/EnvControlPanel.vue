<template>
  <div class="env-panel">
    <div class="env-header">
      <span class="env-title">
        <el-icon :size="14" aria-hidden="true"><SetUp /></el-icon>
        环境联动
      </span>
      <span class="chip chip-success">控制链路在线</span>
    </div>

    <div class="env-devices">
      <div v-for="dev in devices" :key="dev.id" class="env-device-row">
        <div class="dev-info">
          <span class="dev-icon" aria-hidden="true">
            <el-icon :size="16"><component :is="deviceIcon(dev.id)" /></el-icon>
          </span>
          <div class="dev-copy">
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
          :class="{ active: dev.state === 'on' }"
          :disabled="toggling === dev.id"
          @click="toggleDevice(dev)"
        >
          <span class="toggle-knob" aria-hidden="true"></span>
        </button>
      </div>
    </div>

    <transition name="toast">
      <div v-if="toast" class="env-toast" :class="toastType">{{ toast }}</div>
    </transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import api from '../api/index.js'

const devices = ref([
  { id: 'ac', name: '空调', state: 'off', node_id: 'EDGE-W01-B01' },
  { id: 'light', name: '灯光', state: 'on', node_id: 'EDGE-W01-B01' },
  { id: 'fresh_air', name: '新风', state: 'off', node_id: 'EDGE-W01-B01' },
])
const toggling = ref(null)
const toast = ref('')
const toastType = ref('')

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
.env-panel { display: flex; flex-direction: column; gap: 9px; }

.env-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.env-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text);
  font-size: 13px;
  font-weight: 800;
}
.env-title :deep(.el-icon) { color: var(--primary); }

.env-devices {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.env-device-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 9px;
  transition: border-color 0.2s ease;
}
.env-device-row:hover { border-color: var(--line-strong); }

.dev-info { display: flex; align-items: center; gap: 9px; }
.dev-icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  color: var(--primary);
  background: var(--primary-soft);
  border: 1px solid rgba(42, 125, 225, 0.25);
  border-radius: 8px;
}
.dev-copy { display: flex; flex-direction: column; gap: 2px; }
.dev-name { color: var(--text); font-size: 12.5px; font-weight: 700; }
.dev-status { font-size: 10px; font-weight: 600; }
.dev-status.on { color: var(--success); }
.dev-status.off { color: var(--text-3); }

/* 霓虹拨动开关 */
.env-toggle {
  position: relative;
  width: 40px;
  height: 22px;
  padding: 0;
  border: 1px solid var(--line-strong);
  border-radius: 11px;
  background: var(--bg-deep);
  cursor: pointer;
  transition: all 0.22s ease;
}
.toggle-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--text-3);
  transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}
.env-toggle.active {
  background: rgba(42, 125, 225, 0.14);
  border-color: rgba(42, 125, 225, 0.55);
  box-shadow: 0 0 8px rgba(42, 125, 225, 0.20);
}
.env-toggle.active .toggle-knob {
  left: 20px;
  background: var(--primary);
  box-shadow: 0 0 6px rgba(42, 125, 225, 0.55);
}
.env-toggle:disabled { opacity: 0.55; cursor: not-allowed; }
.env-toggle:focus-visible { outline: 2px solid rgba(42, 125, 225, 0.5); outline-offset: 2px; }

.env-toast {
  padding: 7px 10px;
  font-size: 11px;
  font-weight: 700;
  text-align: center;
  border-radius: 7px;
  border: 1px solid;
}
.env-toast.success {
  color: var(--success);
  background: var(--success-soft);
  border-color: rgba(52, 211, 153, 0.35);
}
.env-toast.error {
  color: var(--danger);
  background: var(--danger-soft);
  border-color: rgba(220, 38, 38, 0.35);
}
.toast-enter-active, .toast-leave-active { transition: all 0.25s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
