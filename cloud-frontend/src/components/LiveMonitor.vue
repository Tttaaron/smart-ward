<template>
  <Transition name="slide-up">
    <div
      v-if="visible"
      class="live-monitor fixed right-4 bottom-14 w-[420px] bg-slate-900/95 border border-slate-700/60 rounded-xl shadow-2xl flex flex-col overflow-hidden text-slate-100 z-50 backdrop-blur-xl"
    >
      <!-- 头部 -->
      <div class="flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-slate-900 to-slate-800 border-b border-slate-700/60">
        <div class="flex items-center gap-2">
          <span class="relative flex h-2 w-2">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
          </span>
          <span class="text-sm font-bold tracking-wide">{{ bedId }}床 实时视频监护</span>
          <span class="text-[9px] bg-red-500/20 text-red-400 border border-red-500/40 px-1.5 py-0.5 rounded font-extrabold">LIVE</span>
        </div>
        <div class="flex items-center gap-1.5">
          <button
            @click="showSettings = !showSettings"
            class="text-slate-400 hover:text-white text-xs px-2 py-1 rounded bg-slate-800/60 border border-slate-700/60 transition-colors"
          >
            ⚙️ {{ showSettings ? '返回' : '配置' }}
          </button>
          <button @click="$emit('close')" class="text-slate-400 hover:text-white text-lg leading-none px-1 transition-colors">&times;</button>
        </div>
      </div>

      <!-- 视频画面区域 -->
      <div class="relative w-full h-[240px] bg-black overflow-hidden">
        <!-- 扫描线（半透明，不遮挡画面） -->
        <div v-if="!privacyCut && activeAuthorized && !showSettings" class="absolute inset-0 z-20 pointer-events-none scanlines"></div>

        <!-- 配置面板 -->
        <div
          v-if="showSettings"
          class="absolute inset-0 bg-slate-950/95 p-4 z-30 flex flex-col gap-3"
        >
          <h4 class="text-xs font-bold text-blue-400">⚙️ 硬件摄像头流接入配置</h4>
          <p class="text-[10px] text-slate-400 leading-relaxed">
            接入硬件设备时输入边缘端摄像头流地址（MJPEG/WebRTC）。留空则自动使用本机摄像头。
          </p>
          <div class="flex flex-col gap-1">
            <label class="text-[9px] text-slate-500 font-bold uppercase font-mono">Camera Stream URL (MJPEG)</label>
            <input
              v-model="tempStreamUrl"
              type="text"
              placeholder="留空 = 本机摄像头 / 或填 MJPEG 流地址"
              class="bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-blue-500"
            />
          </div>
          <div class="flex gap-2">
            <el-button size="small" type="primary" class="flex-1 !text-[10px]" @click="saveSettings">保存并连接</el-button>
            <el-button size="small" type="info" plain class="!text-[10px]" @click="clearSettings">重置为本机摄像头</el-button>
          </div>
        </div>

        <!-- 隐私切断画面 -->
        <div
          v-if="privacyCut || !activeAuthorized"
          class="absolute inset-0 flex flex-col items-center justify-center bg-slate-950 text-center p-4 z-20"
        >
          <div class="w-12 h-12 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center mb-3 text-2xl animate-pulse">🔒</div>
          <h4 class="text-xs font-bold text-slate-300">隐私保护已开启</h4>
          <p class="text-[10px] text-slate-500 max-w-[260px] mt-1 leading-relaxed">
            日常切断实时画面以保护患者隐私。紧急事件时自动授权开启。
          </p>
          <el-button v-if="!activeAuthorized" size="small" type="primary" class="mt-3 !text-[10px]" @click="authorizeOpen">
            🛡️ 授权临时开启
          </el-button>
        </div>

        <!-- 真实画面层 -->
        <div v-if="!privacyCut && activeAuthorized && !showSettings" class="absolute inset-0 z-0">
          <!-- 外部 MJPEG 流 -->
          <img
            v-if="realStreamUrl"
            :src="realStreamUrl"
            class="w-full h-full object-cover"
            @error="handleStreamError"
            @load="handleStreamLoad"
          />
          <template v-else>
            <!-- 本机摄像头 - 始终渲染，用 v-show 控制显隐，确保 ref 可用 -->
            <video
              ref="videoRef"
              autoplay
              playsinline
              muted
              :style="{ display: cameraReady ? 'block' : 'none' }"
              class="w-full h-full object-cover"
            ></video>
            <!-- 摄像头加载中 -->
            <div v-if="cameraStarting" class="absolute inset-0 flex items-center justify-center bg-black">
              <div class="flex flex-col items-center gap-2">
                <div class="w-8 h-8 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin"></div>
                <span class="text-[10px] text-slate-400 font-mono">CONNECTING CAMERA...</span>
              </div>
            </div>
            <!-- 摄像头不可用 - 简洁占位 -->
            <div v-if="!cameraReady && !cameraStarting" class="absolute inset-0 flex flex-col items-center justify-center bg-slate-900 text-center">
              <div class="w-16 h-16 rounded-full bg-slate-800 flex items-center justify-center mb-3 text-3xl">📹</div>
              <span class="text-[11px] text-slate-400 font-medium">摄像头未授权或不可用</span>
              <el-button size="small" type="primary" plain class="mt-3 !text-[10px]" @click="startCamera">重试连接</el-button>
            </div>
          </template>
        </div>

        <!-- OSD 信息（半透明，不遮挡画面） -->
        <div
          v-if="!privacyCut && activeAuthorized && !showSettings"
          class="absolute inset-x-0 top-0 z-15 p-2 flex justify-between items-start pointer-events-none"
        >
          <div class="flex flex-col gap-0.5 text-[9px] font-mono text-emerald-400 bg-black/50 px-2 py-1 rounded backdrop-blur-sm leading-tight">
            <span>CAM-{{ bedId }}</span>
            <span class="text-slate-300">{{ formattedTime }}</span>
          </div>
          <div class="flex flex-col items-end gap-0.5 text-[9px] font-mono bg-black/50 px-2 py-1 rounded backdrop-blur-sm leading-tight">
            <span class="text-emerald-400">{{ realStreamUrl ? 'YOLO MJPEG' : 'OFFLINE' }}</span>
            <span class="text-amber-400">YOLOv8n-pose</span>
          </div>
        </div>

        <!-- 底部事件标识 -->
        <div
          v-if="!privacyCut && activeAuthorized && !showSettings"
          class="absolute inset-x-0 bottom-0 z-15 p-2 bg-gradient-to-t from-black/70 to-transparent flex justify-between items-end pointer-events-none"
        >
          <div class="flex flex-col">
            <span class="text-[11px] font-bold text-red-400 uppercase tracking-wide font-mono">
              ⚠ {{ eventTypeLabel(eventType) }}
            </span>
            <span class="text-[9px] text-slate-300">W-01病区 {{ bedId }}号床 · 置信度 {{ (confidence * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </div>

      <!-- 底部控制栏 -->
      <div class="bg-slate-950/90 p-3 border-t border-slate-700/60 flex flex-col gap-2.5">
        <!-- 操作按钮 -->
        <div class="flex gap-2">
          <el-button
            size="small"
            :type="privacyCut ? 'success' : 'danger'"
            plain
            class="flex-1 !text-[11px] !font-bold"
            @click="togglePrivacy"
          >
            {{ privacyCut ? '🛡️ 恢复画面' : '🔒 阻断画面' }}
          </el-button>
          <el-button
            v-if="cameraReady && !realStreamUrl"
            size="small"
            type="info"
            plain
            class="!text-[11px] !font-bold"
            @click="restartCamera"
          >
            🔄 重连
          </el-button>
        </div>

        <!-- 监护日志 -->
        <div class="flex flex-col">
          <div class="flex justify-between items-center mb-1">
            <span class="text-[10px] text-slate-400 font-semibold">AI 监护日志</span>
            <span class="text-emerald-400 font-mono text-[9px] flex items-center gap-1">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>ONLINE
            </span>
          </div>
          <div class="logs bg-slate-900 border border-slate-800 rounded p-1.5 h-14 overflow-y-auto text-[9px] font-mono flex flex-col gap-0.5">
            <div v-for="(log, idx) in logs" :key="idx" class="leading-tight">
              <span class="text-slate-600">[{{ log.time }}]</span>
              <span class="ml-1" :class="log.color">{{ log.text }}</span>
            </div>
            <div v-if="logs.length === 0" class="text-slate-600 italic">等待事件...</div>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, computed, nextTick } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  bedId: { type: String, default: 'B01' },
  eventType: { type: String, default: 'fall_suspected' },
  confidence: { type: Number, default: 0.90 }
})

