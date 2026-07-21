const WS_URL = `ws://${window.location.hostname}:${window.location.port}/ws`

class WebSocketClient {
  constructor() {
    this.ws = null
    this.callbacks = []
    this.reconnectTimer = null
    this._closed = false
  }

  connect() {
    if (this._closed) return
    this.ws = new WebSocket(WS_URL)

    this.ws.onopen = () => {
      console.log('[WS] 连接成功')
    }

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'ping') {
          this.ws?.send(JSON.stringify({ type: 'pong' }))
          return
        }
        this.callbacks.forEach(cb => {
          try { cb(message) } catch (e) { /* ignore */ }
        })
      } catch (e) {
        console.error('[WS] 消息解析失败:', e)
      }
    }

    this.ws.onclose = () => {
      console.log('[WS] 连接断开')
      if (!this._closed) {
        this.reconnectTimer = setTimeout(() => this.connect(), 3000)
      }
    }

    this.ws.onerror = (e) => {
      console.error('[WS] 连接错误')
    }
  }

  onMessage(callback) {
    this.callbacks.push(callback)
  }

  disconnect() {
    this._closed = true
    clearTimeout(this.reconnectTimer)
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.callbacks = []
  }
}

export default new WebSocketClient()
