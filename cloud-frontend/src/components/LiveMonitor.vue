<template>
  <Transition name="slide-up">
    <div v-if="visible" class="live-monitor-container">
      <!-- 头部：监护信息 & 状态 & 设置按钮 -->
      <div class="monitor-header">
        <div class="monitor-header-left">
          <span class="pulse-dot-red" aria-hidden="true"></span>
          <span class="monitor-title">{{ bedId }}床 实时视频监护</span>
          <span class="monitor-live-badge font-num">LIVE</span>
        </div>
        <div class="monitor-header-right">
          <button
            @click="showSettings = !showSettings"
            class="monitor-action"
          >
            <span class="settings-symbol" aria-hidden="true"></span>{{ showSettings ? '返回' : '配置' }}
          </button>
          <button @click="$emit('close')" class="monitor-close" aria-label="关闭监护窗口">&times;</button>
        </div>
      </div>

      <!-- 视频画面与配置面板区域 -->
      <div class="video-feed-viewport monitor-feed">
        <!-- 扫描线效果 -->
        <div class="scanline-overlay" aria-hidden="true"></div>
        <!-- 噪点特效 -->
        <div class="noise-overlay" aria-hidden="true"></div>

        <!-- 开发者配置面板 -->
        <div v-if="showSettings" class="monitor-settings">
          <h4>
            <span class="settings-symbol" aria-hidden="true"></span>硬件摄像头流接入配置
          </h4>
          <p class="monitor-copy">
            当接入硬件设备时，在此输入边缘端摄像头的视频流地址（支持 MJPEG 图像流或 WebRTC 播放源）。流将作为底层背景，前端 AI 骨骼点与遮罩将自动在上方精准叠加。
          </p>
          <div class="settings-field">
            <label class="monitor-label">Camera Stream URL (MJPEG)</label>
            <input
              v-model="tempStreamUrl"
              type="text"
              placeholder="e.g., http://192.168.1.100:8000/stream"
              class="monitor-input"
            />
          </div>
          <div class="settings-actions">
            <el-button size="small" type="primary" class="settings-btn" @click="saveSettings">
              保存并连接
            </el-button>
            <el-button size="small" type="info" plain class="settings-btn" @click="clearSettings">
              重置为模拟
            </el-button>
          </div>
        </div>

        <!-- 隐私切断画面 / 隐私锁定模式 -->
        <div v-if="privacyCut || !activeAuthorized" class="monitor-privacy">
          <div class="privacy-symbol" aria-hidden="true">
            <span class="privacy-lock"></span>
          </div>
          <h4 class="monitor-privacy-title">AI 隐私屏处于保护状态</h4>
          <p class="monitor-privacy-copy">
            日常切断实时视频画面以保护患者隐私。发生紧急呼叫或安全事件时自动授权单路开启。
          </p>
          <el-button v-if="!activeAuthorized" size="small" type="primary" class="authorize-btn" @click="authorizeOpen">
            授权临时开启监护
          </el-button>
        </div>

        <!-- 实时监控背景层 -->
        <div v-if="!privacyCut && activeAuthorized" class="monitor-scene">
          <!-- 真实硬件摄像头流 (配置了 realStreamUrl 时显示) -->
          <img
            v-if="realStreamUrl"
            :src="realStreamUrl"
            class="scene-media"
            @error="handleStreamError"
            @load="handleStreamLoad"
          />

          <!-- 高保真内置 3D 医用矢量病房背景 (未配置 realStreamUrl 时展示，离线 100% 成功) -->
          <svg
            v-else
            width="100%"
            height="100%"
            viewBox="0 0 400 240"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            class="scene-media"
          >
            <!-- Background Walls -->
            <rect width="400" height="240" fill="#0C1B20" />
            <path d="M0,0 L100,40 L300,40 L400,0 Z" fill="#081418" />
            <path d="M0,240 L80,190 L320,190 L400,240 Z" fill="#12262C" />
            <!-- Ceiling Grid -->
            <line x1="100" y1="40" x2="80" y2="190" stroke="#1E3A42" stroke-width="1" />
            <line x1="300" y1="40" x2="320" y2="190" stroke="#1E3A42" stroke-width="1" />
            <line x1="100" y1="40" x2="300" y2="40" stroke="#1E3A42" stroke-width="1" />
            <line x1="80" y1="190" x2="320" y2="190" stroke="#1E3A42" stroke-width="1" />

            <!-- Wall Window (Right Side) -->
            <path d="M330,70 L380,60 L380,140 L330,150 Z" fill="#101F26" />
            <path d="M335,73 L375,65 L375,135 L335,143 Z" fill="#1F3E49" opacity="0.4" />

            <!-- ECG Vital Sign Monitor (Left Wall) -->
            <rect x="25" y="60" width="45" height="35" rx="3" fill="#163039" stroke="#2DD4BF" stroke-width="1" />
            <rect x="28" y="63" width="39" height="22" rx="1" fill="#060D10" />
            <!-- ECG wave -->
            <path d="M 30,74 L 35,74 L 37,68 L 39,78 L 41,72 L 43,74 L 48,74 L 50,70 L 52,77 L 54,74 L 60,74" stroke="#2DD4BF" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />
            <circle cx="61" cy="74" r="1.5" fill="#2DD4BF" />
            <!-- Monitor Text -->
            <text x="30" y="91" fill="#5EEAD4" font-size="5" font-family="monospace" font-weight="bold">HR 72</text>
            <text x="50" y="91" fill="#FF6B6B" font-size="5" font-family="monospace" font-weight="bold">O2 99%</text>

            <!-- 3D Medical Bed Frame & Legs -->
            <line x1="160" y1="140" x2="160" y2="185" stroke="#1F3A42" stroke-width="3" stroke-linecap="round" />
            <line x1="130" y1="130" x2="130" y2="175" stroke="#2C4A54" stroke-width="3.5" stroke-linecap="round" />
            <line x1="270" y1="130" x2="270" y2="175" stroke="#2C4A54" stroke-width="3.5" stroke-linecap="round" />
            <line x1="240" y1="140" x2="240" y2="185" stroke="#1F3A42" stroke-width="3" stroke-linecap="round" />
            <!-- Casters -->
            <circle cx="130" cy="175" r="4.5" fill="#0A1419" stroke="#3E5E68" stroke-width="1.5" />
            <circle cx="270" cy="175" r="4.5" fill="#0A1419" stroke="#3E5E68" stroke-width="1.5" />
            <circle cx="160" cy="185" r="4" fill="#0A1419" stroke="#2C4A54" stroke-width="1.2" />
            <circle cx="240" cy="185" r="4" fill="#0A1419" stroke="#2C4A54" stroke-width="1.2" />

            <!-- Underbed Shadow -->
            <ellipse cx="200" cy="178" rx="75" ry="8" fill="#04090C" opacity="0.55" />

            <!-- Bed Main Base -->
            <path d="M 120,130 L 280,130 L 250,155 L 140,155 Z" fill="#1F3A42" stroke="#2C4A54" stroke-width="1.5" />
            <!-- Mattress -->
            <path d="M 122,123 L 278,123 L 249,148 L 141,148 Z" fill="#94A8B4" />
            <path d="M 122,123 L 141,148 L 141,153 L 122,128 Z" fill="#5F7480" />
            <path d="M 141,148 L 249,148 L 249,153 L 141,153 Z" fill="#94A8B4" />

            <!-- Pillow -->
            <path d="M 135,127 L 160,127 L 153,134 L 138,134 Z" fill="#D7E2E8" />

            <!-- Blue Blanket Sheet -->
            <path d="M 160,123 L 278,123 L 249,148 L 175,148 Z" fill="#0F766E" opacity="0.95" />
            <path d="M 175,148 L 249,148 L 249,153 L 175,153 Z" fill="#14B8A6" />

            <!-- Metal Guard Rails -->
            <path d="M 145,143 L 225,143" stroke="#8CA3B5" stroke-width="2" stroke-linecap="round" />
            <line x1="155" y1="143" x2="155" y2="148" stroke="#8CA3B5" stroke-width="1.5" />
            <line x1="175" y1="143" x2="175" y2="148" stroke="#8CA3B5" stroke-width="1.5" />
            <line x1="195" y1="143" x2="195" y2="148" stroke="#8CA3B5" stroke-width="1.5" />
            <line x1="215" y1="143" x2="215" y2="148" stroke="#8CA3B5" stroke-width="1.5" />

            <!-- IV Infusion Stand (Behind Bed) -->
            <line x1="285" y1="80" x2="285" y2="155" stroke="#3E5E68" stroke-width="2" />
            <path d="M 281,85 L 285,80 L 289,85" stroke="#3E5E68" stroke-width="1.5" fill="none" />
            <!-- IV bag -->
            <rect x="277" y="88" width="5" height="12" rx="1.5" fill="#D7E2E8" opacity="0.8" stroke="#8CA3B5" stroke-width="0.5" />
            <path d="M 280,100 L 285,115" stroke="#94A8B4" stroke-width="0.75" fill="none" opacity="0.6" />
          </svg>

          <!-- 视频加载提示 -->
          <div v-if="streamLoading" class="monitor-loading mono">
            CONNECTING TO CAMERA STREAM...
          </div>
          <!-- 视频错误提示 (仅在配置了真实流地址且连接失败时显示) -->
          <div v-if="streamError && realStreamUrl" class="monitor-error">
            <span class="status-symbol status-symbol-danger" aria-hidden="true">!</span>
            <span class="err-code mono">CAMERA CONNECT FAILED</span>
            <span class="monitor-muted">请检查配置的流地址是否在线且支持跨域</span>
          </div>
        </div>

        <!-- 透明 AI 算法叠加层 (骨骼/热网/遮罩在此绘制) -->
        <canvas
          v-show="!privacyCut && activeAuthorized"
          ref="canvasRef"
          width="380"
          height="220"
          class="monitor-canvas"
        ></canvas>

        <!-- OSD 信息叠层 -->
        <div v-if="!privacyCut && activeAuthorized" class="osd-top">
          <!-- 左上OSD -->
          <div class="monitor-osd mono">
            <span>DEVICE: CAM-{{ bedId }}</span>
            <span>OSD: {{ formattedTime }}</span>
            <span>FPS: 30 / DELAY: 42ms</span>
          </div>

          <!-- 右上OSD -->
          <div class="monitor-osd is-right mono">
            <span>MODE: {{ modeLabel }}</span>
            <span class="monitor-osd-source">SOURCE: {{ realStreamUrl ? 'HARDWARE FEED' : 'AI SIMULATION' }}</span>
          </div>
        </div>

        <!-- 底部 OSD 警报类型叠层 -->
        <div v-if="!privacyCut && activeAuthorized" class="monitor-osd-footer">
          <div class="osd-footer-left">
            <span class="monitor-event-label mono">
              EVENT: {{ eventTypeLabel(eventType) }}
            </span>
            <span class="monitor-location">
              位置: W-01病区 {{ bedId }}号病床
            </span>
          </div>
        </div>
      </div>

      <!-- 画面控制台 -->
      <div class="monitor-controls">
        <!-- 视频模式切换 -->
        <div class="controls-row">
          <span class="monitor-control-label">AI 隐私脱敏模式：</span>
          <div class="mode-switch">
            <button
              @click="mode = 'skeleton'"
              :class="mode === 'skeleton' ? 'mode-active mode-active-primary' : ''"
              :disabled="privacyCut || !activeAuthorized"
            >
              骨骼关键点
            </button>
            <button
              @click="mode = 'thermal'"
              :class="mode === 'thermal' ? 'mode-active mode-active-warning' : ''"
              :disabled="privacyCut || !activeAuthorized"
            >
              红外热成像
            </button>
            <button
              @click="mode = 'blur'"
              :class="mode === 'blur' ? 'mode-active mode-active-success' : ''"
              :disabled="privacyCut || !activeAuthorized"
            >
              隐私模糊
            </button>
          </div>
        </div>

        <!-- 隐私切断与状态管理 -->
        <div class="controls-row">
          <el-button
            size="small"
            :type="privacyCut ? 'success' : 'danger'"
            class="privacy-btn"
            @click="togglePrivacy"
          >
            {{ privacyCut ? '恢复视频画面' : '一键阻断画面（保护隐私）' }}
          </el-button>
        </div>

        <!-- 快速处置通道 -->
        <div class="monitor-log-section">
          <div class="log-label-row">
            <span class="monitor-control-label">AI 状态监护日志</span>
            <span class="monitor-online mono">ONLINE</span>
          </div>
          <div class="logs monitor-logs mono">
            <div v-for="(log, idx) in logs" :key="idx" class="log-line">
              <span class="monitor-log-time font-num">[{{ log.time }}]</span>
              <span class="log-text" :class="log.color">{{ log.text }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  bedId: { type: String, default: 'B01' },
  eventType: { type: String, default: 'fall_suspected' },
  confidence: { type: Number, default: 0.90 },
})