const emit = defineEmits(['close'])

const privacyCut = ref(false)
const activeAuthorized = ref(false)
const logs = ref([])
const formattedTime = ref('')

// 流配置
const showSettings = ref(false)
// 默认指向宿主机 YOLO 脚本的 MJPEG 推流（localhost:8090/stream）
const MJPEG_DEFAULT = 'http://localhost:8090/stream'
const realStreamUrl = ref(MJPEG_DEFAULT)
const tempStreamUrl = ref(MJPEG_DEFAULT)
const streamLoading = ref(false)
const streamError = ref(false)

// 本机摄像头 (getUserMedia 备用，当前默认走 MJPEG)
const videoRef = ref(null)
const cameraReady = ref(false)
const cameraStarting = ref(false)
let cameraStream = null

let timeInterval = null

const eventTypeLabel = (t) => ({
  fall_suspected: '疑似跌倒 (P1)', nurse_call: '护士呼叫 (P1)',
  fall_prediction: '坠床预警 (P1)', seizure: '抽搐检测 (P1)',
  bed_leave: '离床预警 (P2)', door_departure: '门区异常 (P2)',
  night_wandering: '夜间徘徊 (P2)', long_still: '长时间静止 (P2)',
  abnormal_posture: '异常体态 (P2)', environment_anomaly: '环境异常 (P3)',
  node_offline: '节点失联 (P3)', bedsore_risk: '压疮预防 (P3)',
  device_fault: '设备故障 (P3)',
}[t] || t)

