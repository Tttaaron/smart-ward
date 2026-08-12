<template>
  <div class="activity-log-card">
    <div class="activity-header">
      <h3><el-icon :size="16" aria-hidden="true"><DataAnalysis /></el-icon><span>活动日志</span></h3>
      <span class="activity-badge">{{ bedCount }} 床在线</span>
    </div>

    <!-- 每床当前活动 -->
    <div class="activity-beds">
      <div
        v-for="bed in sortedBeds"
        :key="bed.bed_id"
        class="activity-bed-row"
        :class="{ switched: bed.switched }"
      >
        <div class="bed-info">
          <span class="bed-tag">{{ bed.bed_id }}床</span>
          <span class="activity-label" :class="'act-' + bed.label">
            <el-icon :size="14" aria-hidden="true"><component :is="activityIcon(bed.label)" /></el-icon>
            <span>{{ activityLabel(bed.label) }}</span>
          </span>
        </div>
        <div class="bed-meta">
          <span v-if="bed.switched && bed.previous" class="switch-chip" title="活动切换">
            {{ activityLabel(bed.previous) }} → {{ activityLabel(bed.label) }}
          </span>
          <span class="duration-tag font-num">持续 {{ fmtDuration(bed.durationSec) }}</span>
        </div>
      </div>
    </div>

    <div v-if="sortedBeds.length === 0" class="activity-empty">
      <el-icon class="empty-emoji" :size="22" aria-hidden="true"><DataLine /></el-icon>
      <span>等待边缘观测上报…</span>
    </div>

    <div class="panel-divider h-px bg-slate-100 my-2"></div>

    <!-- 活动切换时间线 -->
    <div class="switch-title">切换记录</div>
    <ul v-if="switchLog.length > 0" class="switch-list">
      <li v-for="(entry, idx) in switchLog" :key="idx" class="switch-row">
        <span class="sw-bed font-num">{{ entry.bed_id }}</span>
        <span class="sw-from">{{ activityLabel(entry.from) }}</span>
        <span class="sw-arrow">→</span>
        <span class="sw-to">{{ activityLabel(entry.to) }}</span>
        <span class="sw-time font-num">{{ fmtTime(entry.at) }}</span>
      </li>
    </ul>
    <div v-else class="switch-empty">暂无活动切换</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '../api/index.js'
import ws from '../api/websocket.js'
import { fmtDuration, fmtTime } from '../utils/eventMeta.js'

// 每床当前活动状态：bed_id -> { label, since, switched, previous, durationSec, updatedAt }
const beds = ref({})
// 切换时间线（最新在前）
const switchLog = ref([])
const nowTimestamp = ref(Date.now())

const ACTIVITY_META = {
  walking: { label: '行走', icon: 'LocationFilled' },
  eating: { label: '进食', icon: 'ForkSpoon' },
  playing_phone: { label: '玩手机', icon: 'Cellphone' },
  sleeping: { label: '睡眠', icon: 'MoonNight' },
  sitting: { label: '坐姿', icon: 'UserFilled' },
  standing: { label: '站立', icon: 'Position' },
  lying: { label: '卧躺', icon: 'Place' },
  unknown: { label: '未知', icon: 'QuestionFilled' },
}

const activityLabel = (l) => (ACTIVITY_META[l] || { label: l || '未知' }).label
const activityIcon = (l) => (ACTIVITY_META[l] || { icon: 'QuestionFilled' }).icon

const bedCount = computed(() => Object.keys(beds.value).length)

const sortedBeds = computed(() => {
  return Object.entries(beds.value)
    .map(([bed_id, s]) => ({ bed_id, ...s }))
    .sort((a, b) => a.bed_id.localeCompare(b.bed_id))
})

// 从 WS 观察消息的 camera source 提取 activity，并更新状态
const applyActivity = (bedId, activity, occurredAt) => {
  if (!activity || !activity.label) return
  const prev = beds.value[bedId]
  const sinceTs = (activity.since != null ? activity.since * 1000 : Date.now())
  const durationSec = Math.max(0, Math.floor((Date.now() - sinceTs) / 1000))

  beds.value[bedId] = {
    label: activity.label,
    since: activity.since,
    switched: !!activity.switched,
    previous: activity.previous || null,
    durationSec,
    updatedAt: occurredAt || new Date().toISOString(),
  }

  // 切换事件写入时间线（去重：同一床同一次切换只记一条）
  if (activity.switched && activity.previous && activity.previous !== activity.label) {
    const last = switchLog.value[0]
    if (!(last && last.bed_id === bedId && last.to === activity.label && last.from === activity.previous)) {
      switchLog.value.unshift({
        bed_id: bedId,
        from: activity.previous,
        to: activity.label,
        at: new Date(sinceTs).toISOString(),
      })
      if (switchLog.value.length > 50) switchLog.value.pop()
    }
  }
}