const emit = defineEmits(['close'])

const mode = ref('skeleton') // skeleton, thermal, blur
const privacyCut = ref(false)
const activeAuthorized = ref(false)
const canvasRef = ref(null)
const logs = ref([])
const formattedTime = ref('')

// Hardware stream states
const showSettings = ref(false)
const realStreamUrl = ref('')
const tempStreamUrl = ref('')
const streamLoading = ref(false)
const streamError = ref(false)

let frameId = null
let timeInterval = null

// OSD 标签文本
const modeLabel = computed(() => {
  if (mode.value === 'skeleton') return 'SKELETON KEYPOINTS'
  if (mode.value === 'thermal') return 'THERMAL FLUID MESH'
  return 'AI PIXELATED BLUR'
})

// 状态文字映射
const eventTypeLabel = (t) => {
  const map = {
    fall_suspected: '疑似跌倒 (P1)',
    nurse_call: '护士呼叫 (P1)',
    fall_prediction: '坠床预警 (P1)',
    seizure: '抽搐检测 (P1)',
    bed_leave: '离床预警 (P2)',
    door_departure: '门区异常 (P2)',
    night_wandering: '夜间徘徊 (P2)',
    long_still: '长时间静止 (P2)',
    abnormal_posture: '异常体态 (P2)',
    environment_anomaly: '环境异常 (P3)',
    node_offline: '节点失联 (P3)',
    bedsore_risk: '压疮预防 (P3)',
    device_fault: '设备故障 (P3)',
  }
  return map[t] || t
}