const addLog = (text, type = 'info') => {
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  const colorMap = {
    info: 'text-slate-400', success: 'text-emerald-400',
    warning: 'text-amber-400', danger: 'text-red-400'
  }
  logs.value.unshift({ time, text, color: colorMap[type] || 'text-slate-400' })
  if (logs.value.length > 20) logs.value.pop()
}

// ===== 本机摄像头 =====
const startCamera = async () => {
  if (realStreamUrl.value) return
  if (cameraStream) return
  cameraStarting.value = true
  cameraReady.value = false
  try {
    // 1. 先取流
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false
    })
    // 2. 等 DOM 渲染（video 元素始终在 DOM，但确保 Vue 状态更新）
    await nextTick()
    await nextTick()  // 双重 nextTick 确保稳妥
    // 3. 绑定流到 video
    if (videoRef.value) {
      videoRef.value.srcObject = cameraStream
      // 4. 显式 play（解决 autoplay 未触发导致绿幕）
      try {
        await videoRef.value.play()
      } catch (e) {
        console.warn('video.play() 被拦截，依赖 autoplay', e)
      }
      cameraReady.value = true
      cameraStarting.value = false
      addLog('本机摄像头已接入实时画面', 'success')
    } else {
      // videoRef 还没就绪，重试一次
      await new Promise(r => setTimeout(r, 100))
      if (videoRef.value) {
        videoRef.value.srcObject = cameraStream
        try { await videoRef.value.play() } catch (e) {}
        cameraReady.value = true
        cameraStarting.value = false
        addLog('本机摄像头已接入实时画面', 'success')
      } else {
        throw new Error('video 元素未就绪')
      }
    }
  } catch (err) {
    cameraReady.value = false
    cameraStarting.value = false
    addLog(`摄像头接入失败：${err.message || err}`, 'warning')
  }
}

