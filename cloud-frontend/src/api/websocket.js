/**
 * WebSocket 客户端（云边协同护士站）
 *
 * 在原有"连接 + 消息分发 + 断线重连"基础上增加：
 * - 连接状态跟踪（connecting/connected/reconnecting/disconnected）
 * - 重连次数、最近连接/断开时间、各类消息计数
 * - 状态变化回调，供顶部状态栏做"断网/重连/恢复"视觉提示
 */

const WS_URL = `ws://${window.location.hostname}:${window.location.port}/ws`
const RECONNECT_BASE_MS = 3000   // 基础重连间隔
const RECONNECT_MAX_MS = 30000   // 最大重连间隔（退避上限）
const WATCHDOG_IDLE_MS = 45000   // 心跳看门狗：超过该时长未收到任何消息则强制重连（s）

class WebSocketClient {
  constructor() {
    this.ws = null
    this.callbacks = []
    this.statusCallbacks = []
    this.reconnectTimer = null
    this.watchdogTimer = null
    this._closed = false

    // ---- 可观测状态 ----
    this.status = 'disconnected'     // connecting / connected / reconnecting / disconnected
    this.reconnectCount = 0          // 累计重连次数
    this.connectedAt = null          // 最近一次连接成功时间
    this.disconnectedAt = null       // 最近一次断开时间
    this.lastError = null
    this.messageCount = {}           // type -> 收到条数
    this._lastMessageAt = 0          // 最近一次收到消息的时间戳
  }

  /** 记录并广播状态变化 */
  _setStatus(status, extra = {}) {
    this.status = status
    Object.assign(this, extra)
    this.statusCallbacks.forEach((cb) => {
      try {
        cb(status, {
          reconnectCount: this.reconnectCount,
          connectedAt: this.connectedAt,
          disconnectedAt: this.disconnectedAt,
          lastError: this.lastError,
          messageCount: { ...this.messageCount },
        })
      } catch (e) {
        /* ignore */
      }
    })
  }

  connect() {
    if (this._closed) return

    this._setStatus('connecting')

    try {
      this.ws = new WebSocket(WS_URL)
    } catch (e) {
      this.lastError = e
      this._scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      this.connectedAt = new Date().toISOString()
      this.reconnectCount = 0
      this.lastError = null
      this._lastMessageAt = Date.now()
      this._setStatus('connected')
      // 连接成功后清除重连定时器，启动心跳看门狗
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
      }
      this._startWatchdog()
    }

    this.ws.onmessage = (event) => {
      this._lastMessageAt = Date.now()
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'ping') {
          this.ws?.send(JSON.stringify({ type: 'pong' }))
          return
        }
        // 按类型累计消息计数（用于状态栏展示）
        this.messageCount[message.type] = (this.messageCount[message.type] || 0) + 1
        this.callbacks.forEach((cb) => {
          try {
            cb(message)
          } catch (e) {
            /* ignore */
          }
        })
      } catch (e) {
        console.error('[WS] 消息解析失败:', e)
      }
    }

    this.ws.onclose = () => {
      this.disconnectedAt = new Date().toISOString()
      this._stopWatchdog()
      this._setStatus('disconnected')
      if (!this._closed) {
        this._scheduleReconnect()
      }
    }

    this.ws.onerror = (e) => {
      this.lastError = e
      console.error('[WS] 连接错误')
    }
  }

  /**
   * 心跳看门狗：云端链路（经 aiohttp 代理）断开时浏览器收不到 close 帧，
   * 连接会长期处于半开状态。这里每 10s 检查一次，超过 WATCHDOG_IDLE_MS 未收到
   * 任何消息（含 ping），则强制关闭以触发重连，让状态栏及时进入"重连/离线"。
   */
  _startWatchdog() {
    this._stopWatchdog()
    this.watchdogTimer = setInterval(() => {
      // 非连接态或已关闭则无需监控
      if (this.status !== 'connected' || this._closed) {
        this._stopWatchdog()
        return
      }
      if (Date.now() - this._lastMessageAt > WATCHDOG_IDLE_MS) {
        console.warn('[WS] 心跳看门狗触发：链路疑似断开，强制重连')
        try {
          this.ws?.close()
        } catch (e) {
          /* ignore */
        }
      }
    }, 10000)
  }

  _stopWatchdog() {
    if (this.watchdogTimer) {
      clearInterval(this.watchdogTimer)
      this.watchdogTimer = null
    }
  }

  /** 指数退避重连，记录重连次数 */
  _scheduleReconnect() {
    if (this._closed || this.reconnectTimer) return
    this.reconnectCount += 1
    // 指数退避：3s -> 6s -> 12s ... 上限 30s
    const backoff = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, Math.min(this.reconnectCount - 1, 3)),
      RECONNECT_MAX_MS
    )
    this._setStatus('reconnecting')
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, backoff)
  }

  /** 注册消息回调，返回取消函数 */
  onMessage(callback) {
    this.callbacks.push(callback)
    return () => {
      this.callbacks = this.callbacks.filter((cb) => cb !== callback)
    }
  }

  /** 注册状态变化回调，返回取消函数 */
  onStatusChange(callback) {
    this.statusCallbacks.push(callback)
    return () => {
      this.statusCallbacks = this.statusCallbacks.filter((cb) => cb !== callback)
    }
  }

  disconnect() {
    this._closed = true
    clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
    this._stopWatchdog()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.callbacks = []
    this.statusCallbacks = []
    this._setStatus('disconnected')
  }
}

export default new WebSocketClient()