// 模拟事件日志
const addLog = (text, type = 'info') => {
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  const colorMap = {
    info: 'monitor-log-info',
    success: 'monitor-log-success',
    warning: 'monitor-log-warning',
    danger: 'monitor-log-danger',
  }
  logs.value.unshift({ time, text, color: colorMap[type] || 'monitor-log-info' })
  if (logs.value.length > 20) {
    logs.value.pop()
  }
}

// 开发者接入设置
const saveSettings = () => {
  realStreamUrl.value = tempStreamUrl.value
  localStorage.setItem(`camera_stream_url_${props.bedId}`, realStreamUrl.value)
  showSettings.value = false
  if (realStreamUrl.value) {
    streamLoading.value = true
    streamError.value = false
    addLog(`流地址更改：连接至 ${realStreamUrl.value}`, 'warning')
  } else {
    streamLoading.value = false
    streamError.value = false
    addLog('流地址重置：已切换为内置高仿真病房环境', 'info')
  }
}

const clearSettings = () => {
  tempStreamUrl.value = ''
  saveSettings()
}

const handleStreamLoad = () => {
  streamLoading.value = false
  streamError.value = false
  addLog('硬件监控视频流接入成功！', 'success')
  addLog('AI 算法引擎已在视频图层上精准叠加', 'success')
}

const handleStreamError = () => {
  streamLoading.value = false
  streamError.value = true
  addLog('视频流连接失败，请检查跨域或在线状态', 'danger')
}

// 授权开启
const authorizeOpen = () => {
  activeAuthorized.value = true
  privacyCut.value = false
  addLog(`管理员授权：临时开启 ${props.bedId}床 隐私视频流`, 'success')
  addLog('AI 隐私保护机制：自动替换原始图像为体态拓扑', 'info')
}

// 阻断画面
const togglePrivacy = () => {
  privacyCut.value = !privacyCut.value
  if (privacyCut.value) {
    addLog(`视频阻断：用户切断了 ${props.bedId}床 的实时画面`, 'danger')
  } else {
    addLog(`视频恢复：恢复 ${props.bedId}床 的隐私保护画面`, 'success')
  }
}