const stopCamera = () => {
  if (cameraStream) {
    cameraStream.getTracks().forEach(t => t.stop())
    cameraStream = null
  }
  if (videoRef.value) {
    videoRef.value.srcObject = null
  }
  cameraReady.value = false
}

const restartCamera = () => {
  stopCamera()
  addLog('正在重新连接摄像头...', 'info')
  setTimeout(() => startCamera(), 300)
}

// ===== 配置 =====
const saveSettings = () => {
  realStreamUrl.value = tempStreamUrl.value
  localStorage.setItem(`camera_stream_url_${props.bedId}`, realStreamUrl.value)
  showSettings.value = false
  if (realStreamUrl.value) {
    streamLoading.value = true
    streamError.value = false
    stopCamera()
    addLog(`流地址更改：连接至 ${realStreamUrl.value}`, 'warning')
  } else {
    streamLoading.value = false
    streamError.value = false
    startCamera()
    addLog('已切换为本机摄像头', 'info')
  }
}

const clearSettings = () => {
  tempStreamUrl.value = MJPEG_DEFAULT
  saveSettings()
}

const handleStreamLoad = () => {
  streamLoading.value = false
  streamError.value = false
  addLog('硬件视频流接入成功', 'success')
}

const handleStreamError = () => {
  streamLoading.value = false
  streamError.value = true
  addLog('视频流连接失败', 'danger')
}

const authorizeOpen = () => {
  activeAuthorized.value = true
  privacyCut.value = false
  addLog(`授权开启 ${props.bedId}床 视频流`, 'success')
  startCamera()
}

const togglePrivacy = () => {
  privacyCut.value = !privacyCut.value
  addLog(privacyCut.value ? `画面已阻断` : `画面已恢复`, privacyCut.value ? 'danger' : 'success')
}

// ===== 监听 =====
watch(() => props.bedId, (newBed) => {
  const savedUrl = localStorage.getItem(`camera_stream_url_${newBed}`) || MJPEG_DEFAULT
  realStreamUrl.value = savedUrl
  tempStreamUrl.value = savedUrl
  if (props.visible) {
    activeAuthorized.value = true
    privacyCut.value = false
    logs.value = []
    addLog(`接入 ${newBed}床 视频探针`, 'warning')
    startCamera()
  }
})

watch(() => props.visible, (newVal) => {
  if (newVal) {
    const savedUrl = localStorage.getItem(`camera_stream_url_${props.bedId}`) || MJPEG_DEFAULT
    realStreamUrl.value = savedUrl
    tempStreamUrl.value = savedUrl
    activeAuthorized.value = true
    privacyCut.value = false
    logs.value = []
    addLog(`接入 ${props.bedId}床 视频探针`, 'warning')
    addLog('YOLOv8n-pose 引擎在线', 'success')
    startCamera()
  } else {
    stopCamera()
  }
})

onMounted(() => {
  formattedTime.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  timeInterval = setInterval(() => {
    formattedTime.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  }, 1000)
  if (props.visible) {
    activeAuthorized.value = true
    startCamera()
  }
})

onUnmounted(() => {
  stopCamera()
  if (timeInterval) clearInterval(timeInterval)
})
</script>

<script>
export default { name: 'LiveMonitor' }
</script>

<style scoped>
.live-monitor {
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(255, 255, 255, 0.06) inset;
}

/* 扫描线效果 - 半透明、不遮挡画面 */
.scanlines {
  background: repeating-linear-gradient(
    0deg,
    rgba(16, 185, 129, 0.03) 0px,
    rgba(16, 185, 129, 0.03) 1px,
    transparent 1px,
    transparent 3px
  );
}

/* 日志滚动条 */
.logs::-webkit-scrollbar { width: 4px; }
.logs::-webkit-scrollbar-track { background: transparent; }
.logs::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }

/* 过渡动画 */
.slide-up-enter-active, .slide-up-leave-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-up-enter-from, .slide-up-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>
