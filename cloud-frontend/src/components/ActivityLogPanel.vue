<template>
  <div class="activity-panel">
    <div class="activity-header">
      <span class="act-title">
        <el-icon :size="14" aria-hidden="true"><DataAnalysis /></el-icon>
        当前活动
      </span>
      <span class="chip chip-success font-num">{{ bedCount }} 床在线</span>
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
          <span class="bed-tag font-num">{{ bed.bed_id }}床</span>
          <span class="activity-label" :class="'act-' + bed.label">
            <el-icon :size="13" aria-hidden="true"><component :is="activityIcon(bed.label)" /></el-icon>
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
      <el-icon :size="24" aria-hidden="true"><DataLine /></el-icon>
      <span>等待边缘观测上报…</span>
    </div>

    <div class="panel-divider" aria-hidden="true"></div>

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

const sortedBeds = computed(() =>
  Object.entries(beds.value)
    .map(([bed_id, s]) => ({ bed_id, ...s }))
    .sort((a, b) => a.bed_id.localeCompare(b.bed_id))
)

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
.activity-panel {
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
.act-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text);
  font-size: 13px;
  font-weight: 800;
}
.act-title :deep(.el-icon) { color: var(--primary); }

.activity-beds {
  display: flex;
  flex-direction: column;
  gap: 7px;
  flex: 0 0 auto;
}

.activity-bed-row {
  padding: 8px 10px;
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: 9px;
  transition: all 0.2s ease;
}
.activity-bed-row.switched {
  border-color: rgba(42, 125, 225, 0.35);
  background:
    linear-gradient(90deg, rgba(42, 125, 225, 0.05), transparent 55%),
    var(--surface-2);
}

.bed-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bed-tag {
  padding: 2px 8px;
  color: var(--primary);
  background: var(--primary-soft);
  border: 1px solid rgba(42, 125, 225, 0.28);
  border-radius: 6px;
  font-size: 11px;
  font-weight: 800;
}
.activity-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--text);
  font-size: 12px;
  font-weight: 700;
}
.activity-label.act-walking { color: var(--primary); }
.activity-label.act-standing { color: var(--success); }
.activity-label.act-sleeping { color: var(--accent); }
.activity-label.act-lying { color: #A78BFA; }
.activity-label.act-eating { color: var(--warning); }
.activity-label.act-playing_phone { color: var(--accent); }
.activity-label.act-sitting { color: var(--text-2); }
.activity-label.act-unknown { color: var(--text-3); }

.bed-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}
.switch-chip {
  padding: 2px 7px;
  color: var(--primary);
  background: var(--primary-soft);
  border: 1px dashed rgba(42, 125, 225, 0.4);
  border-radius: 5px;
  font-size: 10px;
  font-weight: 700;
}
.duration-tag { color: var(--text-3); font-size: 10.5px; }

.activity-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 22px 0;
  color: var(--text-3);
  font-size: 11.5px;
}
.activity-empty :deep(.el-icon) { color: var(--text-3); }

.switch-title {
  color: var(--text-2);
  font-size: 11px;
  font-weight: 700;
  margin-bottom: 7px;
}
.switch-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  list-style: none;
  flex: 1;
  min-height: 40px;
  overflow-y: auto;
}
.switch-row {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 4px 9px;
  background: rgba(24, 48, 76, 0.04);
  border: 1px solid var(--line);
  border-radius: 6px;
  font-size: 10.5px;
}
.sw-bed { color: var(--primary); font-weight: 800; }
.sw-from { color: var(--text-3); }
.sw-arrow { color: var(--primary); font-weight: 800; }
.sw-to { color: var(--text-2); font-weight: 700; }
.sw-time { margin-left: auto; color: var(--text-3); }
.switch-empty {
  color: var(--text-3);
  font-size: 10.5px;
  padding: 6px 0;
}
</style>