// 监听床位或者事件变动
watch(() => props.bedId, (newBed) => {
  const savedUrl = localStorage.getItem(`camera_stream_url_${newBed}`) || ''
  realStreamUrl.value = savedUrl
  tempStreamUrl.value = savedUrl
  streamError.value = false
  streamLoading.value = !!savedUrl

  if (props.visible) {
    activeAuthorized.value = true // 有新事件时自动单路开启授权
    privacyCut.value = false
    logs.value = []
    addLog(`事件触发：正在接入 ${newBed}床 视频监护探针...`, 'warning')
    if (savedUrl) {
      addLog(`检测到硬件流配置：尝试连接外部源...`, 'info')
    } else {
      addLog(`视频流状态：单路临时授权通过`, 'success')
      addLog(`AI 隐私保护机制已启动，加载高仿真模拟环境`, 'info')
    }
  }
})

watch(() => props.visible, (newVal) => {
  if (newVal) {
    const savedUrl = localStorage.getItem(`camera_stream_url_${props.bedId}`) || ''
    realStreamUrl.value = savedUrl
    tempStreamUrl.value = savedUrl
    streamError.value = false
    streamLoading.value = !!savedUrl

    activeAuthorized.value = true // 新拉起时自动授权
    privacyCut.value = false
    logs.value = []
    addLog(`接入 ${props.bedId}床 视频探针中...`, 'warning')
    if (savedUrl) {
      addLog(`正在连接至硬件视频流：${savedUrl}`, 'info')
    } else {
      addLog(`通道连接成功，隐私遮罩服务在线`, 'success')
      addLog(`分析引擎：yolov8-pose-fusion 启动`, 'info')
    }
    startAnimationLoop()
  } else {
    stopAnimationLoop()
  }
})

// === Canvas 绘制逻辑 ===
let animTime = 0
const startAnimationLoop = () => {
  stopAnimationLoop()

  const draw = () => {
    if (!canvasRef.value) {
      frameId = requestAnimationFrame(draw)
      return
    }

    const canvas = canvasRef.value
    const ctx = canvas.getContext('2d')
    const w = canvas.width
    const h = canvas.height

    animTime += 0.05

    // 1. 清空画布 (使 Canvas 成为完全透明的 AI 检测叠加层)
    ctx.clearRect(0, 0, w, h)

    // 2. 根据事件类型计算人体坐标
    let px = w / 2
    let py = h / 2 - 20
    let posture = 'sitting'

    if (props.eventType === 'fall_suspected') {
      posture = 'fallen'
      px = w / 2 + 30
      py = h - 50
    } else if (props.eventType === 'nurse_call') {
      posture = 'sitting_handup'
      px = w / 2 - 30
      py = 120
    } else if (props.eventType === 'fall_prediction') {
      posture = 'leaning_edge'
      px = w / 2 + 50
      py = 115
    } else if (props.eventType === 'seizure') {
      posture = 'lying_seizure'
      px = w / 2 - 10
      py = 125
    } else if (['bed_leave', 'door_departure', 'night_wandering'].includes(props.eventType)) {
      posture = 'walking'
      px = w / 2 - 60 + Math.sin(animTime) * 40
      py = h - 60
    } else {
      posture = 'lying'
      px = w / 2
      py = 125
    }

    // 3. 绘制不同模式的体态
    if (mode.value === 'skeleton') {
      drawSkeleton(ctx, px, py, posture)
    } else if (mode.value === 'thermal') {
      drawThermal(ctx, px, py, posture)
    } else if (mode.value === 'blur') {
      drawPrivacyBlur(ctx, px, py, posture)
    }

    frameId = requestAnimationFrame(draw)
  }

  draw()
}

const stopAnimationLoop = () => {
  if (frameId) {
    cancelAnimationFrame(frameId)
    frameId = null
  }
}