// WS observation 消息：msg.data.sources[] 中取 camera 源
const handleWsMessage = (msg) => {
  if (!msg || msg.type !== 'observation') return
  const data = msg.data || {}
  const bedId = msg.bed_id || data.bed_id
  const sources = Array.isArray(data.sources) ? data.sources : []
  const cameraSrc = sources.find((s) => s && s.source_type === 'camera')
  if (!cameraSrc) return
  applyActivity(bedId, cameraSrc.data && cameraSrc.data.activity, msg.timestamp || data.timestamp)
}

// REST 历史回填：/api/observations?source_type=camera
const loadHistory = async () => {
  try {
    const res = await api.getObservations({ source_type: 'camera', hours: 3, limit: 200 })
    const records = (res.data && res.data.data) || []
    // 每条记录是单源，data.activity 已在顶层
    for (const r of records) {
      if (r.source_type !== 'camera' || !r.data) continue
      applyActivity(r.bed_id, r.data.activity, r.timestamp)
    }
  } catch (e) {
    console.error('[ActivityLog] 加载观测历史失败', e)
  }
}

let timer = null
let unsubscribe = null

onMounted(() => {
  loadHistory()
  unsubscribe = ws.onMessage(handleWsMessage)
  // 持续时长每秒刷新
  timer = setInterval(() => {
    nowTimestamp.value = Date.now()
    for (const key in beds.value) {
      const sinceTs = beds.value[key].since != null ? beds.value[key].since * 1000 : nowTimestamp.value
      beds.value[key].durationSec = Math.max(0, Math.floor((nowTimestamp.value - sinceTs) / 1000))
    }
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (unsubscribe) unsubscribe()
})
</script>

<style scoped>
.activity-log-card {
  background: transparent;
  border: 0;
  border-radius: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.activity-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.activity-header h3 {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  color: var(--color-primary);
  margin: 0;
  font-weight: 700;
  letter-spacing: 0;
}
.activity-badge {
  font-size: 10px;
  font-weight: 700;
  color: var(--color-success);
  background: rgba(24, 131, 94, 0.08);
  border: 1px solid rgba(24, 131, 94, 0.25);
  padding: 2px 8px;
  border-radius: 10px;
}

.activity-beds {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.activity-bed-row {
  border: 1px solid #e0e7ec;
  border-radius: 6px;
  padding: 8px 10px;
  background: #fafafa;
  transition: all 0.2s;
}
.activity-bed-row.switched {
  border-color: rgba(20, 121, 118, 0.35);
  background: #edf6f4;
}
.bed-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bed-tag {
  font-weight: 800;
  color: var(--color-primary);
  background: #e4f1ef;
  border: 1px solid rgba(20, 121, 118, 0.2);
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
}
.activity-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #1d2129;
}
.activity-label.act-lying { color: #722ed1; }
.activity-label.act-standing { color: var(--color-success); }
.activity-label.act-walking { color: #13c2c2; }
.activity-label.act-sleeping { color: #531dab; }
.activity-label.act-unknown { color: #86909c; }

.bed-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}
.switch-chip {
  font-size: 9.5px;
  font-weight: 700;
  color: var(--color-primary);
  background: rgba(20, 121, 118, 0.08);
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px dashed rgba(20, 121, 118, 0.35);
}
.duration-tag {
  font-size: 10px;
  color: #86909c;
}

.activity-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 24px 0;
  color: #c9cdd4;
  font-size: 11px;
}
.empty-emoji { font-size: 22px; }

.switch-title {
  font-size: 11px;
  font-weight: 700;
  color: #4e5969;
  margin-bottom: 6px;
}
.switch-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
  flex: 1;
  min-height: 120px;
  max-height: none;
}
.switch-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  padding: 4px 8px;
  background: var(--color-surface-2);
  border-radius: 6px;
}
.sw-bed {
  font-weight: 800;
  color: var(--color-primary);
}
.sw-from { color: #86909c; }
.sw-arrow { color: var(--color-primary); font-weight: 800; }
.sw-to { color: #1d2129; font-weight: 700; }
.sw-time { margin-left: auto; color: #86909c; }
.switch-empty {
  font-size: 10px;
  color: #c9cdd4;
  padding: 8px 0;
}
</style>
