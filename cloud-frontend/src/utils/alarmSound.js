/**
 * 告警提示音（Web Audio 合成蜂鸣，无需音频资源文件）
 *
 * 浏览器自动播放策略要求用户先与页面交互过才能出声，因此：
 * - 页面任意首次 pointerdown/keydown 即创建并解锁 AudioContext；
 * - P1 告警到达时调用 playAlarmSound()，被拦截时静默失败不影响页面。
 */

let ctx = null
let primed = false

const ensureCtx = () => {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext
    if (!AC) return null
    ctx = new AC()
  }
  if (ctx.state === 'suspended') ctx.resume().catch(() => {})
  return ctx
}

export const primeAlarmSound = () => {
  if (primed) return
  primed = true
  ensureCtx()
}

// 三段急促蜂鸣（标准医疗告警节奏），总长约 1 秒
export const playAlarmSound = () => {
  try {
    const ac = ensureCtx()
    if (!ac) return
    const t0 = ac.currentTime
    const seq = [
      [880, 0.00, 0.16],
      [880, 0.24, 0.16],
      [880, 0.48, 0.16],
      [1046, 0.72, 0.28],
    ]
    seq.forEach(([freq, at, dur]) => {
      const osc = ac.createOscillator()
      const gain = ac.createGain()
      osc.type = 'square'
      osc.frequency.value = freq
      gain.gain.setValueAtTime(0.0001, t0 + at)
      gain.gain.exponentialRampToValueAtTime(0.14, t0 + at + 0.02)
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + at + dur)
      osc.connect(gain)
      gain.connect(ac.destination)
      osc.start(t0 + at)
      osc.stop(t0 + at + dur + 0.05)
    })
  } catch (e) {
    // 音频被禁用时静默，不影响告警展示
  }
}

// 页面任意首次交互即解锁音频上下文
if (typeof window !== 'undefined') {
  const unlock = () => {
    primeAlarmSound()
    window.removeEventListener('pointerdown', unlock)
    window.removeEventListener('keydown', unlock)
  }
  window.addEventListener('pointerdown', unlock)
  window.addEventListener('keydown', unlock)
}