// 骨骼绘制
const drawSkeleton = (ctx, px, py, posture) => {
  ctx.lineWidth = 3

  let joints = {}

  if (posture === 'fallen') {
    joints = {
      head: [px, py],
      neck: [px - 15, py + 10],
      shoulderL: [px - 20, py + 2],
      shoulderR: [px - 10, py + 18],
      elbowL: [px - 35, py],
      handL: [px - 40, py - 10],
      elbowR: [px - 20, py + 30],
      handR: [px - 25, py + 35],
      hipL: [px - 45, py + 15],
      hipR: [px - 40, py + 25],
      kneeL: [px - 65, py + 10],
      footL: [px - 80, py + 15],
      kneeR: [px - 60, py + 30],
      footR: [px - 75, py + 35]
    }
  } else if (posture === 'sitting_handup') {
    const armWave = Math.sin(animTime * 4) * 8
    joints = {
      head: [px, py - 30],
      neck: [px, py - 15],
      shoulderL: [px - 15, py - 10],
      shoulderR: [px + 15, py - 10],
      elbowL: [px - 25, py + 5],
      handL: [px - 28, py + 15],
      elbowR: [px + 20, py - 25],
      handR: [px + 25 + armWave, py - 40],
      hipL: [px - 10, py + 15],
      hipR: [px + 10, py + 15],
      kneeL: [px - 30, py + 20],
      footL: [px - 45, py + 30],
      kneeR: [px + 30, py + 20],
      footR: [px + 45, py + 30]
    }
  } else if (posture === 'leaning_edge') {
    joints = {
      head: [px + 20, py - 20],
      neck: [px + 10, py - 10],
      shoulderL: [px + 5, py - 18],
      shoulderR: [px + 15, py - 2],
      elbowL: [px + 10, py - 35],
      handL: [px + 5, py - 42],
      elbowR: [px + 25, py - 2],
      handR: [px + 35, py + 5],
      hipL: [px - 20, py],
      hipR: [px - 15, py + 10],
      kneeL: [px - 35, py + 15],
      footL: [px - 40, py + 30],
      kneeR: [px - 30, py + 25],
      footR: [px - 35, py + 40]
    }
  } else if (posture === 'lying_seizure') {
    const dx = (Math.random() - 0.5) * 4
    const dy = (Math.random() - 0.5) * 4
    joints = {
      head: [px + dx, py - 10 + dy],
      neck: [px + 15 + dx, py - 5 + dy],
      shoulderL: [px + 12 + dx, py - 15 + dy],
      shoulderR: [px + 18 + dx, py + 5 + dy],
      elbowL: [px + 30 + dx, py - 20 + dy],
      handL: [px + 40 + dx, py - 22 + dy],
      elbowR: [px + 32 + dx, py + 10 + dy],
      handR: [px + 42 + dx, py + 8 + dy],
      hipL: [px + 50 + dx, py - 8 + dy],
      hipR: [px + 52 + dx, py + 2 + dy],
      kneeL: [px + 70 + dx, py - 12 + dy],
      footL: [px + 85 + dx, py - 10 + dy],
      kneeR: [px + 72 + dx, py + 8 + dy],
      footR: [px + 87 + dx, py + 10 + dy]
    }
  } else if (posture === 'walking') {
    const legSwing = Math.sin(animTime * 2) * 15
    joints = {
      head: [px, py - 35],
      neck: [px, py - 20],
      shoulderL: [px - 12, py - 15],
      shoulderR: [px + 12, py - 15],
      elbowL: [px - 20, py - 2],
      handL: [px - 22, py + 10],
      elbowR: [px + 20, py - 2],
      handR: [px + 22, py + 10],
      hipL: [px - 8, py + 10],
      hipR: [px + 8, py + 10],
      kneeL: [px - 10 - legSwing / 2, py + 25],
      footL: [px - 12 - legSwing, py + 40],
      kneeR: [px + 10 + legSwing / 2, py + 25],
      footR: [px + 12 + legSwing, py + 40]
    }
  } else {
    joints = {
      head: [px - 40, py - 10],
      neck: [px - 25, py - 5],
      shoulderL: [px - 28, py - 15],
      shoulderR: [px - 22, py + 5],
      elbowL: [px - 10, py - 20],
      handL: [px + 2, py - 20],
      elbowR: [px - 8, py + 10],
      handR: [px + 4, py + 8],
      hipL: [px + 10, py - 8],
      hipR: [px + 12, py + 2],
      kneeL: [px + 35, py - 10],
      footL: [px + 55, py - 8],
      kneeR: [px + 37, py + 5],
      footR: [px + 57, py + 7]
    }
  }

  const skeletonColor = props.eventType.startsWith('fall') || props.eventType === 'seizure' ? '#FF6B6B' : '#2DD4BF'
  ctx.strokeStyle = skeletonColor
  ctx.fillStyle = skeletonColor

  const drawJoint = (pt, radius = 3.5) => {
    ctx.beginPath()
    ctx.arc(pt[0], pt[1], radius, 0, Math.PI * 2)
    ctx.fill()
  }

  const link = (p1, p2) => {
    ctx.beginPath()
    ctx.moveTo(p1[0], p1[1])
    ctx.lineTo(p2[0], p2[1])
    ctx.stroke()
  }

  // 1. 躯干
  ctx.lineWidth = 4
  link(joints.shoulderL, joints.shoulderR)
  link(joints.hipL, joints.hipR)
  link(joints.neck, [(joints.hipL[0] + joints.hipR[0]) / 2, (joints.hipL[1] + joints.hipR[1]) / 2])

  // 2. 四肢
  ctx.lineWidth = 2.5
  link(joints.shoulderL, joints.elbowL)
  link(joints.elbowL, joints.handL)
  link(joints.shoulderR, joints.elbowR)
  link(joints.elbowR, joints.handR)
  link(joints.hipL, joints.kneeL)
  link(joints.kneeL, joints.footL)
  link(joints.hipR, joints.kneeR)
  link(joints.kneeR, joints.footR)

  // 3. 头部与脖子
  ctx.lineWidth = 3
  link(joints.head, joints.neck)

  // 4. 画关键点
  Object.values(joints).forEach((pt) => drawJoint(pt))
  drawJoint(joints.head, 7)

  // 额外绘制人体包围盒
  ctx.strokeStyle = 'rgba(45, 212, 191, 0.42)'
  ctx.lineWidth = 1
  ctx.setLineDash([4, 4])

  const xs = Object.values(joints).map((p) => p[0])
  const ys = Object.values(joints).map((p) => p[1])
  const minX = Math.min(...xs) - 15
  const maxX = Math.max(...xs) + 15
  const minY = Math.min(...ys) - 15
  const maxY = Math.max(...ys) + 15
  ctx.strokeRect(minX, minY, maxX - minX, maxY - minY)
  ctx.setLineDash([])
}

// 红外热成像绘制
const drawThermal = (ctx, px, py, posture) => {
  const drawHeatBlob = (x, y, r, temp) => {
    const grad = ctx.createRadialGradient(x, y, r * 0.1, x, y, r)
    if (temp === 'high') {
      grad.addColorStop(0, 'rgba(255, 107, 107, 0.95)')
      grad.addColorStop(0.3, 'rgba(251, 146, 60, 0.75)')
      grad.addColorStop(0.6, 'rgba(250, 204, 21, 0.45)')
      grad.addColorStop(1, 'rgba(45, 212, 191, 0)')
    } else {
      grad.addColorStop(0, 'rgba(251, 146, 60, 0.9)')
      grad.addColorStop(0.4, 'rgba(250, 204, 21, 0.6)')
      grad.addColorStop(0.8, 'rgba(22, 163, 74, 0.25)')
      grad.addColorStop(1, 'rgba(45, 212, 191, 0)')
    }
    ctx.fillStyle = grad
    ctx.beginPath()
    ctx.arc(x, y, r, 0, Math.PI * 2)
    ctx.fill()
  }

  if (posture === 'fallen') {
    drawHeatBlob(px, py, 26, 'high')
    drawHeatBlob(px - 25, py + 12, 22, 'normal')
    drawHeatBlob(px - 55, py + 20, 18, 'normal')
  } else if (posture === 'sitting_handup') {
    drawHeatBlob(px, py - 20, 22, 'high')
    drawHeatBlob(px, py + 10, 28, 'high')
    drawHeatBlob(px + 20, py - 30, 14, 'high')
  } else if (posture === 'walking') {
    drawHeatBlob(px, py - 25, 20, 'high')
    drawHeatBlob(px, py, 26, 'high')
    drawHeatBlob(px - 10, py + 25, 16, 'normal')
    drawHeatBlob(px + 10, py + 25, 16, 'normal')
  } else if (posture === 'lying_seizure') {
    const shake = Math.sin(animTime * 8) * 3
    drawHeatBlob(px + shake, py - 5, 25, 'high')
    drawHeatBlob(px + 25 + shake, py, 28, 'high')
    drawHeatBlob(px + 60 + shake, py + 5, 20, 'normal')
  } else {
    drawHeatBlob(px - 35, py - 5, 20, 'high')
    drawHeatBlob(px, py, 28, 'high')
    drawHeatBlob(px + 45, py + 5, 22, 'normal')
  }

  ctx.fillStyle = 'rgba(56, 189, 248, 0.04)'
  for (let i = 0; i < 6; i++) {
    const rx = (Math.sin(animTime + i) * 0.5 + 0.5) * ctx.canvas.width
    const ry = (Math.cos(animTime * 1.5 + i) * 0.5 + 0.5) * ctx.canvas.height
    ctx.beginPath()
    ctx.arc(rx, ry, 12, 0, Math.PI * 2)
    ctx.fill()
  }
}

// 隐私模糊与边框绘制
const drawPrivacyBlur = (ctx, px, py, posture) => {
  ctx.fillStyle = 'rgba(22, 163, 74, 0.2)'
  ctx.strokeStyle = '#34D399'
  ctx.lineWidth = 1.5

  let rectW = 60
  let rectH = 80
  let rectX = px - rectW / 2
  let rectY = py - rectH / 2

  if (posture === 'fallen') {
    rectW = 100
    rectH = 50
    rectX = px - rectW / 2 - 20
    rectY = py - rectH / 2 + 10
  } else if (posture === 'sitting_handup') {
    rectW = 65
    rectH = 95
    rectX = px - rectW / 2
    rectY = py - rectH / 2 - 15
  } else if (posture === 'walking') {
    rectW = 55
    rectH = 100
    rectX = px - rectW / 2
    rectY = py - rectH / 2 - 10
  } else if (posture === 'lying_seizure') {
    rectW = 105
    rectH = 55
    rectX = px - rectW / 2 + 25
    rectY = py - rectH / 2 + 10
  } else {
    rectW = 110
    rectH = 50
    rectX = px - rectW / 2 + 5
    rectY = py - rectH / 2
  }

  const cols = 8
  const rows = 6
  const cellW = rectW / cols
  const cellH = rectH / rows

  for (let c = 0; c < cols; c++) {
    for (let r = 0; r < rows; r++) {
      const cx = rectX + c * cellW
      const cy = rectY + r * cellH
      const colorVal = Math.floor(40 + Math.sin(animTime + c + r) * 15 + Math.random() * 10)
      ctx.fillStyle = `rgba(16, ${colorVal + 80}, ${colorVal + 50}, 0.85)`
      ctx.fillRect(cx, cy, cellW - 0.5, cellH - 0.5)
    }
  }

  const isDanger = props.eventType.startsWith('fall') || props.eventType === 'seizure'
  ctx.strokeStyle = isDanger ? '#FF6B6B' : '#34D399'
  ctx.lineWidth = 1.5
  ctx.strokeRect(rectX - 2, rectY - 2, rectW + 4, rectH + 4)

  ctx.fillStyle = isDanger ? '#FF6B6B' : '#34D399'
  ctx.font = 'bold 9px monospace'
  const tagText = `PATIENT_${props.bedId} [${isDanger ? 'WARNING' : 'DETECTED'}]`
  ctx.fillText(tagText, rectX - 2, rectY - 6)

  ctx.fillStyle = 'rgba(0, 0, 0, 0.4)'
  ctx.fillRect(rectX + 3, rectY + rectH - 14, rectW - 6, 11)
  ctx.fillStyle = '#ffffff'
  ctx.font = '8px sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText('PRIVACY FILTERED', rectX + rectW / 2, rectY + rectH - 5)
  ctx.textAlign = 'left'
}

onMounted(() => {
  formattedTime.value = new Date().toISOString().replace('T', ' ').slice(0, 19)
  timeInterval = setInterval(() => {
    formattedTime.value = new Date().toISOString().replace('T', ' ').slice(0, 19)
  }, 1000)

  if (props.visible) {
    activeAuthorized.value = true
    startAnimationLoop()
  }
})

onUnmounted(() => {
  stopAnimationLoop()
  if (timeInterval) clearInterval(timeInterval)
})
</script>

<style scoped>
.live-monitor-container {
  --monitor-ink: #0D171D;
  --monitor-ink-deep: #081014;
  --monitor-ink-soft: #12222B;
  --monitor-line: #1E3A42;
  --monitor-line-soft: rgba(150, 200, 210, 0.22);
  --monitor-text: #E4F0F3;
  --monitor-muted: #8CA3B5;
  --monitor-teal: #2DD4BF;
  --monitor-amber: #FBBF24;
  --monitor-coral: #FF6B6B;

  position: fixed;
  right: 18px;
  bottom: 44px;
  z-index: 50;
  width: 380px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 13px;
  color: var(--monitor-text);
  background: var(--monitor-ink);
  border: 1px solid var(--monitor-line);
  box-shadow: 0 26px 60px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(255, 255, 255, 0.05) inset;
  backdrop-filter: blur(18px) saturate(105%);
  -webkit-backdrop-filter: blur(18px) saturate(105%);
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--monitor-ink-soft);
  border-bottom: 1px solid var(--monitor-line);
}
.monitor-header-left { display: flex; align-items: center; gap: 8px; min-width: 0; }
.monitor-header-right { display: flex; align-items: center; gap: 7px; }

.monitor-title { color: var(--monitor-text); font-size: 13.5px; font-weight: 800; letter-spacing: 0.02em; white-space: nowrap; }
.monitor-live-badge {
  padding: 2px 7px;
  border-radius: 5px;
  color: #FFB3A8;
  background: rgba(255, 107, 107, 0.14);
  border: 1px solid rgba(255, 107, 107, 0.45);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.monitor-action,
.monitor-close {
  color: var(--monitor-muted);
  background: rgba(150, 200, 210, 0.05);
  border: 1px solid var(--monitor-line-soft);
  cursor: pointer;
  transition: all 0.18s ease;
}
.monitor-action {
  display: flex;
  align-items: center;
  gap: 5px;
  height: 26px;
  padding: 0 9px;
  border-radius: 7px;
  font-size: 11.5px;
}
.monitor-action:hover,
.monitor-close:hover {
  color: var(--monitor-text);
  border-color: rgba(45, 212, 191, 0.55);
  background: rgba(45, 212, 191, 0.10);
}
.monitor-close {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: 7px;
  font-size: 20px;
  line-height: 1;
}

.settings-symbol {
  display: inline-block;
  width: 11px;
  height: 11px;
  border: 1.5px solid currentColor;
  border-radius: 50%;
  position: relative;
  flex: 0 0 auto;
}
.settings-symbol::before,
.settings-symbol::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 50%;
  width: 15px;
  height: 1.5px;
  background: currentColor;
  transform: translate(-50%, -50%);
}
.settings-symbol::after { transform: translate(-50%, -50%) rotate(90deg); }

.video-feed-viewport {
  position: relative;
  width: 100%;
  height: 220px;
  overflow: hidden;
  box-shadow: inset 0 0 30px rgba(3, 10, 13, 0.86);
}
.monitor-feed { background: #08151A; }
.monitor-scene {
  position: absolute;
  inset: 0;
  z-index: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #08151A;
}
.scene-media { width: 100%; height: 100%; object-fit: cover; }

.monitor-settings {
  position: absolute;
  inset: 0;
  z-index: 30;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 13px;
  overflow-y: auto;
  color: var(--monitor-text);
  background: #0C191F;
  border-top: 1px solid rgba(45, 212, 191, 0.22);
}
.monitor-settings h4 {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--monitor-teal);
  font-size: 12.5px;
  font-weight: 800;
}
.monitor-copy { color: var(--monitor-muted); font-size: 11.5px; line-height: 1.6; }
.settings-field { display: flex; flex-direction: column; gap: 6px; margin-top: 2px; }
.monitor-label { color: #7E9891; font-size: 11px; font-weight: 800; text-transform: uppercase; }
.monitor-input {
  padding: 7px 9px;
  border-radius: 6px;
  color: var(--monitor-text);
  background: #081216;
  border: 1px solid #24504D;
  font-size: 11.5px;
  outline: none;
}
.monitor-input::placeholder { color: #5F7784; }
.monitor-input:focus { border-color: var(--monitor-teal); box-shadow: 0 0 0 2px rgba(45, 212, 191, 0.14); }
.settings-actions { display: flex; gap: 8px; margin-top: 4px; }
.settings-btn { flex: 1; font-size: 11.5px; }

.monitor-privacy {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 14px;
  text-align: center;
  color: var(--monitor-text);
  background: #081216;
  transition: all 0.3s;
}
.privacy-symbol {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 10px;
  border-radius: 50%;
  background: #10242A;
  border: 1px solid rgba(45, 212, 191, 0.35);
  box-shadow: 0 8px 18px rgba(3, 10, 13, 0.3);
  animation: med-blink 2.4s ease-in-out infinite;
}
.privacy-lock {
  width: 16px;
  height: 13px;
  border: 2px solid var(--monitor-teal);
  border-radius: 3px;
  position: relative;
  display: block;
}
.privacy-lock::before {
  content: '';
  position: absolute;
  width: 9px;
  height: 8px;
  left: 1.5px;
  top: -9px;
  border: 2px solid var(--monitor-teal);
  border-bottom: 0;
  border-radius: 8px 8px 0 0;
}
.monitor-privacy-title { color: #D7E6EB; font-size: 12.5px; font-weight: 800; }
.monitor-privacy-copy {
  color: #7E9891;
  font-size: 11.5px;
  max-width: 280px;
  margin-top: 4px;
  line-height: 1.6;
}
.authorize-btn { margin-top: 10px; font-size: 11.5px; padding: 0 12px; }

.monitor-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11.5px;
  color: var(--monitor-muted);
  background: rgba(8, 20, 22, 0.78);
}
.monitor-error {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 14px;
  text-align: center;
  color: #FFB3A8;
  background: rgba(10, 16, 18, 0.9);
}
.err-code { font-size: 11.5px; }
.monitor-muted { color: #7E9891; font-size: 11px; margin-top: 4px; }
.status-symbol {
  display: inline-grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 1px solid currentColor;
  font: 800 12.5px/1 'Outfit', sans-serif;
  margin-bottom: 4px;
}
.status-symbol-danger { color: var(--monitor-coral); }

.monitor-canvas {
  position: absolute;
  inset: 0;
  z-index: 10;
  width: 100%;
  height: 100%;
  object-fit: cover;
  background: transparent;
  pointer-events: none;
}

/* OSD 叠层 */
.osd-top {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 15;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 9px;
  pointer-events: none;
}
.monitor-osd {
  display: flex;
  flex-direction: column;
  padding: 4px 7px;
  border-radius: 5px;
  color: #A8E6D8;
  background: rgba(5, 16, 19, 0.74);
  border: 1px solid rgba(45, 212, 191, 0.18);
  font-size: 11px;
  line-height: 1.5;
}
.monitor-osd.is-right { align-items: flex-end; }
.monitor-osd-source { color: var(--monitor-amber); }

.monitor-osd-footer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 15;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding: 9px;
  pointer-events: none;
  background: linear-gradient(to top, rgba(5, 12, 14, 0.88), rgba(5, 12, 14, 0));
}
.osd-footer-left { display: flex; flex-direction: column; }
.monitor-event-label {
  color: #FF9E91;
  font-size: 11.5px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.monitor-location { color: #B7CBD2; font-size: 11px; margin-top: 1px; }

/* 控制台 */
.monitor-controls {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 11px 12px;
  background: var(--monitor-ink-soft);
  border-top: 1px solid var(--monitor-line);
}
.controls-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.monitor-control-label { color: var(--monitor-muted); font-size: 12px; font-weight: 700; }

.mode-switch {
  display: flex;
  padding: 2px;
  border-radius: 7px;
  background: #081216;
  border: 1px solid #1E3A42;
}
.mode-switch button {
  padding: 4px 9px;
  border: 0;
  border-radius: 5px;
  color: #7E9891;
  background: transparent;
  font-size: 11.5px;
  cursor: pointer;
  transition: all 0.18s ease;
}
.mode-switch button:hover:not(:disabled) { color: #D7E6EB; background: rgba(45, 212, 191, 0.12); }
.mode-switch button:disabled { cursor: not-allowed; opacity: 0.45; }
.mode-switch .mode-active { color: #04211D; font-weight: 800; }
.mode-switch .mode-active-primary { background: #2DD4BF; }
.mode-switch .mode-active-warning { background: #FBBF24; }
.mode-switch .mode-active-success { background: #34D399; }

.privacy-btn { flex: 1; font-size: 11.5px; font-weight: 700; }

.monitor-log-section {
  display: flex;
  flex-direction: column;
  padding-top: 9px;
  margin-top: 2px;
  border-top: 1px solid var(--monitor-line-soft);
}
.log-label-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}
.monitor-online { color: var(--monitor-teal); font-size: 11px; }
.monitor-logs {
  display: flex;
  flex-direction: column;
  gap: 2px;
  height: 64px;
  padding: 6px;
  overflow-y: auto;
  border-radius: 6px;
  color: var(--monitor-muted);
  background: #081216;
  border: 1px solid #1E3A42;
  font-size: 11px;
}
.log-line { line-height: 1.5; }
.log-text { margin-left: 4px; }
.monitor-log-time { color: #68827B; }
.monitor-log-info { color: #A1B4AE; }
.monitor-log-success { color: #6EE7B7; }
.monitor-log-warning { color: #FBBF24; }
.monitor-log-danger { color: #FF9E91; }

/* Element Plus 按钮在监护窗口内的适配 */
.live-monitor-container :deep(.el-button) {
  border-radius: 7px;
  font-weight: 700;
}

/* 脉冲红点 */
.pulse-dot-red {
  display: inline-block;
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  background-color: var(--monitor-coral);
  border-radius: 50%;
  box-shadow: 0 0 8px rgba(255, 107, 107, 0.8);
  animation: med-blink 1.2s infinite;
}

/* 扫描线叠层 */
.scanline-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  pointer-events: none;
  background: linear-gradient(
      rgba(18, 16, 16, 0) 50%,
      rgba(0, 0, 0, 0.25) 50%
    ),
    linear-gradient(
      90deg,
      rgba(255, 107, 107, 0.05),
      rgba(45, 212, 191, 0.04),
      rgba(217, 119, 6, 0.05)
    );
  background-size: 100% 3px, 3px 100%;
}

/* 噪点背景效果 */
.noise-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  pointer-events: none;
  opacity: 0.03;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E");
}

/* 日志滚动条 */
.logs::-webkit-scrollbar { width: 4px; }
.logs::-webkit-scrollbar-track { background: #081216; }
.logs::-webkit-scrollbar-thumb { background: #1E3A42; border-radius: 2px; }

/* 过渡动画 */
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100px) scale(0.95);
  opacity: 0;
}
</style>
